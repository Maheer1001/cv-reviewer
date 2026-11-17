import os
from typing import Dict
from dotenv import load_dotenv

load_dotenv()


class AppConfig:
    """Centralized configuration for Harsh Recruiter CV Reviewer & Editor."""

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    HOST: str = os.getenv("HOST", "127.0.0.1").strip()
    PORT: int = int(os.getenv("PORT", "8000"))
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en-GB").strip()

    SUPPORTED_GEMINI_MODELS = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    ]

    # Default rubric weights totalling 100 points (Section 5 of specification)
    DEFAULT_RUBRIC_WEIGHTS: Dict[str, int] = {
        "relevance_alignment": 20,
        "impact_achievements": 20,
        "experience_project_quality": 20,
        "skills_credibility": 15,
        "writing_clarity": 10,
        "structure_readability": 10,
        "ats_compatibility": 5,
    }

    # Preset weight profiles for different career stages / target roles
    RUBRIC_PRESETS: Dict[str, Dict[str, int]] = {
        "default": {
            "relevance_alignment": 20,
            "impact_achievements": 20,
            "experience_project_quality": 20,
            "skills_credibility": 15,
            "writing_clarity": 10,
            "structure_readability": 10,
            "ats_compatibility": 5,
        },
        "student_graduate": {
            "relevance_alignment": 15,
            "impact_achievements": 15,
            "experience_project_quality": 25,
            "skills_credibility": 20,
            "writing_clarity": 10,
            "structure_readability": 10,
            "ats_compatibility": 5,
        },
        "technical_engineering": {
            "relevance_alignment": 20,
            "impact_achievements": 20,
            "experience_project_quality": 20,
            "skills_credibility": 20,
            "writing_clarity": 8,
            "structure_readability": 7,
            "ats_compatibility": 5,
        },
        "senior_leadership": {
            "relevance_alignment": 20,
            "impact_achievements": 30,
            "experience_project_quality": 20,
            "skills_credibility": 10,
            "writing_clarity": 10,
            "structure_readability": 5,
            "ats_compatibility": 5,
        },
    }

    # In-memory runtime overrides (never written to disk)
    _runtime_api_key: str = ""
    _runtime_model: str = ""

    @classmethod
    def get_api_key(cls) -> str:
        return cls._runtime_api_key or cls.GEMINI_API_KEY

    @classmethod
    def get_model(cls) -> str:
        model = cls._runtime_model or cls.GEMINI_MODEL or "gemini-2.5-flash"
        return model

    @classmethod
    def set_runtime_credentials(cls, api_key: str = "", model: str = "") -> None:
        if api_key is not None:
            cls._runtime_api_key = api_key.strip()
        if model:
            cls._runtime_model = model.strip()

    @classmethod
    def has_api_key(cls) -> bool:
        return bool(cls.get_api_key())
