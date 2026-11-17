import json
from typing import Dict, Optional

from backend.config import AppConfig
from backend.deterministic_analyzer import run_deterministic_cv_audit
from backend.extractor import extract_cv_from_bytes
from backend.facts import unsupported_numbers
from backend.llm_client import (
    SemanticAnalysisError,
    apply_faithful_rewrites,
    llm_available,
    request_semantic_judgement,
)
from backend.report_builder import assemble_report
from backend.role_inference import infer_career_level, merge_semantic_role_hypotheses
from backend.schemas import AnalysisContext, CVAnalysisReport, ExtractedCV
from backend.scoring import CATEGORY_METADATA, validate_and_anchor_report


def evidence_fingerprint(report: CVAnalysisReport) -> str:
    """Stable identity of the evidence profile. Wording changes that do not alter it do not move the rubric."""
    audit = report.deterministic_audit
    payload = {
        "tiers": audit.tier_counts,
        "unanchored": len(audit.unanchored_claims_detected),
        "duplicates": len(audit.duplicate_bullet_pairs),
        "buzzwords": audit.buzzwords_detected,
        "unsupported_skills": report.skills_audit.unsupported_skills,
        "role_coverage": [
            f"{c.key}:{c.coverage}:{c.depth}"
            for target in (report.role_targets.candidates if report.role_targets else [])
            if target.is_primary
            for c in target.competencies
        ],
    }
    return json.dumps(payload, sort_keys=True)


def _finalise(report: CVAnalysisReport, extracted_cv: ExtractedCV, context: AnalysisContext) -> CVAnalysisReport:
    report = validate_and_anchor_report(report, extracted_cv)
    if report.role_targets and not context.pinned_role_id:
        context.pinned_role_id = report.role_targets.primary_role_id
    return report


def _clean_subscores(raw: Dict) -> Dict[str, int]:
    cleaned: Dict[str, int] = {}
    for key in CATEGORY_METADATA:
        if key not in raw:
            continue
        try:
            cleaned[key] = max(0, min(100, int(raw[key])))
        except (TypeError, ValueError):
            continue
    return cleaned


def analyze_cv(
    extracted_cv: ExtractedCV,
    context: AnalysisContext,
    semantic_subscores: Optional[Dict[str, int]] = None,
    semantic_narrative: Optional[Dict[str, str]] = None,
) -> CVAnalysisReport:
    """
    Run the assessment pipeline.

    1. Deterministic structure, evidence-tier, skills, and job-description checks always run.
    2. The optional model may supply qualitative subscores and rewrites.
    3. Application code validates quotes, rejects invented quantities, and calculates the weighted score.
    """
    if extracted_cv.deterministic_audit is None:
        run_deterministic_cv_audit(extracted_cv)
    if context.career_level_source == "auto":
        level, reason = infer_career_level(extracted_cv)
        context.career_level = level  # type: ignore[assignment]
        context.career_level_source = "inferred"
        context.career_level_reason = reason

    notes = []
    engine = "Deterministic evidence-tier rubric"
    model_name = "local-rules-v1"
    subscores = semantic_subscores
    narrative = semantic_narrative

    if subscores is None and context.use_llm and llm_available():
        draft = assemble_report(extracted_cv, context)
        try:
            payload = request_semantic_judgement(
                extracted_cv,
                {
                    "target_job_title": context.target_job_title,
                    "target_industry": context.target_industry,
                    "career_level": context.career_level,
                    "job_description_present": bool(context.job_description.strip()),
                    "language": context.language,
                    "rule_based_role_targets": [c.title for c in (draft.role_targets.candidates if draft.role_targets else [])],
                },
                draft.recommendations,
            )
            subscores = _clean_subscores(payload.get("semantic_subscores") or {})
            if not subscores:
                raise SemanticAnalysisError("The model JSON did not include usable subscores.")
            narrative = {
                "blunt_verdict": str(payload.get("blunt_verdict") or ""),
                "strongest_aspect": str(payload.get("strongest_aspect") or ""),
                "biggest_weakness": str(payload.get("biggest_weakness") or ""),
            }
            for label, text in list(narrative.items()):
                invented = unsupported_numbers(extracted_cv.raw_text, text)
                if invented:
                    notes.append(
                        f"Ignored the model {label.replace('_', ' ')} because it introduced {', '.join(invented)}."
                    )
                    narrative[label] = ""
            engine = "Hybrid: deterministic rubric plus Gemini semantic judgement"
            model_name = AppConfig.get_model()
            report = assemble_report(
                extracted_cv,
                context,
                semantic_subscores=subscores,
                semantic_narrative={key: value for key, value in narrative.items() if value},
                engine_name=engine,
                model_identifier=model_name,
            )
            notes.extend(apply_faithful_rewrites(report.recommendations, payload, extracted_cv.raw_text))
            if report.role_targets:
                merge_semantic_role_hypotheses(report.role_targets, payload, extracted_cv.raw_text)
            if payload.get("subscore_uncertainty"):
                report.verdict.important_limitations_and_uncertainties.append(
                    "Semantic-model uncertainty: " + str(payload["subscore_uncertainty"])[:400]
                )
            report.validation_notes.extend(notes)
            return _finalise(report, extracted_cv, context)
        except Exception as exc:
            reason = str(exc) if isinstance(exc, SemanticAnalysisError) else exc.__class__.__name__
            notes.append(f"Semantic model was not used ({reason}). The deterministic rubric stands on its own.")

    report = assemble_report(
        extracted_cv,
        context,
        semantic_subscores=subscores,
        semantic_narrative=narrative,
        engine_name=engine if subscores is None else "Hybrid: deterministic rubric plus reused semantic judgement",
        model_identifier=model_name if subscores is None else AppConfig.get_model() or model_name,
    )
    report.validation_notes.extend(notes)
    return _finalise(report, extracted_cv, context)


def analyze_text(filename: str, content: bytes, context: AnalysisContext) -> tuple[ExtractedCV, CVAnalysisReport]:
    extracted = extract_cv_from_bytes(filename, content)
    return extracted, analyze_cv(extracted, context)
