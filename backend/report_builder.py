import re
from typing import Dict, List, Optional

from backend.deterministic_analyzer import (
    WEAK_OPENING_PATTERNS,
    compute_deterministic_category_baselines,
    run_deterministic_cv_audit,
    run_skills_credibility_audit,
)
from backend.elevation import build_elevation_plan
from backend.jd_analyzer import analyze_job_description_alignment
from backend.role_inference import describe_level, infer_role_targets, primary_target, role_fit_for_scoring
from backend.schemas import (
    AnalysisContext,
    CVAnalysisReport,
    DeterministicCVAudit,
    DimensionEvaluation,
    ExtractedCV,
    FollowUpQuestion,
    JDComparisonResult,
    OverallVerdict,
    PrioritisedAction,
    RecommendationItem,
    SectionReview,
    SkillsCredibilityAudit,
    ThreePillarAssessment,
    TopWeakness,
)
from backend.scoring import CATEGORY_METADATA, compute_category_scores


_TIER_POINTS = {
    "tier_0_generic": 2,
    "tier_1_responsibility_only": 4,
    "tier_2_technical_detail": 6,
    "tier_3_concrete_evidence": 8,
    "tier_4_verified_outcome": 9,
}

_FIX_BY_CATEGORY = {
    "relevance_alignment": "Lead with the experience closest to the target role and show its core requirements in real bullets, not only in the skills list.",
    "impact_achievements": "Rewrite the cited bullets as action, method and observed result. Add a number only if you can verify it; otherwise state the scale or the before-and-after.",
    "experience_project_quality": "For each role or project, name what you built or ran, your part in it, the tools used and what happened as a result.",
    "skills_credibility": "Show each listed skill in an experience or project bullet where you actually used it, or remove it from the skills list.",
    "writing_clarity": "Open each bullet with a direct ownership verb, cut filler and buzzwords, and keep one idea per bullet.",
    "structure_readability": "Use standard headings, put your strongest section first, and keep the CV to one or two tightly edited pages.",
    "ats_compatibility": "Use a single-column layout with plain-text headings, and keep content out of tables, text boxes and images.",
}


def _fix_for(key: str, reason: str) -> str:
    lowered = reason.lower()
    if "contact" in lowered:
        return "Put your name, email address, phone number and town in plain text at the top, outside any header or text box."
    if "duplicat" in lowered:
        return "Merge the near-identical bullets into one stronger line, or cut the weaker copy."
    return _FIX_BY_CATEGORY.get(key, "Replace the cited text with confirmed contribution and outcome, or remove it if you cannot evidence it.")


def _strip_weak_opening(text: str) -> str:
    cleaned = text.strip()
    for _label, pattern in WEAK_OPENING_PATTERNS:
        updated = pattern.sub("", cleaned, count=1)
        if updated == cleaned:
            continue
        updated = updated.strip(" .:-")
        if updated:
            return updated[0].upper() + updated[1:]
    return cleaned


def _neutralise_unverified_claim(text: str) -> str:
    updated = re.sub(r"\bby\s+\d{1,3}\s*%", "by [measured change]", text, flags=re.I)
    updated = re.sub(
        r"\b(?:100%\s*(?:bug[\s-]?free|error[\s-]?free|uptime|accurate|accuracy)|zero\s+(?:bugs|defects|errors))",
        "[observed quality result you can defend]",
        updated,
        flags=re.I,
    )
    updated = re.sub(
        r"\b(?:improved\s+performance|increased\s+efficiency|made\s+it\s+faster|optimised\s+the\s+system)",
        "changed performance",
        updated,
        flags=re.I,
    )
    return updated


def _faithful_rewrite(text: str, tier: str) -> tuple[str, str, Optional[str]]:
    """Rewrite wording without adding achievements. Unknown facts stay in brackets."""
    base = _strip_weak_opening(text)
    missing = None
    if tier in ("tier_0_generic", "tier_1_responsibility_only", "tier_2_technical_detail"):
        missing = (
            "Your individual contribution, the method or tools you actually used, "
            "and the observed result. Include a number only if you can verify the baseline and the outcome."
        )
        if "[" not in base:
            base = base.rstrip(".") + " — [your specific contribution and the observed result]."
        what = "Removed the passive opening and marked the missing contribution and result instead of inventing them."
    else:
        what = "Tightened the wording while preserving the facts already in the CV."
    why = (
        "A recruiter can separate what you did from a generic duty statement, "
        "and can see which facts still need to be confirmed."
    )
    return base, f"{what} {why}", missing


def _condense(text: str) -> str:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]
    if len(sentences) <= 1:
        words = text.split()
        if len(words) <= 32:
            return text.strip()
        return " ".join(words[:32]).rstrip(".,;") + "."
    kept: List[str] = []
    count = 0
    for sentence in sentences:
        kept.append(sentence)
        count += len(sentence.split())
        if count >= 28:
            break
    return " ".join(kept)


def _badge_for_score(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Adequate"
    if score >= 40:
        return "Weak"
    return "Critical Defect"


def _section_reviews(extracted: ExtractedCV, audit: DeterministicCVAudit, skills: SkillsCredibilityAudit) -> List[SectionReview]:
    reviews: List[SectionReview] = []
    for section in extracted.sections:
        related = [item for item in audit.bullet_audits if item.section_name == section.title]
        if section.normalized_type == "contact":
            missing = extracted.contact.missing_critical_fields
            rating = "Strong" if not missing else "Weak" if len(missing) < 3 else "Missing / Critical"
            reviews.append(
                SectionReview(
                    section_id=section.section_id,
                    section_title=section.title,
                    normalized_type=section.normalized_type,
                    rating=rating,
                    score_out_of_10=9 if not missing else max(2, 8 - len(missing) * 2),
                    summary_verdict=(
                        "Contact details can be parsed from the document body."
                        if not missing
                        else "Missing or unparsable: " + ", ".join(missing) + "."
                    ),
                    strengths=[] if missing else ["Email or profile details were extracted from the document."],
                    weaknesses=[f"{field} was not found in extractable text." for field in missing],
                    key_recommendations=["Put contact details in the body of page one, not only in a header or footer."],
                )
            )
            continue
        if section.normalized_type == "skills":
            score = 8 if skills.claimed_skills and not skills.unsupported_skills else 4 if skills.unsupported_skills else 5
            reviews.append(
                SectionReview(
                    section_id=section.section_id,
                    section_title=section.title,
                    normalized_type=section.normalized_type,
                    rating="Strong" if score >= 8 else "Mixed" if score >= 5 else "Weak",
                    score_out_of_10=score,
                    summary_verdict=skills.recruiter_commentary,
                    strengths=[f"{len(skills.evidenced_skills)} listed or demonstrated {'skill is' if len(skills.evidenced_skills) == 1 else 'skills are'} backed by other sections."],
                    weaknesses=skills.overloaded_or_unsubstantiated_levels[:3],
                    key_recommendations=(
                        [f"Remove or evidence: {', '.join(skills.unsupported_skills[:6])}."]
                        if skills.unsupported_skills
                        else ["Keep the skills that your bullets already prove."]
                    ),
                )
            )
            continue
        if not related and section.normalized_type not in ("experience", "projects", "summary", "education"):
            continue
        if related:
            avg = sum(_TIER_POINTS[item.evidence_tier] for item in related) / len(related)
            score = max(1, min(10, int(round(avg))))
        else:
            score = 5
        rating = "Strong" if score >= 8 else "Mixed" if score >= 6 else "Weak"
        strengths = [item.text[:140] for item in related if item.evidence_tier in ("tier_3_concrete_evidence", "tier_4_verified_outcome")][:2]
        weaknesses = [f"{item.evidence_tier_label}: {item.text[:120]}" for item in related if item.evidence_tier in ("tier_0_generic", "tier_1_responsibility_only")][:3]
        reviews.append(
            SectionReview(
                section_id=section.section_id,
                section_title=section.title,
                normalized_type=section.normalized_type,
                rating=rating,
                score_out_of_10=score,
                summary_verdict=(
                    f"{len(related)} {'statement' if len(related) == 1 else 'statements'} reviewed. "
                    + (
                        "The stronger statements already show method and result."
                        if strengths
                        else "The section describes activity more often than it proves contribution."
                    )
                ),
                strengths=strengths,
                weaknesses=weaknesses,
                key_recommendations=["Preserve the evidenced statements and replace duty-only lines with confirmed contribution and outcome."],
            )
        )
    return reviews


def _recommendations(
    extracted: ExtractedCV,
    audit: DeterministicCVAudit,
    skills: SkillsCredibilityAudit,
    context: AnalysisContext,
    jd: JDComparisonResult,
) -> tuple[List[RecommendationItem], List[FollowUpQuestion]]:
    recs: List[RecommendationItem] = []
    questions: List[FollowUpQuestion] = []

    keeps = [item for item in audit.bullet_audits if item.evidence_tier in ("tier_3_concrete_evidence", "tier_4_verified_outcome") and not item.has_unanchored_claim and not item.duplicate_of_bullet_id]
    for item in keeps[:3]:
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="keep",
                priority="low",
                section_name=item.section_name,
                bullet_id=item.bullet_id,
                original_text=item.text,
                suggested_text=item.text,
                what_changed="No change. The statement already shows contribution with enough specificity to keep.",
                why_stronger=item.evidence_tier_reason,
                recruiter_benefit="Preserves evidence a recruiter can use without asking what you actually did.",
                rubric_criteria_affected=["Evidence of impact and achievements", "Experience and project quality"],
                evidence_reasoning=item.evidence_tier_label,
                evidence_type="verified_quote",
                source_stage="deterministic",
            )
        )

    duplicates = [item for item in audit.bullet_audits if item.duplicate_of_bullet_id]
    for item in duplicates[:3]:
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="cut",
                priority="high",
                section_name=item.section_name,
                bullet_id=item.bullet_id,
                original_text=item.text,
                suggested_text="",
                what_changed="Remove the repeated statement.",
                why_stronger="The same point is already made elsewhere, so this line spends space without adding evidence.",
                recruiter_benefit="The remaining version of the point is easier to find.",
                cut_handling="remove_entirely",
                value_lost_if_removed="Little, provided the earlier copy stays.",
                space_reallocation_advice="Use the space for a distinct contribution, decision, or result from the same role.",
                rubric_criteria_affected=["Writing quality and clarity", "Structure and readability"],
                evidence_reasoning=f"Near-duplicate of {item.duplicate_of_bullet_id}.",
                source_stage="deterministic",
            )
        )

    claims = [item for item in audit.bullet_audits if item.has_unanchored_claim]
    for item in claims[:4]:
        suggested = _neutralise_unverified_claim(item.text)
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="verify",
                priority="critical",
                section_name=item.section_name,
                bullet_id=item.bullet_id,
                original_text=item.text,
                suggested_text=suggested,
                what_changed="Replaced the unsupported figure or vague outcome with a visible gap.",
                why_stronger=item.unanchored_claim_reason or item.evidence_tier_reason,
                recruiter_benefit="Removes a claim that invites a sceptical recruiter to discount the surrounding evidence.",
                missing_info_required="The baseline, the result, and the change that produced it. If you do not have a measurement, describe the concrete change without a number.",
                rubric_criteria_affected=["Evidence of impact and achievements", "Technical or professional skills credibility"],
                evidence_reasoning=item.unanchored_claim_reason or "Unanchored claim.",
                source_stage="deterministic",
            )
        )

    weak = [
        item
        for item in audit.bullet_audits
        if not item.duplicate_of_bullet_id
        and not item.has_unanchored_claim
        and (item.evidence_tier in ("tier_0_generic", "tier_1_responsibility_only", "tier_2_technical_detail") or item.weak_verb_prefix or item.buzzwords_found)
    ]
    weak.sort(key=lambda item: (item.evidence_tier, 0 if item.weak_verb_prefix else 1))
    for item in weak[:8]:
        if item.buzzwords_found and item.evidence_tier == "tier_0_generic" and item.word_count < 22:
            recs.append(
                RecommendationItem(
                    rec_id="pending",
                    action="cut",
                    priority="high",
                    section_name=item.section_name,
                    bullet_id=item.bullet_id,
                    original_text=item.text,
                    suggested_text="",
                    what_changed="Remove the unsupported self-description.",
                    why_stronger="Words such as "
                    + ", ".join(item.buzzwords_found)
                    + " do not tell a recruiter what you can do.",
                    recruiter_benefit="Stops the profile competing with the evidence.",
                    cut_handling="remove_entirely",
                    value_lost_if_removed="No verifiable achievement is lost.",
                    space_reallocation_advice="Replace it with one evidenced outcome from a role or project.",
                    rubric_criteria_affected=["Writing quality and clarity"],
                    evidence_reasoning="Buzzwords without supporting detail: " + ", ".join(item.buzzwords_found),
                    source_stage="deterministic",
                )
            )
            continue
        suggested, why, missing = _faithful_rewrite(item.text, item.evidence_tier)
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="rewrite",
                priority="high" if item.evidence_tier in ("tier_0_generic", "tier_1_responsibility_only") else "medium",
                section_name=item.section_name,
                bullet_id=item.bullet_id,
                original_text=item.text,
                suggested_text=suggested,
                what_changed="Replaced a duty-style statement with a version that keeps known facts and marks unknown ones.",
                why_stronger=why,
                recruiter_benefit="Makes the gap explicit instead of sounding like an achievement that is not there.",
                missing_info_required=missing,
                rubric_criteria_affected=["Evidence of impact and achievements", "Writing quality and clarity"],
                evidence_reasoning=item.evidence_tier_reason,
                source_stage="deterministic",
            )
        )

    long_items = [item for item in audit.bullet_audits if item.is_overlong and not item.duplicate_of_bullet_id][:2]
    for item in long_items:
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="condense",
                priority="medium",
                section_name=item.section_name,
                bullet_id=item.bullet_id,
                original_text=item.text,
                suggested_text=_condense(item.text),
                what_changed="Shortened the statement by keeping the earlier factual clauses.",
                why_stronger="A recruiter scanning the page is more likely to absorb one direct point than a 40-word sentence.",
                recruiter_benefit="Improves scan speed without adding new claims.",
                rubric_criteria_affected=["Structure and readability", "Writing quality and clarity"],
                evidence_reasoning=f"{item.word_count} words.",
                source_stage="deterministic",
            )
        )

    if skills.unsupported_skills:
        skill_lines = [item for sec in extracted.sections if sec.normalized_type == "skills" for item in sec.items]
        target = next((item for item in skill_lines if any(skill.lower() in item.text.lower() for skill in skills.unsupported_skills)), None)
        if target:
            kept_parts = []
            for part in re.split(r"[,|•;/]", target.text):
                token = part.strip()
                if token and not any(skill.lower() in token.lower() for skill in skills.unsupported_skills):
                    kept_parts.append(token)
            recs.append(
                RecommendationItem(
                    rec_id="pending",
                    action="cut",
                    priority="high",
                    section_name=target.section_name,
                    bullet_id=target.bullet_id,
                    original_text=target.text,
                    suggested_text=", ".join(kept_parts),
                    what_changed="Removed skills that never appear in experience or projects.",
                    why_stronger="A skills list that includes unevidenced tools weakens the tools you have actually used.",
                    recruiter_benefit="The remaining list is easier to trust.",
                    cut_handling="shorten",
                    value_lost_if_removed="Only the unevidenced names: " + ", ".join(skills.unsupported_skills[:8]) + ".",
                    space_reallocation_advice="If you have used one of those tools, add a bullet that shows the work. Do not put the name back on its own.",
                    rubric_criteria_affected=["Technical or professional skills credibility"],
                    evidence_reasoning="No experience or project line supports these names.",
                    source_stage="deterministic",
                )
            )

    if skills.omitted_demonstrated_skills:
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="add",
                priority="medium",
                section_name="Technical Skills",
                original_text="",
                suggested_text="Add the skills already demonstrated elsewhere: " + ", ".join(skills.omitted_demonstrated_skills[:8]) + ".",
                what_changed="This does not add a new skill. It surfaces skills already evidenced in the CV.",
                why_stronger="A recruiter looking at the skills block currently misses abilities your projects or roles already show.",
                recruiter_benefit="Makes evidenced tools easier to scan.",
                is_essential=False,
                question_to_answer="Confirm that you want these evidenced tools listed in the skills section.",
                rubric_criteria_affected=["Technical or professional skills credibility", "Relevance and role alignment"],
                evidence_reasoning="Found in experience or project text and absent from the skills section.",
                evidence_type="explicit_omission",
                source_stage="deterministic",
            )
        )

    if extracted.contact.missing_critical_fields:
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="add",
                priority="critical",
                section_name="Contact & Header",
                original_text="",
                suggested_text="Add: " + ", ".join(extracted.contact.missing_critical_fields) + ".",
                what_changed="Identifies contact fields the parser could not find.",
                why_stronger="Without a reliable email or profile link, a recruiter cannot act on an otherwise acceptable CV.",
                recruiter_benefit="Makes the application usable.",
                is_essential=True,
                question_to_answer="What email address, phone number, and profile URL should appear at the top of the CV?",
                rubric_criteria_affected=["ATS compatibility", "Structure and readability"],
                evidence_reasoning="Contact extraction did not find: " + ", ".join(extracted.contact.missing_critical_fields) + ".",
                evidence_type="explicit_omission",
                source_stage="deterministic",
            )
        )

    section_types = [section.normalized_type for section in extracted.sections]
    if (
        context.career_level in ("mid_level", "senior_lead", "executive")
        and "education" in section_types
        and "experience" in section_types
        and section_types.index("education") < section_types.index("experience")
    ):
        education = next(section for section in extracted.sections if section.normalized_type == "education")
        anchor = education.items[0] if education.items else None
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="move",
                priority="medium",
                section_name=education.title,
                bullet_id=anchor.bullet_id if anchor else None,
                original_text=anchor.text if anchor else education.title,
                suggested_text="Move the Work Experience section above Education.",
                what_changed="Changes section order so recent evidence leads.",
                why_stronger="For this career stage, education is context. The work record is the decision material.",
                recruiter_benefit="The strongest evidence appears before the reader stops scanning.",
                target_destination="Immediately after the professional summary.",
                rubric_criteria_affected=["Structure and readability", "Relevance and role alignment"],
                evidence_reasoning="Education currently precedes Work Experience.",
                evidence_type="structural_observation" if anchor is None else "verified_quote",
                source_stage="deterministic",
            )
        )

    for gap in jd.genuine_experience_gaps[:2]:
        recs.append(
            RecommendationItem(
                rec_id="pending",
                action="add",
                priority="high",
                section_name="Target role",
                original_text="",
                suggested_text="Only if this is true: add one bullet showing where you met this requirement. Do not insert the keyword alone.",
                what_changed="Marks a job requirement the CV does not currently evidence.",
                why_stronger=gap,
                recruiter_benefit="Either supplies the missing evidence or stops the CV implying a fit it does not show.",
                is_essential=True,
                question_to_answer=gap,
                missing_info_required=gap,
                rubric_criteria_affected=["Relevance and role alignment"],
                evidence_reasoning="The job-description comparison found no supporting passage. This is an omission, not proof you lack the skill.",
                evidence_type="explicit_omission",
                source_stage="deterministic",
            )
        )

    question_sources = [rec for rec in recs if rec.action in ("rewrite", "verify") and rec.missing_info_required][:6]
    for index, rec in enumerate(question_sources, start=1):
        questions.append(
            FollowUpQuestion(
                question_id=f"q_{index}",
                linked_rec_id=rec.rec_id,
                bullet_id=rec.bullet_id,
                section_name=rec.section_name,
                original_excerpt=rec.original_text[:240],
                category=rec.action,
                priority=rec.priority,
                primary_question="What can you confirm about this work without guessing?",
                sub_questions=[
                    "What did you personally change or build?",
                    "What was the problem or constraint?",
                    "Which tools or methods did you use?",
                    "What result did you observe, and was it measured?",
                ],
                why_recruiter_asks=rec.missing_info_required or rec.why_stronger,
            )
        )
    return recs, questions


def _dimensions(
    extracted: ExtractedCV,
    audit: DeterministicCVAudit,
    skills: SkillsCredibilityAudit,
    scores: Dict[str, int],
    jd: JDComparisonResult,
) -> List[DimensionEvaluation]:
    sample_weak = next((item.text for item in audit.bullet_audits if item.evidence_tier in ("tier_0_generic", "tier_1_responsibility_only")), "")
    sample_strong = next((item.text for item in audit.bullet_audits if item.evidence_tier in ("tier_3_concrete_evidence", "tier_4_verified_outcome")), "")
    definitions = [
        ("A", "First impression", scores["structure_readability"], "The opening has to show who you are and why the rest of the page is worth reading.", [extracted.contact.name or "", sample_strong or sample_weak]),
        ("B", "Relevance and positioning", scores["relevance_alignment"], "Positioning is judged from what is easy to find, not from a claim that you are suitable.", [sample_strong or sample_weak]),
        ("C", "Experience and achievements", scores["impact_achievements"], "Duties are not achievements. The page is scored on evidence of what changed.", [sample_weak or sample_strong]),
        ("D", "Bullet-point quality", scores["writing_clarity"], "Each bullet should survive the question: what did you do, how, and what happened?", [sample_weak or sample_strong]),
        ("E", "Technical or professional credibility", scores["skills_credibility"], skills.recruiter_commentary, skills.unsupported_skills[:3] or [sample_strong]),
        ("F", "Projects", scores["experience_project_quality"], "Projects count when your contribution and the hard part are visible.", [sample_strong or "No project statement with a clear personal contribution was found."]),
        ("G", "Skills section", scores["skills_credibility"], skills.recruiter_commentary, skills.unsupported_skills[:4] or skills.claimed_skills[:4]),
        ("H", "Structure and readability", scores["structure_readability"], f"The document has {audit.total_words} words and {audit.total_bullets} reviewed statements.", [f"Average bullet length {audit.avg_bullet_words} words."]),
        ("I", "Credibility and potential concerns", scores["impact_achievements"], "Unsupported precision and empty praise are treated as credibility problems.", [item["text"] for item in audit.unanchored_claims_detected[:2]] or audit.buzzwords_detected[:3]),
        ("J", "ATS compatibility", scores["ats_compatibility"], "Only issues found in this file are called document defects. This is not an employer ATS test.", [issue.evidence for issue in extracted.diagnostics.ats_issues if issue.issue_type == "verified_document_issue"][:2]),
    ]
    dimensions: List[DimensionEvaluation] = []
    for code, title, score, assessment, quotes in definitions:
        clean_quotes = [quote for quote in quotes if quote]
        dimensions.append(
            DimensionEvaluation(
                dimension_code=code,
                dimension_title=title,
                verdict_badge=_badge_for_score(score),
                recruiter_assessment=assessment,
                evidence_quotes=clean_quotes[:3],
                specific_defects=clean_quotes[:2] if score < 70 else [],
                recruiter_inference=(
                    "A recruiter can defend this part of the CV from the text."
                    if score >= 75
                    else "A recruiter would ask for the missing proof, or move on."
                ),
            )
        )
    if not jd.provided:
        dimensions[1].recruiter_inference = "Role fit cannot be judged reliably because no job description was supplied."
    return dimensions


def _short_title(text: str, limit: int = 100) -> str:
    plain = re.sub(r"\s+\([^)]*\)", "", text.strip())
    head = re.split(r";\s|:\s|\s[—–-]\s", plain, maxsplit=1)[0].strip()
    if len(head) <= limit:
        return head
    return head[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _top_weaknesses(deductions: Dict[str, List], audit: DeterministicCVAudit) -> List[TopWeakness]:
    ranked = []
    for key, items in deductions.items():
        for item in items:
            if item.points_impact < 0:
                ranked.append((item.points_impact, key, item))
    ranked.sort(key=lambda row: row[0])
    weaknesses: List[TopWeakness] = []
    seen = set()
    for impact, key, item in ranked:
        title = _short_title(item.reason)
        if title in seen:
            continue
        seen.add(title)
        category = CATEGORY_METADATA[key]["name"]
        weaknesses.append(
            TopWeakness(
                rank=len(weaknesses) + 1,
                problem_title=title,
                exact_problem=item.reason,
                where_it_appears=item.evidence_ref or category,
                recruiter_impact=f"This is scored under {category}. A recruiter treats it as missing or unreliable evidence, not as a stylistic quibble.",
                how_to_address=_fix_for(key, item.reason),
                expected_impact=f"It currently changes the {category} rating by {item.points_impact} points before weighting. Fixing the evidence can remove that deduction; a paraphrase will not.",
            )
        )
        if len(weaknesses) == 5:
            break
    if not weaknesses:
        weaknesses.append(
            TopWeakness(
                rank=1,
                problem_title="No major deterministic defect dominated the rubric",
                exact_problem=f"Reviewed {audit.total_bullets} statements. The remaining limits are qualitative and may need the semantic pass.",
                where_it_appears="Across the CV",
                recruiter_impact="The document may still be ordinary for the role even if the structural checks pass.",
                how_to_address="Check the preserved bullets and confirm that the strongest evidence is the first thing a recruiter sees.",
                expected_impact="Further gains require better evidence, not another wording pass.",
            )
        )
    return weaknesses


def _actions(weaknesses: List[TopWeakness]) -> List[PrioritisedAction]:
    actions = []
    for index, weakness in enumerate(weaknesses[:5], start=1):
        priority = "critical" if index == 1 else "high" if index <= 3 else "medium"
        actions.append(
            PrioritisedAction(
                step_number=index,
                priority=priority,
                action_title=weakness.problem_title,
                rationale=weakness.recruiter_impact,
                target_area=weakness.where_it_appears,
                expected_score_lift=weakness.expected_impact,
            )
        )
    return actions


def _competitiveness(score: float, jd: JDComparisonResult, has_role: bool, inferred_role: str = "") -> tuple[str, str]:
    if not has_role and not jd.provided and not inferred_role:
        return (
            "Insufficient Role Context",
            "No target role or job description was supplied, so competitiveness against a vacancy cannot be assessed. The score below is document quality only.",
        )
    if jd.provided and jd.alignment_percentage < 45:
        return (
            "Uncompetitive in Current Form",
            "Against the supplied job description, too many essential requirements have no supporting passage. This is not a comparison with other applicants.",
        )
    if score >= 80:
        label = "Highly Competitive"
    elif score >= 65:
        label = "Moderately Competitive"
    elif score >= 48:
        label = "Borderline / At Risk of Rejection"
    else:
        label = "Uncompetitive in Current Form"
    basis = ""
    if not has_role and not jd.provided:
        basis = (
            f" Indicative only: no target or job description was supplied, so this is measured against {inferred_role}, "
            "the role your CV most resembles."
        )
    return (
        label,
        f"'{label}' describes how compelling the available evidence looks against this rubric. It is not an estimate of interview probability and it does not account for the actual applicant pool.{basis}",
    )


def assemble_report(
    extracted_cv: ExtractedCV,
    context: AnalysisContext,
    semantic_subscores: Optional[Dict[str, int]] = None,
    semantic_narrative: Optional[Dict[str, str]] = None,
    engine_name: str = "Deterministic evidence-tier rubric",
    model_identifier: str = "local-rules-v1",
) -> CVAnalysisReport:
    audit = extracted_cv.deterministic_audit or run_deterministic_cv_audit(extracted_cv)
    skills = run_skills_credibility_audit(extracted_cv)
    jd = analyze_job_description_alignment(extracted_cv, context)
    targets = infer_role_targets(extracted_cv, context, audit)
    primary = primary_target(targets)
    baselines, deductions, evidence, weaknesses, improvements, uncertainty = compute_deterministic_category_baselines(
        extracted_cv,
        audit,
        skills,
        context,
        role_fit=role_fit_for_scoring(targets),
        jd_alignment=jd.alignment_percentage if jd.provided else None,
    )
    if jd.provided:
        evidence["relevance_alignment"].append(jd.application_verdict[:240])
        if jd.alignment_percentage < 50:
            weaknesses["relevance_alignment"].append(
                f"Job-description evidence alignment is {jd.alignment_percentage}% after weighting essential requirements more heavily."
            )
    category_scores, total = compute_category_scores(
        baselines,
        context.weights,
        evidence,
        weaknesses,
        improvements,
        deductions,
        uncertainty,
        semantic_subscores,
    )
    raw_by_key = {item.category_key: item.raw_rating_out_of_100 for item in category_scores}
    recommendations, questions = _recommendations(extracted_cv, audit, skills, context, jd)
    top = _top_weaknesses(deductions, audit)
    inferred_role = primary.title if primary and primary.confidence != "low" else ""
    rating, rating_text = _competitiveness(total, jd, targets.role_was_specified, inferred_role)
    elevation = build_elevation_plan(extracted_cv, audit, skills, context, targets, recommendations)
    narrative = semantic_narrative or {}
    strongest = narrative.get("strongest_aspect") or (
        next((item.text[:180] for item in audit.bullet_audits if item.evidence_tier == "tier_4_verified_outcome"), "")
        or "No statement currently combines a specific action, method, and credible result."
    )
    biggest = narrative.get("biggest_weakness") or top[0].exact_problem
    if total >= 75:
        opening = "The CV contains enough specific evidence to survive a sceptical first read, with defects that are real but local."
    elif total >= 55:
        opening = "The CV is readable, but a demanding recruiter still has to guess what you personally achieved."
    else:
        opening = "In its current form the CV describes attendance and intent more often than it proves capability."
    verdict = narrative.get("blunt_verdict") or (
        f"{opening} The largest evidenced problem is: {biggest}"
    )
    limitations = [
        "The score is a weighted rubric result. It is not a prediction of an interview or an offer, and it has not been calibrated on a hiring dataset.",
        "The same weakness is assigned to one primary category so it is not deducted again under a second heading.",
        "Rule-based evidence tiers judge structure of proof (action, method, scope, result). They do not fully judge whether a project was a tutorial or production work; that limit is stated where the semantic model is not used.",
    ]
    if not jd.provided:
        limitations.append(
            "No job description was supplied, so suitability for a specific vacancy is not assessed. "
            "Role targets are measured against typical requirements and are indicative only."
        )
    if context.career_level_source == "inferred":
        limitations.append(
            f"Career level was inferred as {describe_level(context.career_level)}. {context.career_level_reason} "
            "Set it explicitly if that is wrong; it changes how the CV is judged."
        )
    if extracted_cv.diagnostics.extraction_warnings:
        limitations.extend(extracted_cv.diagnostics.extraction_warnings)
    if semantic_subscores is None:
        limitations.append(
            "No semantic-model subscores were applied. Qualitative nuance beyond the evidence-tier rules is therefore uncertain rather than scored."
        )
    stage = {
        "student_graduate": "Student and graduate CVs are judged on projects, placements, and evidenced learning, not on years of employment. That does not turn a vague project into a strong one.",
        "career_changer": "Transferable evidence is credited when the CV shows the work. A change of field is not itself a defect or a mitigating excuse for missing proof.",
        "junior": "Junior CVs are not failed for lacking senior scope. They are failed when the available work is described as duties only.",
        "mid_level": "At this stage a recruiter expects ownership, judgement, and results, not a list of responsibilities.",
        "senior_lead": "Senior CVs are judged on scope, decisions, and outcomes. Tool lists do not substitute for that.",
        "executive": "Executive CVs are judged on organisational outcomes and decisions. Operational task lists are supporting detail.",
    }[context.career_level]
    report = CVAnalysisReport(
        verdict=OverallVerdict(
            overall_score=total,
            blunt_recruiter_verdict=verdict,
            career_stage_calibration_note=stage,
            strongest_aspect=strongest,
            biggest_weakness=biggest,
            competitiveness_summary=rating_text,
            important_limitations_and_uncertainties=limitations,
            analysis_engine_used=engine_name,
            model_identifier=model_identifier,
        ),
        three_pillars=ThreePillarAssessment(
            general_cv_quality_score=int(round(total)),
            general_cv_quality_verdict=opening,
            role_suitability_assessed=jd.provided,
            role_suitability_score=jd.alignment_percentage if jd.provided else None,
            role_suitability_verdict=jd.application_verdict + (
                f" Indicative fit against typical {primary.title} requirements: {primary.fit_percentage}% (see Role targets)."
                if primary and not jd.provided
                else ""
            ),
            application_competitiveness_rating=rating,  # type: ignore[arg-type]
            application_competitiveness_verdict=rating_text,
        ),
        weights_used=context.weights.normalized(),
        deterministic_audit=audit,
        category_scores=category_scores,
        top_weaknesses=top,
        section_reviews=_section_reviews(extracted_cv, audit, skills),
        prioritised_action_plan=_actions(top),
        dimensions=_dimensions(extracted_cv, audit, skills, raw_by_key, jd),
        skills_audit=skills,
        recommendations=recommendations,
        follow_up_questions=questions,
        jd_comparison=jd,
        role_targets=targets,
        elevation_plan=elevation,
        validation_notes=[
            "Category points are calculated in application code from validated ratings and the configured weights.",
            "Objective checks and evidence tiers are deterministic. Semantic subscores, when present, are blended and do not replace those checks.",
            "Role targets and the elevation plan come from deterministic profile matching against the CV text. They suggest actions and never add content to the CV.",
        ],
    )
    return report
