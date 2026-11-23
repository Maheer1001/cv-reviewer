"""Opt-in live setup check.

Run with:  python -m pytest -m integration -v

It reads your real .env (or environment) and, in order:
  1. confirms the configuration loaded and the keys the app reads are present and valid;
  2. sends one minimal request to the configured Gemini model to prove the key and model work;
  3. runs one full hybrid review of a tiny bundled CV and checks the report is well formed
     and actually used the model.

Steps 2 and 3 make two small Gemini generation calls (free tier is fine). Everything is skipped,
with a message saying why, when no GEMINI_API_KEY is configured.
"""
import re

import pytest

from backend.config import AppConfig
from backend.pipeline import analyze_text
from backend.schemas import AnalysisContext

from conftest import FIXTURES, ROOT

pytestmark = pytest.mark.integration

ENV_FILE = ROOT / ".env"
NO_KEY = (
    "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key to run the live setup check "
    "(the app itself works without one in deterministic mode)."
)


def _require_key():
    if not AppConfig.get_api_key():
        pytest.skip(NO_KEY)


def _example_keys():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    return re.findall(r"^(\w+)=", text, flags=re.M)


def test_1_env_loaded_and_required_keys_present():
    _require_key()
    if ENV_FILE.is_file():
        env_text = ENV_FILE.read_text(encoding="utf-8")
        set_keys = set(re.findall(r"^\s*(\w+)\s*=", env_text, flags=re.M))
        missing = [key for key in _example_keys() if key not in set_keys]
        # Optional keys fall back to defaults, so a missing one is a warning, not a failure.
        if missing:
            import warnings

            warnings.warn(f".env does not set {missing}; the defaults from config.py will be used.")
    assert AppConfig.get_api_key().strip(), "GEMINI_API_KEY is blank"
    assert AppConfig.get_model() in AppConfig.SUPPORTED_GEMINI_MODELS, (
        f"GEMINI_MODEL={AppConfig.get_model()!r} is not one of {AppConfig.SUPPORTED_GEMINI_MODELS}"
    )
    assert AppConfig.MAX_UPLOAD_MB > 0, "MAX_UPLOAD_MB must be a positive integer"


def test_2_configured_model_is_reachable():
    _require_key()
    from google import genai

    client = genai.Client(api_key=AppConfig.get_api_key())
    model = AppConfig.get_model()
    try:
        info = client.models.get(model=model)  # metadata lookup: proves key and model id
    except Exception as exc:
        pytest.fail(f"Gemini rejected the key or model {model!r}: {exc.__class__.__name__}: {str(exc)[:300]}")
    assert model in (info.name or ""), f"unexpected model metadata: {info.name!r}"
    response = client.models.generate_content(model=model, contents="Reply with the single word OK.")
    assert (response.text or "").strip(), "the model returned an empty response"


def test_3_end_to_end_review_of_tiny_sample_cv():
    _require_key()
    content = (FIXTURES / "tiny_cv.txt").read_bytes()
    context = AnalysisContext(career_level="junior", target_job_title="Python developer", use_llm=True)
    _, report = analyze_text("tiny_cv.txt", content, context)

    fallback = [note for note in report.validation_notes if "Semantic model was not used" in note]
    assert not fallback, fallback[0] if fallback else ""
    assert report.verdict.analysis_engine_used.startswith("Hybrid")
    assert report.verdict.model_identifier == AppConfig.get_model()
    assert 0 <= report.verdict.overall_score <= 100
    assert len(report.category_scores) == 7
    assert abs(sum(c.achieved_points for c in report.category_scores) - report.verdict.overall_score) < 0.2
    assert report.verdict.blunt_recruiter_verdict.strip()
    assert report.recommendations
