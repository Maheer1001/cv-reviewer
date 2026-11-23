"""Shared test setup.

Offline tests (everything not marked ``integration``) must never reach the network,
even when a developer has a real GEMINI_API_KEY in their .env. The autouse fixture
below blanks the configured key and replaces the Gemini client with a guard that
fails the test if anything tries to construct it. Tests that want to exercise the
LLM path install their own fake client on top of this.
"""
from pathlib import Path

import pytest

from backend.config import AppConfig

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _NetworkGuardClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("Offline test tried to create a real Gemini client.")


@pytest.fixture(autouse=True)
def offline_by_default(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        yield
        return
    monkeypatch.setattr(AppConfig, "GEMINI_API_KEY", "")
    monkeypatch.setattr(AppConfig, "_runtime_api_key", "")
    monkeypatch.setattr(AppConfig, "_runtime_model", "")
    try:
        from google import genai
    except ImportError:
        pass
    else:
        monkeypatch.setattr(genai, "Client", _NetworkGuardClient)
    yield


@pytest.fixture
def tiny_cv_bytes() -> bytes:
    return (FIXTURES / "tiny_cv.txt").read_bytes()
