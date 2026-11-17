import json
import re
from typing import Any, Dict, List, Optional

from backend.config import AppConfig
from backend.facts import rewrite_is_faithful
from backend.schemas import ExtractedCV, RecommendationItem


class SemanticAnalysisError(Exception):
    """The semantic model did not return a usable assessment."""


def llm_available() -> bool:
    return AppConfig.has_api_key()


def parse_semantic_payload(raw: str) -> Optional[Dict[str, Any]]:
    """Parse a model payload. Returns None when the response is not usable JSON."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("semantic_subscores"), dict):
        return None
    return data


def request_semantic_judgement(
    extracted_cv: ExtractedCV,
    context_summary: Dict[str, Any],
    pending_rewrites: List[RecommendationItem],
) -> Dict[str, Any]:
    """
    Ask Gemini for qualitative judgements and faithful rewrites.
    Scores returned here are subscores only. The application calculates the weighted total.
    """
    if not llm_available():
        raise SemanticAnalysisError("No GEMINI_API_KEY is configured.")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise SemanticAnalysisError("The google-genai SDK is not installed.") from exc

    bullet_payload = [
        {
            "bullet_id": item.bullet_id,
            "section": item.section_name,
            "tier": item.evidence_tier,
            "tier_reason": item.evidence_tier_reason,
            "text": item.text,
        }
        for item in (extracted_cv.deterministic_audit.bullet_audits if extracted_cv.deterministic_audit else [])
    ]
    rewrite_ids = [
        {"bullet_id": rec.bullet_id, "original_text": rec.original_text, "action": rec.action}
        for rec in pending_rewrites
        if rec.bullet_id and rec.action in ("rewrite", "verify", "condense")
    ]

    prompt = {
        "task": (
            "You are the semantic-judgement component of a CV assessment application. "
            "Deterministic checks have already classified evidence. Do not rescore the whole CV. "
            "Judge only the qualitative points requested. Use British English. "
            "Never invent employers, tools, metrics, dates, or outcomes."
        ),
        "context": context_summary,
        "evidence_classified_by_application": bullet_payload[:40],
        "rewrites_requested": rewrite_ids[:12],
        "required_json": {
            "semantic_subscores": {
                "relevance_alignment": "integer 0-100",
                "impact_achievements": "integer 0-100",
                "experience_project_quality": "integer 0-100",
                "skills_credibility": "integer 0-100",
                "writing_clarity": "integer 0-100",
            },
            "subscore_uncertainty": "short note where the evidence is ambiguous",
            "blunt_verdict": "two or three sentences citing actual CV content",
            "strongest_aspect": "one sentence, or say there is no strong aspect",
            "biggest_weakness": "one sentence naming the exact weakness",
            "dimension_notes": [
                {"code": "A-J", "assessment": "evidence-based paragraph", "inference": "what a recruiter may infer"}
            ],
            "role_hypotheses": [
                {
                    "title": "a realistic job title this CV could target that is not in rule_based_role_targets",
                    "evidence_quote": "exact text copied from the CV that supports it",
                }
            ],
            "rewrites": [
                {
                    "bullet_id": "id from rewrites_requested",
                    "suggested_text": "truthful replacement using only supplied facts; use [brackets] for unknown facts",
                    "why_stronger": "what a recruiter can now see",
                    "missing_information": "what the candidate still needs to confirm",
                }
            ],
        },
    }

    client = genai.Client(api_key=AppConfig.get_api_key())
    response = client.models.generate_content(
        model=AppConfig.get_model(),
        contents=json.dumps(prompt),
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
            system_instruction=(
                "Return only JSON. Quote CV text accurately. "
                "Do not add numbers, employers, or technologies that are absent from the supplied evidence. "
                "A missing detail is an omission, not permission to invent an achievement."
            ),
        ),
    )
    raw = getattr(response, "text", None) or ""
    parsed = parse_semantic_payload(raw)
    if parsed is None:
        raise SemanticAnalysisError("The model response was not valid assessment JSON.")
    return parsed


def apply_faithful_rewrites(
    recommendations: List[RecommendationItem],
    payload: Dict[str, Any],
    corpus: str,
) -> List[str]:
    """Apply model rewrites only when they stay within the source evidence."""
    notes: List[str] = []
    by_id = {item.get("bullet_id"): item for item in payload.get("rewrites", []) if isinstance(item, dict)}
    for rec in recommendations:
        proposal = by_id.get(rec.bullet_id or "")
        if not proposal:
            continue
        suggested = str(proposal.get("suggested_text") or "").strip()
        ok, reason = rewrite_is_faithful(rec.original_text or corpus, suggested)
        if not ok:
            notes.append(reason + f" Bullet {rec.bullet_id} kept the rule-based wording.")
            continue
        rec.suggested_text = suggested
        if proposal.get("why_stronger"):
            rec.why_stronger = str(proposal["why_stronger"])
        if proposal.get("missing_information"):
            rec.missing_info_required = str(proposal["missing_information"])
        rec.source_stage = "semantic_ai"
        rec.evidence_reasoning = (
            (rec.evidence_reasoning + " " if rec.evidence_reasoning else "")
            + "Wording refined by the semantic model and checked against the source text."
        ).strip()
    return notes
