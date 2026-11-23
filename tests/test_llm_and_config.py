"""Offline tests for configuration and the Gemini integration seam.

The Gemini SDK is replaced by a fake client, so these run with no key and no network
while still exercising request_semantic_judgement and the hybrid pipeline end to end.
"""
import json
import re

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import AppConfig
from backend.llm_client import (
    SemanticAnalysisError,
    apply_faithful_rewrites,
    llm_available,
    parse_semantic_payload,
    request_semantic_judgement,
)
from backend.pipeline import _clean_subscores, analyze_text
from backend.schemas import AnalysisContext, RecommendationItem

from conftest import ROOT

client = TestClient(app)

SUBSCORES = {
    "relevance_alignment": 70,
    "impact_achievements": 65,
    "experience_project_quality": 60,
    "skills_credibility": 55,
    "writing_clarity": 75,
}


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeGemini:
    """Stands in for google.genai.Client and records every call."""

    calls: list = []
    responder = None  # callable(prompt_dict) -> str, or an Exception instance to raise

    def __init__(self, api_key=None, **kwargs):
        FakeGemini.calls.append({"api_key": api_key})
        self.models = self

    def generate_content(self, model, contents, config=None):
        FakeGemini.calls[-1].update({"model": model, "prompt": json.loads(contents), "config": config})
        if isinstance(FakeGemini.responder, Exception):
            raise FakeGemini.responder
        return FakeResponse(FakeGemini.responder(json.loads(contents)))


def good_payload(prompt):
    rewrites = [
        {
            "bullet_id": item["bullet_id"],
            "suggested_text": "Delivered the [specific outcome] for " + item["original_text"].rstrip(".").lower() + ".",
            "why_stronger": "Names the outcome.",
            "missing_information": "Confirm the outcome.",
        }
        for item in prompt["rewrites_requested"][:1]
    ]
    return json.dumps(
        {
            "semantic_subscores": SUBSCORES,
            "subscore_uncertainty": "Little evidence on team size.",
            "blunt_verdict": "Solid junior CV with one measured outcome.",
            "strongest_aspect": "The Flask API bullet states a before and after.",
            "biggest_weakness": "The reporting page bullet says nothing about results.",
            "rewrites": rewrites,
            "role_hypotheses": [],
        }
    )


@pytest.fixture
def fake_gemini(monkeypatch):
    from google import genai

    FakeGemini.calls = []
    FakeGemini.responder = good_payload
    monkeypatch.setattr(genai, "Client", FakeGemini)
    monkeypatch.setattr(AppConfig, "GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(AppConfig, "GEMINI_MODEL", "gemini-2.5-flash")
    return FakeGemini


def llm_context(**kwargs):
    return AnalysisContext(career_level="junior", use_llm=True, **kwargs)


# ---------------------------------------------------------------- configuration


def test_env_example_documents_every_key_the_code_reads():
    read_keys = set()
    for path in (ROOT / "backend").rglob("*.py"):
        read_keys.update(re.findall(r"os\.(?:getenv|environ\.get)\(\s*[\"'](\w+)[\"']", path.read_text(encoding="utf-8")))
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^(\w+)=", example, flags=re.M))
    assert read_keys, "expected backend/config.py to read environment variables"
    assert read_keys <= documented, f"missing from .env.example: {sorted(read_keys - documented)}"
    assert re.search(r"^GEMINI_API_KEY=\s*$", example, flags=re.M), ".env.example must not ship a key"


def test_default_model_in_env_example_is_supported():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    model = re.search(r"^GEMINI_MODEL=(.*)$", example, flags=re.M).group(1).strip()
    assert model in AppConfig.SUPPORTED_GEMINI_MODELS


def test_offline_suite_has_no_key_configured():
    assert AppConfig.has_api_key() is False
    assert llm_available() is False


def test_runtime_credentials_override_env_values(monkeypatch):
    monkeypatch.setattr(AppConfig, "GEMINI_MODEL", "gemini-2.5-flash")
    AppConfig.set_runtime_credentials("  runtime-key  ", " gemini-2.5-pro ")
    assert AppConfig.get_api_key() == "runtime-key"
    assert AppConfig.get_model() == "gemini-2.5-pro"
    AppConfig.set_runtime_credentials("", "")
    assert AppConfig.has_api_key() is False
    assert AppConfig.get_model() == "gemini-2.5-pro"  # an empty model does not clear the override


def test_model_falls_back_to_default_when_blank(monkeypatch):
    monkeypatch.setattr(AppConfig, "GEMINI_MODEL", "")
    assert AppConfig.get_model() == "gemini-2.5-flash"


def test_rubric_presets_each_total_100_points():
    assert sum(AppConfig.DEFAULT_RUBRIC_WEIGHTS.values()) == 100
    for name, weights in AppConfig.RUBRIC_PRESETS.items():
        assert sum(weights.values()) == 100, name
        assert set(weights) == set(AppConfig.DEFAULT_RUBRIC_WEIGHTS), name


# ---------------------------------------------------------------- config API


def test_config_endpoint_reports_state_without_leaking_the_key():
    body = client.get("/api/config").json()
    assert body["has_api_key"] is False
    assert body["model"] in body["supported_models"]
    assert body["max_upload_mb"] == AppConfig.MAX_UPLOAD_MB
    updated = client.post("/api/config", json={"gemini_api_key": "secret-value", "gemini_model": "gemini-2.0-flash"})
    assert updated.status_code == 200
    assert updated.json() == {"has_api_key": True, "model": "gemini-2.0-flash"}
    assert "secret-value" not in client.get("/api/config").text


def test_config_endpoint_rejects_unsupported_model():
    response = client.post("/api/config", json={"gemini_api_key": "", "gemini_model": "gpt-4"})
    assert response.status_code == 422


def test_samples_endpoint_lists_and_analyses_bundled_samples():
    names = client.get("/api/samples").json()["samples"]
    assert "strong_engineer" in names
    response = client.post("/api/samples/strong_engineer/analyze", data={"career_level": "mid_level"})
    assert response.status_code == 200
    assert 0 <= response.json()["initial_report"]["verdict"]["overall_score"] <= 100
    assert client.post("/api/samples/does_not_exist/analyze").status_code == 404
    assert client.post("/api/samples/strong_engineer/analyze", data={"career_level": "wizard"}).status_code == 422


# ---------------------------------------------------------------- payload parsing


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"semantic_subscores": {"writing_clarity": 50}}\n```',
        'Here you go: {"semantic_subscores": {"writing_clarity": 50}} thanks',
    ],
)
def test_parse_semantic_payload_accepts_fenced_or_wrapped_json(raw):
    assert parse_semantic_payload(raw)["semantic_subscores"]["writing_clarity"] == 50


@pytest.mark.parametrize("raw", ["", "   ", "[1, 2]", '{"semantic_subscores": [1]}', '{"other": 1}', "{not json"])
def test_parse_semantic_payload_rejects_unusable_responses(raw):
    assert parse_semantic_payload(raw) is None


def test_clean_subscores_clamps_and_drops_bad_values():
    cleaned = _clean_subscores({"writing_clarity": 140, "impact_achievements": -5, "skills_credibility": "x", "unknown": 50})
    assert cleaned == {"writing_clarity": 100, "impact_achievements": 0}


def test_apply_faithful_rewrites_rejects_invented_numbers():
    rec = RecommendationItem(
        rec_id="r1", action="rewrite", priority="high", section_name="Experience",
        bullet_id="b1", original_text="Worked on the reporting page.",
    )
    notes = apply_faithful_rewrites(
        [rec], {"rewrites": [{"bullet_id": "b1", "suggested_text": "Rebuilt the reporting page for 300 users."}]}, ""
    )
    assert rec.suggested_text == ""
    assert notes and "300" in notes[0]


# ---------------------------------------------------------------- Gemini seam (faked)


def test_request_semantic_judgement_without_key_raises_before_any_call(tiny_cv_bytes):
    from backend.extractor import extract_cv_from_bytes

    with pytest.raises(SemanticAnalysisError, match="GEMINI_API_KEY"):
        request_semantic_judgement(extract_cv_from_bytes("cv.txt", tiny_cv_bytes), {}, [])


def test_request_uses_configured_key_model_and_json_mode(fake_gemini, tiny_cv_bytes):
    from backend.deterministic_analyzer import run_deterministic_cv_audit
    from backend.extractor import extract_cv_from_bytes

    extracted = extract_cv_from_bytes("cv.txt", tiny_cv_bytes)
    run_deterministic_cv_audit(extracted)
    payload = request_semantic_judgement(extracted, {"career_level": "junior"}, [])
    call = fake_gemini.calls[-1]
    assert call["api_key"] == "test-key-not-real"
    assert call["model"] == "gemini-2.5-flash"
    assert call["config"].response_mime_type == "application/json"
    assert call["prompt"]["evidence_classified_by_application"], "bullets should be sent for judgement"
    assert payload["semantic_subscores"] == SUBSCORES


def test_hybrid_pipeline_uses_fake_model_output(fake_gemini, tiny_cv_bytes):
    _, report = analyze_text("cv.txt", tiny_cv_bytes, llm_context())
    assert len(fake_gemini.calls) == 1
    assert report.verdict.analysis_engine_used.startswith("Hybrid")
    assert report.verdict.model_identifier == "gemini-2.5-flash"
    assert not any("Semantic model was not used" in note for note in report.validation_notes)
    assert any("Semantic-model uncertainty" in item for item in report.verdict.important_limitations_and_uncertainties)
    assert 0 <= report.verdict.overall_score <= 100
    assert abs(sum(c.achieved_points for c in report.category_scores) - report.verdict.overall_score) < 0.2
    if fake_gemini.calls[0]["prompt"]["rewrites_requested"]:
        assert any(rec.source_stage == "semantic_ai" for rec in report.recommendations)


def test_hybrid_pipeline_drops_narrative_with_invented_numbers(fake_gemini, tiny_cv_bytes):
    def invented(prompt):
        data = json.loads(good_payload(prompt))
        data["blunt_verdict"] = "Saved the company 9999 pounds."
        return json.dumps(data)

    fake_gemini.responder = invented
    _, report = analyze_text("cv.txt", tiny_cv_bytes, llm_context())
    assert any("9999" in note for note in report.validation_notes)
    assert "9999" not in report.verdict.blunt_recruiter_verdict


@pytest.mark.parametrize(
    "responder, expected_note",
    [
        (lambda prompt: "Sorry, I can't do that.", "not valid assessment JSON"),
        (lambda prompt: json.dumps({"semantic_subscores": {"nonsense": 5}}), "usable subscores"),
        (RuntimeError("connection reset"), "RuntimeError"),
    ],
)
def test_pipeline_falls_back_to_deterministic_when_model_fails(fake_gemini, tiny_cv_bytes, responder, expected_note):
    fake_gemini.responder = responder
    _, report = analyze_text("cv.txt", tiny_cv_bytes, llm_context())
    assert any("Semantic model was not used" in n and expected_note in n for n in report.validation_notes)
    assert not any(rec.source_stage == "semantic_ai" for rec in report.recommendations)


@pytest.mark.parametrize(
    "responder",
    [lambda prompt: "Sorry, I can't do that.", RuntimeError("connection reset")],
)
def test_failed_model_call_is_labelled_deterministic(fake_gemini, tiny_cv_bytes, responder):
    fake_gemini.responder = responder
    _, report = analyze_text("cv.txt", tiny_cv_bytes, llm_context())
    assert report.verdict.analysis_engine_used == "Deterministic evidence-tier rubric"
    assert report.verdict.model_identifier == "local-rules-v1"


@pytest.mark.xfail(
    strict=True,
    reason="Known issue: when the model JSON has no usable subscores, pipeline.analyze_cv leaves "
    "subscores={} (not None), so the deterministic fallback is labelled as 'reused semantic judgement'.",
)
def test_unusable_subscores_fallback_is_labelled_deterministic(fake_gemini, tiny_cv_bytes):
    fake_gemini.responder = lambda prompt: json.dumps({"semantic_subscores": {"nonsense": 5}})
    _, report = analyze_text("cv.txt", tiny_cv_bytes, llm_context())
    assert report.verdict.analysis_engine_used == "Deterministic evidence-tier rubric"


def test_pipeline_does_not_call_model_when_llm_is_switched_off(fake_gemini, tiny_cv_bytes):
    analyze_text("cv.txt", tiny_cv_bytes, AnalysisContext(career_level="junior", use_llm=False))
    assert fake_gemini.calls == []


def test_tiny_fixture_cv_produces_a_well_formed_deterministic_report(tiny_cv_bytes):
    extracted, report = analyze_text("cv.txt", tiny_cv_bytes, AnalysisContext(career_level_source="auto", use_llm=False))
    assert extracted.raw_text.startswith("Sam Example")
    assert 0 <= report.verdict.overall_score <= 100
    assert len(report.category_scores) == 7
    assert report.recommendations
