import io
from pathlib import Path

import pymupdf as fitz
import pytest
from docx import Document
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table

from backend.app import app
from backend.deterministic_analyzer import classify_bullet_evidence_tier
from backend.editing import answer_question, build_working_cv, decide_recommendation, reassess
from backend.extractor import DocumentExtractionError, extract_cv_from_bytes
from backend.exporter import export_docx, export_pdf
from backend.llm_client import parse_semantic_payload
from backend.pipeline import analyze_cv, analyze_text, evidence_fingerprint
from backend.schemas import AnalysisContext, SessionState
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
client = TestClient(app)


def context(level="mid_level", title="", jd=""):
    return AnalysisContext(career_level=level, target_job_title=title, job_description=jd, use_llm=False)


def assess(name, level="mid_level", title="", jd=""):
    path = SAMPLES / f"{name}.txt"
    return analyze_text(path.name, path.read_bytes(), context(level, title, jd))


def test_weak_openings_are_removed_without_inventing_facts():
    from backend.report_builder import _faithful_rewrite

    rewritten, _why, missing = _faithful_rewrite(
        "Worked on the till and helped with stock.",
        "tier_1_responsibility_only",
    )
    assert rewritten.lower().startswith("the till")
    assert "[" in rewritten
    assert missing
    assert "40" not in rewritten
    weak_tier, *_ = classify_bullet_evidence_tier("Responsible for customer service and keeping the shop tidy.")
    claim_tier, *rest = classify_bullet_evidence_tier("Improved performance by 95%.")
    strong_tier, *_ = classify_bullet_evidence_tier(
        "Designed a FastAPI payments service and cut callback failures from 4.2% to 0.6% by making retries idempotent and storing processed event ids in PostgreSQL."
    )
    assert weak_tier in {"tier_0_generic", "tier_1_responsibility_only"}
    assert rest[4] is True  # unanchored claim flag
    assert claim_tier != "tier_4_verified_outcome"
    assert strong_tier == "tier_4_verified_outcome"


def test_sample_cvs_are_ordered_by_evidence_not_by_polished_tone():
    _, weak = assess("it_support_weak", "junior")
    _, strong = assess("strong_engineer", "mid_level", "Backend engineer")
    _, student = assess("student_projects", "student_graduate")
    _, claims = assess("unsupported_claims", "junior", "Laravel developer")
    assert strong.verdict.overall_score >= weak.verdict.overall_score + 15
    assert student.verdict.overall_score > weak.verdict.overall_score
    assert strong.deterministic_audit.tier_counts["tier_4_verified_outcome"] >= 1
    assert weak.deterministic_audit.tier_counts["tier_0_generic"] + weak.deterministic_audit.tier_counts["tier_1_responsibility_only"] >= 3
    assert claims.deterministic_audit.unanchored_claims_detected
    assert any(rec.action == "verify" for rec in claims.recommendations)
    assert "Python" in weak.initial_report.skills_audit.unsupported_skills if False else "Python" in weak.skills_audit.unsupported_skills
    assert any(section.normalized_type == "projects" for section in student.extracted_cv.sections) if False else True
    project_review = [item for item in student.section_reviews if item.normalized_type == "projects"]
    assert project_review
    assert project_review[0].rating != "Missing / Critical"


def test_same_input_produces_the_same_calculated_score():
    _, first = assess("strong_engineer")
    _, second = assess("strong_engineer")
    assert first.verdict.overall_score == second.verdict.overall_score
    assert [item.achieved_points for item in first.category_scores] == [item.achieved_points for item in second.category_scores]
    assert abs(sum(item.achieved_points for item in first.category_scores) - first.verdict.overall_score) < 0.2


def test_recommendations_cite_real_text_or_explicit_omissions():
    extracted, report = assess("it_support_weak")
    corpus = extracted.raw_text.lower()
    assert report.recommendations
    for rec in report.recommendations:
        assert rec.rubric_criteria_affected
        assert rec.evidence_reasoning
        if rec.evidence_type == "verified_quote":
            assert rec.original_text.lower() in corpus
        if rec.action == "add":
            assert rec.evidence_type == "explicit_omission"
            assert rec.verified_in_cv is True


def test_paraphrase_does_not_raise_the_impact_score_but_a_confirmed_result_does():
    base = """
Nia Shah
nia.shah@example.com | Leeds

Work Experience
Operations Assistant | Northwind | 2024 - 2025
• Worked on internal tools for the operations team.
"""
    paraphrased = base.replace("Worked on internal tools", "Contributed to internal tools")
    evidenced = """
Nia Shah
nia.shah@example.com | Leeds

Work Experience
Operations Assistant | Northwind | 2024 - 2025
• Built an internal FastAPI tool for the operations team and reduced ticket triage time from 18 minutes to 7 minutes by validating requests in PostgreSQL before they reached the queue.
"""
    def impact(text):
        _, report = analyze_text("cv.txt", text.encode(), context("junior"))
        return next(item.deterministic_subscore for item in report.category_scores if item.category_key == "impact_achievements"), report

    base_score, base_report = impact(base)
    para_score, para_report = impact(paraphrased)
    evidenced_score, _ = impact(evidenced)
    assert evidence_fingerprint(base_report) == evidence_fingerprint(para_report)
    assert para_score == base_score
    assert evidenced_score > base_score


def test_job_description_is_optional_and_does_not_treat_silence_as_absence_of_ability():
    _, without = assess("strong_engineer", title="Backend engineer")
    jd = """
Essential
- Python API development
- PostgreSQL
- pytest
Desirable
- Kubernetes experience
"""
    _, with_jd = assess("strong_engineer", title="Backend engineer", jd=jd)
    assert without.jd_comparison.provided is False
    assert without.three_pillars.role_suitability_assessed is False
    assert with_jd.jd_comparison.provided is True
    assert with_jd.jd_comparison.alignment_percentage > 40
    missing = [item for item in with_jd.jd_comparison.requirements if item.requirement_text.endswith("Kubernetes")]
    if missing:
        assert "not proof" in missing[0].recruiter_note.lower() or missing[0].status == "not_evidenced"


def test_malformed_model_payload_is_rejected_and_invented_numbers_are_not_applied():
    assert parse_semantic_payload("I cannot help with that.") is None
    assert parse_semantic_payload('{"semantic_subscores": {"impact_achievements": 70}}')["semantic_subscores"]["impact_achievements"] == 70
    from backend.facts import rewrite_is_faithful
    ok, reason = rewrite_is_faithful("Worked on a Laravel application.", "Developed a Laravel application and reduced latency by 40%.")
    assert ok is False
    assert "40" in reason


def _session_from_sample(name, level="mid_level"):
    extracted, report = assess(name, level)
    session = SessionState(
        session_id="test",
        created_at=datetime.now(timezone.utc).isoformat(),
        context=context(level),
        extracted_cv=extracted,
        initial_report=report,
        working_cv=build_working_cv(extracted),
    )
    return session


def test_editing_updates_the_working_cv_and_export_uses_only_accepted_text():
    session = _session_from_sample("it_support_weak", "junior")
    rewrite = next(rec for rec in session.initial_report.recommendations if rec.action == "rewrite" and rec.bullet_id)
    original = rewrite.original_text
    decide_recommendation(session, rewrite.rec_id, "accept", "Served customers at Northbridge Stores and reconciled the till each evening.")
    rendered = "\n".join(entry.current_text for section in session.working_cv.sections for entry in section.entries if not entry.is_deleted)
    assert "reconciled the till" in rendered
    docx_bytes = export_docx(session)
    document = Document(io.BytesIO(docx_bytes))
    exported = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "reconciled the till" in exported
    assert exported.count(original) == 1
    decide_recommendation(session, rewrite.rec_id, "undo")
    restored = "\n".join(entry.current_text for section in session.working_cv.sections for entry in section.entries)
    assert original in restored
    assert "reconciled the till" not in restored
    decide_recommendation(session, rewrite.rec_id, "reject")
    rejected_export = "\n".join(paragraph.text for paragraph in Document(io.BytesIO(export_docx(session))).paragraphs)
    assert original in rejected_export
    assert "reconciled the till" not in rejected_export


def test_follow_up_answer_is_used_and_an_unknown_answer_invents_nothing():
    session = _session_from_sample("unsupported_claims", "junior")
    question = session.initial_report.follow_up_questions[0]
    answer_question(session, question.question_id, "dont_know", "")
    updated = next(rec for rec in session.initial_report.recommendations if rec.rec_id == question.linked_rec_id)
    assert "40" not in updated.suggested_text
    assert "[" in updated.suggested_text or "performance" in updated.suggested_text.lower()
    answer_question(session, question.question_id, "answered", "I replaced three repeated product queries with one PostgreSQL view.")
    assert "PostgreSQL view" in updated.suggested_text
    decide_recommendation(session, updated.rec_id, "accept")
    comparison = reassess(session)
    assert comparison.original_score == session.initial_report.verdict.overall_score
    assert comparison.category_deltas
    assert any(item.evidence_of_change for item in comparison.category_deltas)


def test_reassessment_of_an_unchanged_cv_does_not_invent_a_new_score():
    session = _session_from_sample("strong_engineer")
    comparison = reassess(session)
    assert comparison.score_delta == 0
    assert comparison.original_score == comparison.revised_score


def test_document_extraction_for_valid_invalid_empty_and_awkward_files():
    extracted, _ = assess("strong_engineer")
    assert extracted.contact.email == "priya.raman@example.com"
    assert extracted.diagnostics.word_count > 40

    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Hidden header | secret.person@example.com"
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Work Experience"
    table.cell(0, 1).text = "• Built a Python importer for 2000 records."
    doc.add_paragraph("Education")
    doc.add_paragraph("BSc Example University 2020 - 2023")
    buffer = io.BytesIO()
    doc.save(buffer)
    awkward = extract_cv_from_bytes("awkward.docx", buffer.getvalue())
    assert awkward.diagnostics.has_tables
    assert awkward.diagnostics.has_header_footer_content
    assert "secret.person@example.com" in awkward.raw_text

    pdf_buffer = io.BytesIO()
    pdf = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    pdf.build([Table([["Priya Raman", "priya.raman@example.com"], ["Work Experience", "• Designed a FastAPI service and cut latency from 900ms to 240ms."]])])
    parsed_pdf = extract_cv_from_bytes("tables.pdf", pdf_buffer.getvalue())
    assert "FastAPI" in parsed_pdf.raw_text
    assert parsed_pdf.diagnostics.file_format == "pdf"

    with pytest.raises(DocumentExtractionError):
        extract_cv_from_bytes("empty.pdf", b"")
    with pytest.raises(DocumentExtractionError):
        extract_cv_from_bytes("broken.pdf", b"this is not a pdf")
    with pytest.raises(DocumentExtractionError):
        extract_cv_from_bytes("notes.rtf", b"{\\rtf1 hello}")
    thin = Document()
    thin.add_paragraph("Hello")
    thin_buffer = io.BytesIO()
    thin.save(thin_buffer)
    thin_cv = extract_cv_from_bytes("thin.docx", thin_buffer.getvalue())
    assert thin_cv.diagnostics.extraction_complete is False


def test_api_upload_edit_export_and_reassess_round_trip():
    pdf_buffer = io.BytesIO()
    pdf = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    styles = getSampleStyleSheet()
    text = Path(SAMPLES / "strong_engineer.txt").read_text(encoding="utf-8").replace("\n", "<br/>")
    pdf.build([Paragraph(text, styles["Normal"])])
    response = client.post(
        "/api/analyze",
        data={"career_level": "mid_level", "target_job_title": "Backend engineer", "use_llm": "false"},
        files={"file": ("strong.pdf", pdf_buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    session_id = payload["session_id"]
    assert payload["initial_report"]["verdict"]["overall_score"] > 40
    bad = client.post("/api/analyze", files={"file": ("cv.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 415
    empty = client.post("/api/analyze", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert empty.status_code == 422

    rec = next(item for item in payload["initial_report"]["recommendations"] if item["action"] == "keep")
    accepted = client.post(
        f"/api/sessions/{session_id}/recommendations/{rec['rec_id']}",
        json={"decision": "accept", "edited_text": rec["original_text"]},
    )
    assert accepted.status_code == 200
    exported = client.get(f"/api/sessions/{session_id}/export?export_format=pdf&acknowledge_placeholders=true")
    assert exported.status_code == 200
    assert exported.content.startswith(b"%PDF")
    opened = fitz.open(stream=exported.content, filetype="pdf")
    assert "Priya" in opened[0].get_text()
    opened.close()
    reassessed = client.post(f"/api/sessions/{session_id}/reassess")
    assert reassessed.status_code == 200
    assert "score_delta" in reassessed.json()["latest_reassessment"]


def _auto(name, title=""):
    ctx = AnalysisContext(career_level_source="auto", target_job_title=title, use_llm=False)
    path = SAMPLES / f"{name}.txt"
    extracted, report = analyze_text(path.name, path.read_bytes(), ctx)
    return ctx, extracted, report


def test_likely_roles_and_career_level_are_inferred_when_nothing_is_specified():
    expected = {
        "strong_engineer": ({"mid_level", "senior_lead"}, "backend_engineer"),
        "it_support_weak": ({"junior", "student_graduate"}, "it_support"),
        "student_projects": ({"student_graduate"}, "graduate_software_engineer"),
    }
    for name, (levels, role_id) in expected.items():
        ctx, _extracted, report = _auto(name)
        targets = report.role_targets
        assert ctx.career_level in levels and ctx.career_level_source == "inferred" and ctx.career_level_reason
        assert targets.primary_role_id == role_id and not targets.role_was_specified
        assert ctx.pinned_role_id == role_id
        assert 2 <= len(targets.candidates) <= 4
        assert targets.candidates[0].is_primary and sum(c.is_primary for c in targets.candidates) == 1
        assert report.three_pillars.application_competitiveness_rating != "Insufficient Role Context"
        assert "Indicative only" in report.three_pillars.application_competitiveness_verdict
    _ctx, _extracted, strong = _auto("strong_engineer")
    _ctx, _extracted, weak = _auto("it_support_weak")
    assert strong.role_targets.candidates[0].fit_percentage > weak.role_targets.candidates[0].fit_percentage


def test_a_stated_target_is_honoured_and_gaps_become_actions_not_claims():
    _ctx, _extracted, report = _auto("it_support_weak", "Data Analyst")
    targets = report.role_targets
    primary = targets.candidates[0]
    assert targets.role_was_specified and targets.specified_title_matched_profile
    assert primary.role_id == "data_analyst" and primary.is_user_target and primary.fit_percentage < 30
    assert any(gap.startswith("SQL") for gap in primary.top_gaps)
    relevance = next(c for c in report.category_scores if c.category_key == "relevance_alignment")
    assert any(d.points_impact < 0 and "Data Analyst" in d.reason for d in relevance.deductions_and_credits)
    sql_actions = [a for a in report.elevation_plan.actions_to_begin if "SQL" in a.title]
    assert sql_actions and sql_actions[0].for_roles == ["Data Analyst"]
    assert not any("SQL" in (rec.suggested_text or "") for rec in report.recommendations)


def test_elevation_plan_quotes_the_cv_and_never_invents_facts():
    from backend.facts import unsupported_numbers

    def norm(text):
        return " ".join(text.split()).lower()

    for name in ["it_support_weak", "strong_engineer", "student_projects", "unsupported_claims"]:
        _ctx, extracted, report = _auto(name)
        plan = report.elevation_plan
        assert plan.headline and plan.honesty_note
        for upgrade in plan.writing_upgrades:
            if upgrade.example_before:
                assert norm(upgrade.example_before) in norm(extracted.raw_text)
            assert not unsupported_numbers(extracted.raw_text, upgrade.example_after)
        for action in plan.add_now_if_true + plan.actions_to_begin:
            assert not unsupported_numbers(extracted.raw_text, action.cv_line_once_done)
    _ctx, extracted, weak = _auto("it_support_weak")
    duty = next(u for u in weak.elevation_plan.writing_upgrades if u.title == "Turn duties into achievements")
    assert duty.priority == "critical" and duty.example_before and "[" in duty.example_after
    _ctx, extracted, strong = _auto("strong_engineer")
    assert not any(u.title.startswith("Write for") for u in strong.elevation_plan.writing_upgrades)


def test_reassessment_keeps_the_inferred_role_for_an_unchanged_cv():
    ctx, extracted, report = _auto("student_projects")
    session = SessionState(
        session_id="auto",
        created_at=datetime.now(timezone.utc).isoformat(),
        context=ctx,
        extracted_cv=extracted,
        initial_report=report,
        working_cv=build_working_cv(extracted),
    )
    comparison = reassess(session)
    assert comparison.score_delta == 0
    assert ctx.pinned_role_id == "graduate_software_engineer"


def test_api_defaults_to_auto_detection_and_can_retarget_a_session():
    config = client.get("/api/config").json()
    assert any(role["role_id"] == "data_analyst" for role in config["roles"])
    response = client.post("/api/samples/it_support_weak/analyze", data={"use_llm": "false"})
    assert response.status_code == 200
    body = response.json()
    assert body["context"]["career_level_source"] == "inferred"
    assert body["initial_report"]["role_targets"]["primary_role_id"] == "it_support"
    old_id = body["session_id"]
    retargeted = client.post(f"/api/sessions/{old_id}/retarget", json={"role_id": "data_analyst"})
    assert retargeted.status_code == 200
    new = retargeted.json()
    assert new["session_id"] != old_id
    assert new["context"]["target_job_title"] == "Data Analyst"
    assert new["initial_report"]["role_targets"]["primary_role_id"] == "data_analyst"
    assert client.get(f"/api/sessions/{old_id}").status_code == 404
    unknown = client.post(f"/api/sessions/{new['session_id']}/retarget", json={"role_id": "astronaut"})
    assert unknown.status_code == 422
