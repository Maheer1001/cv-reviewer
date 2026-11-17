import re
from datetime import datetime, timezone
from typing import List, Optional

from backend.pipeline import analyze_cv, evidence_fingerprint
from backend.report_builder import _faithful_rewrite, _strip_weak_opening
from backend.schemas import (
    CategoryDelta,
    ChangeHistoryEvent,
    ExtractedCV,
    RecommendationItem,
    ReassessmentComparison,
    SessionState,
    WorkingCV,
    WorkingEntry,
    WorkingSection,
)


_PLACEHOLDER = re.compile(r"\[[^\]\n]{2,120}\]")
_INSTRUCTIONAL = re.compile(r"^(?:Add:|Add the skills|Only if this is true|Move the Work Experience)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _unresolved(text: str) -> bool:
    return bool(_PLACEHOLDER.search(text or "") or _INSTRUCTIONAL.search((text or "").strip()))


def build_working_cv(extracted: ExtractedCV) -> WorkingCV:
    sections: List[WorkingSection] = []
    for section in extracted.sections:
        entries = [
            WorkingEntry(
                item_id=item.bullet_id,
                original_text=item.text,
                current_text=item.text,
                is_bullet=item.is_bullet,
            )
            for item in section.items
        ]
        sections.append(
            WorkingSection(
                section_id=section.section_id,
                title=section.title,
                normalized_type=section.normalized_type,
                entries=entries,
            )
        )
    working = WorkingCV(
        contact=extracted.contact.model_copy(deep=True),
        sections=sections,
        original_section_ids=[section.section_id for section in sections],
    )
    return working


def render_working_cv(working: WorkingCV) -> str:
    """Render the working CV as linear text. Contact lines are not repeated outside their section."""
    lines: List[str] = []
    for section in working.sections:
        visible = [entry for entry in section.entries if not entry.is_deleted]
        if not visible:
            continue
        if section.normalized_type != "contact":
            lines.append(section.title)
        for entry in visible:
            prefix = "• " if entry.is_bullet else ""
            lines.append(prefix + entry.current_text)
    return "\n".join(lines).strip() + "\n"


def placeholders_in(working: WorkingCV) -> List[str]:
    found = []
    for section in working.sections:
        for entry in section.entries:
            if entry.is_deleted:
                continue
            if _unresolved(entry.current_text):
                found.append(f"{section.title}: {entry.current_text[:180]}")
    working.unresolved_placeholders = found
    return found


def _find_rec(session: SessionState, rec_id: str) -> RecommendationItem:
    for rec in session.initial_report.recommendations:
        if rec.rec_id == rec_id:
            return rec
    raise KeyError(rec_id)


def _find_entry(working: WorkingCV, item_id: str) -> Optional[tuple[WorkingSection, WorkingEntry]]:
    for section in working.sections:
        for entry in section.entries:
            if entry.item_id == item_id:
                return section, entry
    return None


def _history(working: WorkingCV, rec_id: Optional[str], action: str, section: str, before: str, after: str) -> None:
    working.change_history.append(
        ChangeHistoryEvent(
            event_id=f"evt_{len(working.change_history) + 1}",
            timestamp=_now(),
            rec_id=rec_id,
            action_taken=action,
            section_name=section,
            before_text=before,
            after_text=after,
        )
    )


def _revert_rec(working: WorkingCV, rec: RecommendationItem) -> None:
    if rec.action == "add":
        for section in working.sections:
            section.entries = [entry for entry in section.entries if entry.modified_by_rec_id != rec.rec_id]
        return
    if rec.action == "move":
        order = {section_id: index for index, section_id in enumerate(working.original_section_ids)}
        working.sections.sort(key=lambda section: order.get(section.section_id, 1000))
        return
    found = _find_entry(working, rec.bullet_id or "")
    if not found:
        return
    _section, entry = found
    entry.current_text = entry.original_text
    entry.is_deleted = False
    entry.modified_by_rec_id = None
    entry.has_unverified_placeholder = _unresolved(entry.original_text)


def _apply_to_working(working: WorkingCV, rec: RecommendationItem, text: str) -> None:
    if rec.action == "add":
        section = next((item for item in working.sections if item.title == rec.section_name), None)
        if section is None:
            section = WorkingSection(
                section_id=f"sec_added_{rec.rec_id}",
                title=rec.section_name or "Additional",
                normalized_type="additional",
                entries=[],
            )
            working.sections.append(section)
        section.entries.append(
            WorkingEntry(
                item_id=f"added_{rec.rec_id}",
                original_text="",
                current_text=text,
                is_bullet=True,
                is_added=True,
                modified_by_rec_id=rec.rec_id,
                has_unverified_placeholder=_unresolved(text),
            )
        )
        _history(working, rec.rec_id, "add", section.title, "", text)
        return

    if rec.action == "move":
        experience = [section for section in working.sections if section.normalized_type == "experience"]
        education = [section for section in working.sections if section.normalized_type == "education"]
        if experience and education:
            exp = experience[0]
            edu = education[0]
            others = [section for section in working.sections if section.section_id not in (exp.section_id, edu.section_id)]
            leading = [section for section in others if section.normalized_type in ("contact", "summary")]
            trailing = [section for section in others if section not in leading]
            working.sections = leading + [exp, edu] + trailing
            _history(working, rec.rec_id, "move", exp.title, edu.title, "Work Experience placed before Education")
        return

    found = _find_entry(working, rec.bullet_id or "")
    if not found:
        return
    section, entry = found
    before = entry.current_text
    if rec.action == "cut" and (
        not text.strip() or text.strip() == (rec.suggested_text or "").strip() and rec.cut_handling == "remove_entirely"
    ):
        entry.is_deleted = True
        entry.modified_by_rec_id = rec.rec_id
        _history(working, rec.rec_id, "cut", section.title, before, "")
        return
    entry.current_text = text or entry.original_text
    entry.is_deleted = False
    entry.modified_by_rec_id = rec.rec_id
    entry.has_unverified_placeholder = _unresolved(entry.current_text)
    _history(working, rec.rec_id, rec.action, section.title, before, entry.current_text)


def refresh_counts(session: SessionState) -> None:
    recs = session.initial_report.recommendations
    working = session.working_cv
    working.accepted_count = sum(1 for rec in recs if rec.status == "accepted")
    working.rejected_count = sum(1 for rec in recs if rec.status == "rejected")
    working.pending_count = sum(1 for rec in recs if rec.status == "pending")
    working.unresolved_count = sum(1 for rec in recs if rec.status == "unresolved")
    placeholders_in(working)


def decide_recommendation(
    session: SessionState,
    rec_id: str,
    decision: str,
    edited_text: Optional[str] = None,
) -> RecommendationItem:
    rec = _find_rec(session, rec_id)
    if decision == "edit":
        rec.user_edited_text = (edited_text or "").strip()
        if rec.status == "accepted":
            _apply_to_working(session.working_cv, rec, rec.user_edited_text)
        refresh_counts(session)
        return rec
    if decision == "alternative":
        source = rec.original_text or rec.suggested_text
        rec.alternative_text = _strip_weak_opening(source)
        if rec.alternative_text == rec.suggested_text:
            words = source.split()
            rec.alternative_text = " ".join(words[:24]).rstrip(".,;") + "."
        refresh_counts(session)
        return rec
    if decision in ("reject", "undo"):
        if rec.status == "accepted":
            _revert_rec(session.working_cv, rec)
        rec.status = "rejected" if decision == "reject" else "pending"
        refresh_counts(session)
        return rec
    if decision == "unresolved":
        rec.status = "unresolved"
        refresh_counts(session)
        return rec
    if decision == "accept":
        text = (edited_text or rec.user_edited_text or rec.suggested_text or rec.original_text).strip()
        if rec.action == "keep":
            text = rec.original_text
        _apply_to_working(session.working_cv, rec, text)
        rec.status = "accepted"
        if edited_text:
            rec.user_edited_text = edited_text.strip()
        refresh_counts(session)
        return rec
    raise ValueError(f"Unsupported decision '{decision}'.")


def answer_question(session: SessionState, question_id: str, resolution: str, answer: str) -> SessionState:
    question = next((item for item in session.initial_report.follow_up_questions if item.question_id == question_id), None)
    if question is None:
        raise KeyError(question_id)
    question.resolution_type = resolution  # type: ignore[assignment]
    question.user_answer = answer.strip()
    rec = next((item for item in session.initial_report.recommendations if item.rec_id == question.linked_rec_id), None)
    original = question.original_excerpt
    if resolution == "answered" and answer.strip():
        base = _strip_weak_opening(original)
        base = re.sub(r"\s*—\s*\[[^\]]+\]\.?$", "", base).strip().rstrip(".")
        synthesised = f"{base}. {answer.strip().rstrip('.')}."
        question.synthesized_rewrite = synthesised
        if rec:
            rec.suggested_text = synthesised
            rec.missing_info_required = None
            rec.what_changed = "Incorporated only the answer you confirmed. No result was added beyond that answer."
            rec.source_stage = "hybrid"
    elif resolution in ("dont_know", "confidential", "use_existing", "skipped"):
        rewritten, why, missing = _faithful_rewrite(original, "tier_1_responsibility_only")
        question.synthesized_rewrite = rewritten
        if rec and resolution != "skipped":
            rec.suggested_text = rewritten
            rec.missing_info_required = missing
            rec.why_stronger = why
            rec.what_changed = "No new fact was available, so the bullet stays within the original evidence."
    refresh_counts(session)
    return session


def _explain_delta(old, new) -> str:
    parts = []
    if old.deterministic_subscore != new.deterministic_subscore:
        parts.append(
            f"Deterministic rating moved from {old.deterministic_subscore} to {new.deterministic_subscore}."
        )
        old_reasons = {item.reason for item in old.deductions_and_credits}
        new_reasons = {item.reason for item in new.deductions_and_credits}
        removed = [reason for reason in old_reasons - new_reasons][:2]
        added = [reason for reason in new_reasons - old_reasons][:2]
        if removed:
            parts.append("No longer triggered: " + "; ".join(removed) + ".")
        if added:
            parts.append("Newly triggered: " + "; ".join(added) + ".")
    else:
        parts.append("The deterministic checks for this category did not change.")
    if old.semantic_subscore != new.semantic_subscore:
        parts.append(
            f"Semantic subscore moved from {old.semantic_subscore} to {new.semantic_subscore}."
        )
    elif old.semantic_subscore is not None:
        parts.append("The semantic subscore was held constant.")
    return " ".join(parts)


def reassess(session: SessionState) -> ReassessmentComparison:
    rendered = render_working_cv(session.working_cv)
    from backend.extractor import extract_cv_from_bytes

    revised_cv = extract_cv_from_bytes("revised-working-cv.txt", rendered.encode("utf-8"))
    context = session.context.model_copy(deep=True)
    probe = context.model_copy(deep=True)
    probe.use_llm = False
    draft = analyze_cv(revised_cv, probe)
    old_fingerprint = evidence_fingerprint(session.initial_report)
    new_fingerprint = evidence_fingerprint(draft)
    reused = {
        item.category_key: item.semantic_subscore
        for item in session.initial_report.category_scores
        if item.semantic_subscore is not None
    }
    if new_fingerprint == old_fingerprint:
        revised = analyze_cv(revised_cv, probe, semantic_subscores=reused or None)
        revised.validation_notes.append(
            "The evidence fingerprint matched the original assessment, so semantic subscores were reused. "
            "Paraphrase without a change in evidence tier, duplication, unsupported skills, or unanchored claims does not move the rubric."
        )
    else:
        context_for_refresh = session.context.model_copy(deep=True)
        revised = analyze_cv(revised_cv, context_for_refresh)
        revised.validation_notes.append(
            "The evidence fingerprint changed, so the rubric was recalculated from the revised text."
        )

    rejected = {
        (rec.action, (rec.original_text or "")[:180].lower())
        for rec in session.initial_report.recommendations
        if rec.status == "rejected"
    }
    revised.recommendations = [
        rec
        for rec in revised.recommendations
        if (rec.action, (rec.original_text or "")[:180].lower()) not in rejected
    ]
    if session.initial_report.verdict.analysis_engine_used.startswith("Deterministic") and any(
        issue.issue_type == "verified_document_issue" and "column" in issue.title.lower()
        for issue in session.extracted_cv.diagnostics.ats_issues
    ):
        revised.validation_notes.append(
            "The working copy is linear text. A higher ATS figure here reflects that generated document, not a repair of the original uploaded layout."
        )

    deltas: List[CategoryDelta] = []
    improvements = []
    new_problems = []
    for old in session.initial_report.category_scores:
        new = next(item for item in revised.category_scores if item.category_key == old.category_key)
        deltas.append(
            CategoryDelta(
                category_key=old.category_key,
                category_name=old.category_name,
                original_points=old.achieved_points,
                revised_points=new.achieved_points,
                max_points=new.max_points,
                delta_points=round(new.achieved_points - old.achieved_points, 1),
                original_raw=old.raw_rating_out_of_100,
                revised_raw=new.raw_rating_out_of_100,
                evidence_of_change=_explain_delta(old, new),
            )
        )
        old_negative = {item.reason for item in old.deductions_and_credits if item.points_impact < 0}
        new_negative = {item.reason for item in new.deductions_and_credits if item.points_impact < 0}
        improvements.extend(f"Fixed: {reason}" for reason in sorted(old_negative - new_negative)[:2])
        new_problems.extend(sorted(new_negative - old_negative)[:2])

    delta = round(revised.verdict.overall_score - session.initial_report.verdict.overall_score, 1)
    if abs(delta) < 0.6:
        summary = "The revised CV receives the same rubric score. The edit did not change the checked evidence."
    elif delta > 0:
        summary = "The score rose where a checked defect was removed or stronger evidence was added. Wording alone is not treated as improvement."
    else:
        summary = "The score fell because the revision removed evidence or triggered a new check."
    rejected_open = [
        rec.original_text or rec.what_changed
        for rec in session.initial_report.recommendations
        if rec.status == "rejected" and rec.priority in ("critical", "high")
    ]
    unresolved = [
        question.primary_question + " — " + question.original_excerpt[:80]
        for question in session.initial_report.follow_up_questions
        if question.resolution_type == "unanswered"
    ]
    unresolved.extend(placeholders_in(session.working_cv))
    comparison = ReassessmentComparison(
        original_score=session.initial_report.verdict.overall_score,
        revised_score=revised.verdict.overall_score,
        score_delta=delta,
        reassessment_verdict=summary,
        category_deltas=deltas,
        improvements_verified=improvements[:8],
        remaining_weaknesses=[item.exact_problem for item in revised.top_weaknesses],
        rejected_worth_reconsidering=rejected_open[:6],
        unresolved_questions_or_missing_info=unresolved[:8],
        new_problems_introduced=new_problems[:8],
        revised_report=revised,
    )
    session.latest_reassessment = comparison
    return comparison
