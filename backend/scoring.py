from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from backend.schemas import (
    CVAnalysisReport,
    CategoryScore,
    ExtractedBullet,
    ExtractedCV,
    RecommendationItem,
    RubricWeights,
    ScoreDeductionItem,
)


CATEGORY_METADATA: Dict[str, Dict[str, str]] = {
    "relevance_alignment": {
        "name": "Relevance and role alignment",
        "criteria": (
            "Evaluates whether the CV communicates a coherent professional direction, prioritises evidence "
            "relevant to the target role and career level, and surfaces strongest qualifications immediately "
            "without burying them under unrelated history."
        ),
    },
    "impact_achievements": {
        "name": "Evidence of impact and achievements",
        "criteria": (
            "Evaluates whether bullet points prove tangible outcomes (Tier 3/4 evidence), professional or business value, "
            "ownership, and problem-solving rather than merely listing routine duties (Tier 1) or unanchored claims."
        ),
    },
    "experience_project_quality": {
        "name": "Experience and project quality",
        "criteria": (
            "Evaluates the depth, complexity, professional rigour, personal contribution, and decision-making "
            "context across employment, internships, research, and projects."
        ),
    },
    "skills_credibility": {
        "name": "Technical or professional skills credibility",
        "criteria": (
            "Evaluates whether skills listed in the Skills section are substantiated by concrete evidence in "
            "Experience or Projects, penalising bloated keyword lists and unverified proficiency claims."
        ),
    },
    "writing_clarity": {
        "name": "Writing quality and clarity",
        "criteria": (
            "Evaluates conciseness, British English professionalism, absence of empty buzzwords or clichés, "
            "meaningful verb choice, and absence of duplicated/repetitive bullets."
        ),
    },
    "structure_readability": {
        "name": "Structure and readability",
        "criteria": (
            "Evaluates visual hierarchy, scan speed, section ordering, bullet length consistency, "
            "and appropriate document length for the candidate's career stage."
        ),
    },
    "ats_compatibility": {
        "name": "ATS compatibility",
        "criteria": (
            "Evaluates structural parsability based on verified document diagnostics: absence of multi-column "
            "interleaving, layout tables, floating text boxes, header-trapped contact info, and ambiguous headings."
        ),
    },
}


def compute_category_scores(
    deterministic_ratings: Dict[str, int],
    weights: RubricWeights,
    evidence_map: Dict[str, List[str]],
    weaknesses_map: Dict[str, List[str]],
    improvements_map: Dict[str, List[str]],
    deductions_map: Optional[Dict[str, List[ScoreDeductionItem]]] = None,
    uncertainty_map: Optional[Dict[str, str]] = None,
    semantic_ratings: Optional[Dict[str, int]] = None,
) -> Tuple[List[CategoryScore], float]:
    """
    Deterministically compute weighted category scores and aggregate total out of 100.
    For objective categories (ATS compatibility, structure, skills cross-check), deterministic rules
    dominate; for qualitative categories (relevance, impact, experience depth), deterministic sub-scores
    and validated semantic judgements are blended transparently.
    """
    norm_weights = weights.normalized()
    weight_dict = {
        "relevance_alignment": norm_weights.relevance_alignment,
        "impact_achievements": norm_weights.impact_achievements,
        "experience_project_quality": norm_weights.experience_project_quality,
        "skills_credibility": norm_weights.skills_credibility,
        "writing_clarity": norm_weights.writing_clarity,
        "structure_readability": norm_weights.structure_readability,
        "ats_compatibility": norm_weights.ats_compatibility,
    }

    # Blend weights between deterministic sub-score and semantic AI sub-score when AI sub-score is available
    deterministic_blend_ratio = {
        "ats_compatibility": 1.0,       # 100% deterministic from document inspection
        "structure_readability": 0.80,  # 80% deterministic structural rules
        "skills_credibility": 0.80,     # 80% deterministic cross-referencing
        "writing_clarity": 0.70,        # 70% deterministic linguistic checks
        "impact_achievements": 0.60,    # 60% deterministic evidence-tier + 40% semantic evaluation
        "experience_project_quality": 0.55,
        "relevance_alignment": 0.50,
    }

    category_scores: List[CategoryScore] = []
    total_points = 0.0
    deductions_map = deductions_map or {}
    uncertainty_map = uncertainty_map or {}

    for key, meta in CATEGORY_METADATA.items():
        w = weight_dict.get(key, 0)
        det_raw = max(0, min(100, int(deterministic_ratings.get(key, 50))))
        sem_raw: Optional[int] = None
        if semantic_ratings and key in semantic_ratings and semantic_ratings[key] is not None:
            sem_raw = max(0, min(100, int(semantic_ratings[key])))
            alpha = deterministic_blend_ratio.get(key, 0.6)
            combined_raw = int(round(alpha * det_raw + (1.0 - alpha) * sem_raw))
        else:
            combined_raw = det_raw

        achieved = round((combined_raw * w) / 100.0, 1)
        total_points += achieved

        category_scores.append(
            CategoryScore(
                category_key=key,
                category_name=meta["name"],
                raw_rating_out_of_100=combined_raw,
                deterministic_subscore=det_raw,
                semantic_subscore=sem_raw,
                weight=w,
                achieved_points=achieved,
                max_points=float(w),
                scoring_criteria=meta["criteria"],
                deductions_and_credits=deductions_map.get(key, [])[:6],
                supporting_evidence=evidence_map.get(key, [])[:4],
                main_weaknesses=weaknesses_map.get(key, [])[:4],
                improvement_actions=improvements_map.get(key, [])[:4],
                uncertainty_note=uncertainty_map.get(key),
            )
        )

    return category_scores, round(min(100.0, max(0.0, total_points)), 1)


def match_text_to_extracted_bullet(
    snippet: str, extracted_cv: ExtractedCV
) -> Tuple[Optional[ExtractedBullet], float]:
    """Find the best matching ExtractedBullet in the CV for a given text snippet."""
    if not snippet or not snippet.strip():
        return None, 0.0

    norm_snip = " ".join(snippet.lower().split())
    best_bullet: Optional[ExtractedBullet] = None
    best_score = 0.0

    all_candidates: List[ExtractedBullet] = []
    for sec in extracted_cv.sections:
        all_candidates.extend(sec.items)

    for b in all_candidates:
        norm_b = " ".join(b.text.lower().split())
        if not norm_b:
            continue
        if norm_snip == norm_b:
            return b, 1.0
        if norm_snip in norm_b or norm_b in norm_snip:
            ratio = min(len(norm_snip), len(norm_b)) / max(len(norm_snip), len(norm_b), 1)
            score = max(0.86, ratio)
        else:
            score = SequenceMatcher(None, norm_snip, norm_b).ratio()
        if score > best_score:
            best_score = score
            best_bullet = b

    return best_bullet, best_score


def validate_and_anchor_report(
    report: CVAnalysisReport,
    extracted_cv: ExtractedCV,
) -> CVAnalysisReport:
    """
    Validate AI/engine analysis output:
    1. Recompute category scores and total score deterministically from weights.
    2. Anchor every recommendation referencing existing CV text to an actual ExtractedBullet.
    3. Filter or flag any unverified references to text that does not exist in the CV.
    4. Ensure every recommendation has explicit rubric_criteria_affected and evidence_type.
    5. Deduplicate recommendations.
    """
    validation_notes = list(report.validation_notes)

    # 1. Re-verify category scores deterministically
    norm_weights = report.weights_used.normalized()
    report.weights_used = norm_weights
    weight_lookup = {
        "relevance_alignment": norm_weights.relevance_alignment,
        "impact_achievements": norm_weights.impact_achievements,
        "experience_project_quality": norm_weights.experience_project_quality,
        "skills_credibility": norm_weights.skills_credibility,
        "writing_clarity": norm_weights.writing_clarity,
        "structure_readability": norm_weights.structure_readability,
        "ats_compatibility": norm_weights.ats_compatibility,
    }

    recalculated_total = 0.0
    for cat in report.category_scores:
        w = weight_lookup.get(cat.category_key, cat.weight)
        cat.weight = w
        cat.max_points = float(w)
        cat.raw_rating_out_of_100 = max(0, min(100, int(cat.raw_rating_out_of_100)))
        cat.achieved_points = round((cat.raw_rating_out_of_100 * w) / 100.0, 1)
        if not cat.scoring_criteria and cat.category_key in CATEGORY_METADATA:
            cat.scoring_criteria = CATEGORY_METADATA[cat.category_key]["criteria"]
        recalculated_total += cat.achieved_points

    recalculated_total = round(min(100.0, max(0.0, recalculated_total)), 1)
    if abs(report.verdict.overall_score - recalculated_total) > 0.15:
        validation_notes.append(
            f"Adjusted overall score from {report.verdict.overall_score} to deterministic rubric sum {recalculated_total}/100."
        )
    report.verdict.overall_score = recalculated_total

    # 2. Anchor recommendations to actual CV bullets & deduplicate
    bullet_by_id = {
        item.bullet_id: item for sec in extracted_cv.sections for item in sec.items
    }
    deduped_recs: List[RecommendationItem] = []
    seen_keys = set()

    default_criteria_by_action = {
        "keep": ["Evidence of impact and achievements", "Experience and project quality"],
        "rewrite": ["Evidence of impact and achievements", "Writing quality and clarity"],
        "cut": ["Writing quality and clarity", "Structure and readability"],
        "add": ["Relevance and role alignment", "Experience and project quality"],
        "move": ["Structure and readability", "Relevance and role alignment"],
        "condense": ["Writing quality and clarity", "Structure and readability"],
        "verify": ["Technical or professional skills credibility", "Evidence of impact and achievements"],
    }

    for idx, rec in enumerate(report.recommendations):
        rec.rec_id = f"rec_{idx + 1}"

        if not rec.rubric_criteria_affected:
            rec.rubric_criteria_affected = default_criteria_by_action.get(
                rec.action, ["Evidence of impact and achievements"]
            )

        if rec.action == "add":
            rec.evidence_type = "explicit_omission"
            rec.verified_in_cv = True
            if not rec.evidence_reasoning:
                rec.evidence_reasoning = (
                    f"Explicit omission identified in [{rec.section_name}]: {rec.why_stronger}"
                )
        elif rec.action == "move" and not rec.original_text:
            rec.evidence_type = "structural_observation"
            rec.verified_in_cv = True
        elif rec.action in ("keep", "rewrite", "cut", "move", "condense", "verify"):
            matched_bullet = bullet_by_id.get(rec.bullet_id or "")
            if matched_bullet and rec.original_text:
                sim = SequenceMatcher(
                    None, rec.original_text.lower().strip(), matched_bullet.text.lower().strip()
                ).ratio()
                if sim < 0.45:
                    matched_bullet = None

            if not matched_bullet and rec.original_text:
                candidate, score = match_text_to_extracted_bullet(rec.original_text, extracted_cv)
                if candidate and score >= 0.55:
                    matched_bullet = candidate
                    rec.bullet_id = candidate.bullet_id
                    if rec.action != "condense":
                        rec.original_text = candidate.text
                    rec.section_name = candidate.section_name
                    rec.verified_in_cv = True
                    rec.evidence_type = "verified_quote"
                elif rec.original_text.lower() in extracted_cv.raw_text.lower():
                    rec.verified_in_cv = True
                    rec.evidence_type = "verified_quote"
                else:
                    rec.verified_in_cv = False
                    validation_notes.append(
                        f"Filtered unverified recommendation referencing text not found in CV: '{rec.original_text[:65]}...'"
                    )
                    continue
            elif matched_bullet:
                rec.bullet_id = matched_bullet.bullet_id
                if rec.action != "condense":
                    rec.original_text = matched_bullet.text
                rec.section_name = matched_bullet.section_name
                rec.verified_in_cv = True
                rec.evidence_type = "verified_quote"

            if not rec.evidence_reasoning:
                rec.evidence_reasoning = (
                    f"Anchored to verified passage in [{rec.section_name}] (item {rec.bullet_id or 'body'})."
                )

        dedup_key = (rec.action, (rec.original_text or rec.suggested_text).strip().lower()[:120])
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        deduped_recs.append(rec)

    # Re-index rec_ids cleanly and update linked questions
    old_to_new_id: Dict[str, str] = {}
    for i, rec in enumerate(deduped_recs):
        new_id = f"rec_{i + 1}"
        old_to_new_id[rec.rec_id] = new_id
        rec.rec_id = new_id

    for q_idx, q in enumerate(report.follow_up_questions):
        q.question_id = f"q_{q_idx + 1}"
        if q.linked_rec_id and q.linked_rec_id in old_to_new_id:
            q.linked_rec_id = old_to_new_id[q.linked_rec_id]
        for rec in deduped_recs:
            if rec.rec_id == q.linked_rec_id or (
                rec.bullet_id and q.bullet_id and rec.bullet_id == q.bullet_id
            ):
                rec.linked_question_id = q.question_id
                q.linked_rec_id = rec.rec_id
                break

    report.recommendations = deduped_recs

    for rank_i, w in enumerate(report.top_weaknesses[:5]):
        w.rank = rank_i + 1
    report.top_weaknesses = report.top_weaknesses[:5]

    report.validation_notes = validation_notes
    return report
