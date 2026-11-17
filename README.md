# CV Reviewer

A local CV assessment application. It parses the uploaded document, classifies evidence with deterministic checks, calculates a weighted rubric in application code, and keeps a separate working copy of the CV for accepted edits.

You do not have to say what you are applying for. With no target title, the reviewer infers your career level and the roles your CV most resembles, scores relevance against the closest one, and builds an elevation plan: writing upgrades taken from your own lines, things to add now if they are true, and things to begin doing so the CV can honestly say more next time.

Semantic judgement is optional. When `GEMINI_API_KEY` is set and semantic analysis is enabled, extracted text is sent to Google Gemini for qualitative subscores, rewrites and extra role suggestions. Rewrites are rejected if they introduce numbers or praise that are not in the source, and role suggestions are dropped unless they quote the CV. The weighted score is still calculated locally.

## Run it

From this directory:

```bash
python -m pip install -r requirements.txt
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Copy `.env.example` to `.env` if you want a Gemini key loaded at startup. You can also enter a key in the page; it stays in the server process memory and is not written into the frontend.

```text
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
```

Supported model identifiers are `gemini-2.5-flash`, `gemini-2.5-pro`, and `gemini-2.0-flash`.

## Using it

1. Drop a PDF or DOCX (or pick a sample). Target title, career level, industry and job description are all optional.
2. **Overview** gives the score, the three separate verdicts (general quality, role suitability, competitiveness), the top weaknesses and what to do next.
3. **Role targets** shows up to four role profiles your evidence fits, each with coverage, evidence depth, readiness, the competencies recruiters screen for, and the gaps to close. "Re-run the review for this role" rescores the CV against another role; the previous session is discarded.
4. **Elevation plan** lists writing upgrades with before/after examples from your CV, items to add now if true, and actions to begin, grouped into this week, the next 30 days and the next 90 days.
5. **Edits** is where you answer questions and accept, edit, reject or undo each suggestion. **Revised CV** previews and exports the result. Export is blocked while `[placeholders]` remain unless you confirm them.
6. **Reassess** rescores the revised CV with the same rubric and the same role.

## Tests

```bash
python -m pytest tests -q
```

The tests use fictional CVs in `samples/`. They check evidence ordering, quote anchoring, edit/export behaviour, document failures, that a paraphrase does not increase the impact score, that roles and career level are inferred when nothing is specified, that a stated target is honoured, that the elevation plan never invents facts, and that reassessment keeps the same role.

## What is calculated locally

- PDF and DOCX text extraction, headings, links, tables, columns, headers, and footers.
- Evidence tiers, bullet length, repetition, duplicates, buzzwords, and unanchored claims.
- Skills cross-checked against experience and projects.
- Career level from dated roles, education and titles, when you leave it on "Auto-detect".
- Role matching against 40 IT profiles in `backend/profiles/`, covering software engineering, data and AI, infrastructure and support, security, hardware and robotics, and product and design. A competency counts fully when it appears in experience or projects, half in the summary, and 0.3 in a skills list only. Essential competencies count double.
- The elevation plan in `backend/elevation.py`.
- Job-description alignment when a description is supplied.
- Weighted scores, validation that a recommendation quotes real text, and edit state.
- DOCX, PDF, and change-summary export from the working CV.

## What the model does, when configured

- Qualitative subscores for relevance, impact, experience, skills, and writing.
- Narrative verdict and faithful rewrites.
- Extra role suggestions, shown separately and only when they quote the CV.

If the model is unavailable or returns malformed JSON, the deterministic rubric is used on its own and the report says so.

## API

- `GET /api/config`: rubric presets, models, role profiles, and whether a key is configured.
- `POST /api/analyze` (upload) and `POST /api/samples/{name}/analyze`: start a session. `career_level` defaults to `auto`.
- `POST /api/sessions/{id}/retarget`: rescore against a role profile (`role_id`) or a free-text `target_job_title`. Returns a new session and drops the old one.
- `POST /api/sessions/{id}/reassess`, plus the decision, question and export endpoints used by the Edits and Revised CV tabs.

## Limits

The rubric is not a prediction of an interview or an offer, and it has not been calibrated on a hiring dataset. Role fit is keyword coverage against a hand-written profile, not a judgement of ability; a missing competency means it is not shown on the CV, not that you lack it.

The profiles and the evidence vocabulary cover IT work: software engineering, data and AI, infrastructure, support, security, embedded systems, robotics, mechatronics, electronics, industrial automation, and the product, design and business-systems roles around them. A CV from outside IT, such as law, medicine or teaching, will score poorly and match no meaningful role, because the reviewer has no way to recognise that evidence. Evidence tiers recognise the shape of proof. They do not fully judge whether a project was production work or a tutorial unless the semantic model is used. Export creates a clean single-column document; it does not reproduce the original visual design. Sessions live in memory and disappear when the server stops.
