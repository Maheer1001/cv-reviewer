import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from backend.config import AppConfig
from backend.editing import (
    answer_question,
    build_working_cv,
    decide_recommendation,
    placeholders_in,
    reassess,
    refresh_counts,
)
from backend.exporter import export_change_summary, export_docx, export_pdf
from backend.extractor import DocumentExtractionError
from backend.pipeline import analyze_cv, analyze_text
from backend.profiles import PROFILES_BY_ID
from backend.schemas import AnalysisContext, RubricWeights, SessionState

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SAMPLES = ROOT / "samples"
SESSIONS: Dict[str, SessionState] = {}

app = FastAPI(title="Harsh Recruiter CV Reviewer", version="1.0.0")
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


class DecisionBody(BaseModel):
    decision: str
    edited_text: str = ""


class AnswerBody(BaseModel):
    resolution: str
    answer: str = ""


class SettingsBody(BaseModel):
    gemini_api_key: str = ""
    gemini_model: str = ""


class RetargetBody(BaseModel):
    role_id: str = ""
    target_job_title: str = ""


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _context_from_form(
    target_job_title: str,
    target_industry: str,
    career_level: str,
    job_description: str,
    language: str,
    use_llm: str,
    weights_json: str,
) -> AnalysisContext:
    allowed = {
        "auto",
        "student_graduate",
        "junior",
        "mid_level",
        "senior_lead",
        "career_changer",
        "executive",
    }
    if career_level not in allowed:
        raise HTTPException(status_code=422, detail="Choose a supported career level.")
    auto_level = career_level == "auto"
    weights = RubricWeights()
    if weights_json.strip():
        try:
            weights = RubricWeights(**json.loads(weights_json))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail="Rubric weights must be a JSON object of the seven categories.") from exc
    return AnalysisContext(
        target_job_title=target_job_title.strip(),
        target_industry=target_industry.strip(),
        career_level="mid_level" if auto_level else career_level,  # type: ignore[arg-type]
        career_level_source="auto" if auto_level else "user",
        job_description=job_description.strip(),
        language=language.strip() or "en-GB",
        weights=weights.normalized(),
        use_llm=_as_bool(use_llm),
    )


def _store_session(extracted, report, context) -> SessionState:
    working = build_working_cv(extracted)
    session = SessionState(
        session_id=uuid.uuid4().hex,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        context=context,
        extracted_cv=extracted,
        initial_report=report,
        working_cv=working,
    )
    refresh_counts(session)
    SESSIONS[session.session_id] = session
    return session


def _session_or_404(session_id: str) -> SessionState:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="This review session is not in memory. Upload the CV again.")
    return session


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html")


@app.get("/api/config")
def get_config() -> dict:
    return {
        "has_api_key": AppConfig.has_api_key(),
        "model": AppConfig.get_model(),
        "supported_models": AppConfig.SUPPORTED_GEMINI_MODELS,
        "max_upload_mb": AppConfig.MAX_UPLOAD_MB,
        "presets": AppConfig.RUBRIC_PRESETS,
        "roles": [{"role_id": p.role_id, "title": p.title, "family": p.family} for p in PROFILES_BY_ID.values()],
        "privacy": (
            "Extraction, evidence checks, scoring, editing, and export run on this machine. "
            "If a Gemini key is configured and semantic analysis is enabled, the extracted text and job description are sent to Google for qualitative judgement only."
        ),
    }


@app.post("/api/config")
def update_config(body: SettingsBody) -> dict:
    if body.gemini_model and body.gemini_model not in AppConfig.SUPPORTED_GEMINI_MODELS:
        raise HTTPException(status_code=422, detail="Choose a supported Gemini model identifier.")
    AppConfig.set_runtime_credentials(body.gemini_api_key, body.gemini_model)
    return {"has_api_key": AppConfig.has_api_key(), "model": AppConfig.get_model()}


@app.get("/api/samples")
def list_samples() -> dict:
    names = sorted(path.stem for path in SAMPLES.glob("*.txt"))
    return {"samples": names}


@app.post("/api/samples/{sample_name}/analyze")
def analyze_sample(
    sample_name: str,
    target_job_title: str = Form(""),
    target_industry: str = Form(""),
    career_level: str = Form("auto"),
    job_description: str = Form(""),
    language: str = Form("en-GB"),
    use_llm: str = Form("false"),
    weights_json: str = Form(""),
) -> dict:
    path = SAMPLES / f"{sample_name}.txt"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Unknown sample CV.")
    context = _context_from_form(
        target_job_title, target_industry, career_level, job_description, language, use_llm, weights_json
    )
    try:
        extracted, report = analyze_text(path.name, path.read_bytes(), context)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _store_session(extracted, report, context).model_dump()


@app.post("/api/analyze")
async def analyze_upload(
    file: UploadFile = File(...),
    target_job_title: str = Form(""),
    target_industry: str = Form(""),
    career_level: str = Form("auto"),
    job_description: str = Form(""),
    language: str = Form("en-GB"),
    use_llm: str = Form("false"),
    weights_json: str = Form(""),
) -> dict:
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX CV.")
    content = await file.read()
    limit = AppConfig.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"The file exceeds the {AppConfig.MAX_UPLOAD_MB} MB limit.")
    context = _context_from_form(
        target_job_title, target_industry, career_level, job_description, language, use_llm, weights_json
    )
    try:
        extracted, report = analyze_text(filename, content, context)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"The document could not be read ({exc.__class__.__name__}).") from exc
    return _store_session(extracted, report, context).model_dump()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    return _session_or_404(session_id).model_dump()


@app.post("/api/sessions/{session_id}/recommendations/{rec_id}")
def update_recommendation(session_id: str, rec_id: str, body: DecisionBody) -> dict:
    session = _session_or_404(session_id)
    try:
        decide_recommendation(session, rec_id, body.decision, body.edited_text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Recommendation not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return session.model_dump()


@app.post("/api/sessions/{session_id}/questions/{question_id}")
def update_question(session_id: str, question_id: str, body: AnswerBody) -> dict:
    session = _session_or_404(session_id)
    allowed = {"answered", "skipped", "dont_know", "confidential", "use_existing"}
    if body.resolution not in allowed:
        raise HTTPException(status_code=422, detail="Unsupported answer type.")
    try:
        answer_question(session, question_id, body.resolution, body.answer)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc
    return session.model_dump()


@app.post("/api/sessions/{session_id}/retarget")
def retarget_session(session_id: str, body: RetargetBody) -> dict:
    source = _session_or_404(session_id)
    profile = PROFILES_BY_ID.get(body.role_id) if body.role_id else None
    if body.role_id and profile is None:
        raise HTTPException(status_code=422, detail="Unknown role profile.")
    title = (profile.title if profile else body.target_job_title).strip()[:120]
    if not title:
        raise HTTPException(status_code=422, detail="Choose a role or enter a job title.")
    context = source.context.model_copy(
        update={"target_job_title": title, "pinned_role_id": profile.role_id if profile else ""}
    )
    extracted = source.extracted_cv.model_copy(deep=True)
    report = analyze_cv(extracted, context)
    session = _store_session(extracted, report, context)
    SESSIONS.pop(session_id, None)
    return session.model_dump()


@app.post("/api/sessions/{session_id}/reassess")
def reassess_session(session_id: str) -> dict:
    session = _session_or_404(session_id)
    try:
        reassess(session)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return session.model_dump()


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str, export_format: str = "docx", acknowledge_placeholders: bool = False) -> Response:
    session = _session_or_404(session_id)
    flags = placeholders_in(session.working_cv)
    if flags and not acknowledge_placeholders:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "The working CV still contains unresolved placeholders or instructions. Confirm them before export.",
                "placeholders": flags,
            },
        )
    stem = (session.extracted_cv.contact.name or "revised-cv").replace(" ", "-").lower()
    if export_format == "docx":
        payload = export_docx(session)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = f"{stem}-revised.docx"
    elif export_format == "pdf":
        payload = export_pdf(session)
        media = "application/pdf"
        filename = f"{stem}-revised.pdf"
    elif export_format == "summary":
        payload = export_change_summary(session).encode("utf-8")
        media = "text/plain; charset=utf-8"
        filename = f"{stem}-change-summary.txt"
    else:
        raise HTTPException(status_code=422, detail="Supported export formats are docx, pdf, and summary.")
    return Response(content=payload, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
