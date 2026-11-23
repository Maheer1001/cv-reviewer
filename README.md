# CV Reviewer

A local CV assessment application. It parses the uploaded document, classifies evidence with deterministic checks, calculates a weighted rubric in application code, and keeps a separate working copy of the CV for accepted edits.

You do not have to say what you are applying for. With no target title, the reviewer infers your career level and the roles your CV most resembles, scores relevance against the closest one, and builds an elevation plan: writing upgrades taken from your own lines, things to add now if they are true, and things to begin doing so the CV can honestly say more next time.

Semantic judgement is optional. When `GEMINI_API_KEY` is set and semantic analysis is enabled, extracted text is sent to Google Gemini for qualitative subscores, rewrites and extra role suggestions. Rewrites are rejected if they introduce numbers or praise that are not in the source, and role suggestions are dropped unless they quote the CV. The weighted score is still calculated locally.

## Prerequisites

- Python 3.13 (tested on Windows 10 with Python 3.13; 3.11+ should work).
- Git, to clone the repository.
- Optional: a Google Gemini API key for semantic analysis. The app works fully without one.

## Setup

Clone the repository and create a virtual environment in the project folder, then install the dependencies.

PowerShell (Windows):

```powershell
git clone https://github.com/Maheer1001/cv-reviewer.git
cd cv-reviewer
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

bash (Git Bash on Windows, macOS, Linux):

```bash
git clone https://github.com/Maheer1001/cv-reviewer.git
cd cv-reviewer
python3 -m venv .venv          # on Windows Git Bash: py -3.13 -m venv .venv
source .venv/bin/activate      # on Windows Git Bash: source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you prefer to activate the environment in PowerShell, run `.\.venv\Scripts\Activate.ps1` (you may need `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once). The commands below call the venv interpreter directly, so activation is optional.

`.venv/` is gitignored.

## Configure (.env)

Configuration is optional. Copy the example file and fill in what you need:

```powershell
Copy-Item .env.example .env      # PowerShell
```

```bash
cp .env.example .env             # bash
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | empty | Optional Gemini key. Empty means deterministic mode only. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | One of `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash`. |
| `MAX_UPLOAD_MB` | `10` | Maximum upload size in MB. |
| `HOST`, `PORT` | `127.0.0.1`, `8000` | Read into config but not used to bind the server; pass `--host`/`--port` to uvicorn instead. |
| `DEFAULT_LANGUAGE` | `en-GB` | Reserved; not currently used. |

`.env` is gitignored. You can also enter a key in the page at runtime; it stays in the server process memory and is not written to disk or into the frontend.

## Getting API keys

The only external key the app uses is a Google Gemini API key, and it is optional. **Without it the app runs in its built-in deterministic mode**: extraction, scoring, role matching, the elevation plan, edits and export all work locally, and no CV text leaves your machine.

To get a Gemini key:

1. Go to Google AI Studio at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2. Sign in with a Google account and accept the terms if prompted.
3. Click **Create API key**. Choose an existing Google Cloud project or let AI Studio create one for you.
4. Copy the key and put it in your `.env` file:

   ```text
   GEMINI_API_KEY=your-key-here
   GEMINI_MODEL=gemini-2.5-flash
   ```

5. Restart the server so the key is loaded, then enable semantic analysis in the page.

The free tier has per-minute and per-day rate limits (they vary by model; see Google's current Gemini API pricing and rate-limit pages). On the free tier Google may use submitted content to improve its products, so avoid sending real CVs you are not comfortable sharing. When the key is set and semantic analysis is enabled, extracted CV text and any job description are sent to the Gemini API. Never commit your `.env` file.

## Run

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

bash (with the venv activated):

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). `GET /api/config` returns JSON and is a quick health check. Stop the server with Ctrl+C.

## Using it

1. Drop a PDF or DOCX (or pick a sample). Target title, career level, industry and job description are all optional.
2. **Overview** gives the score, the three separate verdicts (general quality, role suitability, competitiveness), the top weaknesses and what to do next.
3. **Role targets** shows up to four role profiles your evidence fits, each with coverage, evidence depth, readiness, the competencies recruiters screen for, and the gaps to close. "Re-run the review for this role" rescores the CV against another role; the previous session is discarded.
4. **Elevation plan** lists writing upgrades with before/after examples from your CV, items to add now if true, and actions to begin, grouped into this week, the next 30 days and the next 90 days.
5. **Edits** is where you answer questions and accept, edit, reject or undo each suggestion. **Revised CV** previews and exports the result. Export is blocked while `[placeholders]` remain unless you confirm them.
6. **Reassess** rescores the revised CV with the same rubric and the same role.

## Testing

There are two layers: an offline suite that anyone can run straight after `pip install`, and an opt-in setup check that proves your own `.env` and Gemini key are hooked up.

### 1. Offline suite (no key, no network)

```powershell
.\.venv\Scripts\python.exe -m pytest        # PowerShell
```

```bash
python -m pytest                             # bash, venv activated
```

Settings live in `pytest.ini`. A fixture in `tests/conftest.py` blanks any configured key and replaces the Gemini client with a guard, so this suite never calls Google even if your `.env` has a real key. CI (`.github/workflows/tests.yml`) runs the same command on every push and pull request.

What it proves:

- `tests/test_engine.py`: the deterministic engine. Evidence tiers, ordering of the fictional CVs in `samples/`, quote anchoring, edits and export, document extraction failures, that a paraphrase does not raise the impact score, role and career-level inference, the elevation plan never inventing facts, and reassessment stability.
- `tests/test_llm_and_config.py`: configuration and the Gemini integration seam, using a fake client. `.env.example` documents every variable the code reads and ships no key; runtime credential overrides; `/api/config` reports state without leaking the key and rejects unsupported models; model JSON parsing; that the request is sent with the configured key, model and JSON mode; that a good model reply produces a hybrid report; and that invalid JSON, missing subscores or an SDK error all fall back to the deterministic rubric with a note. One `xfail` test records a known labelling issue (see below).

### 2. Check my setup (live, opt-in)

After you have copied `.env.example` to `.env` and added `GEMINI_API_KEY`:

```powershell
.\.venv\Scripts\python.exe -m pytest -m integration -v -rs     # PowerShell
```

```bash
python -m pytest -m integration -v -rs                           # bash
```

The checks in `tests/integration/test_setup_check.py` run in order:

1. **Environment loaded**: a key is configured, `GEMINI_MODEL` is one of the supported models and `MAX_UPLOAD_MB` is valid. It warns if `.env` leaves out keys from `.env.example` (they fall back to defaults).
2. **Provider reachable**: looks up the configured model with your key, then sends one tiny prompt ("Reply with the single word OK.") and expects a non-empty reply. A wrong key or model fails here with Google's error message.
3. **End to end**: runs a full hybrid review of the tiny bundled CV `tests/fixtures/tiny_cv.txt` and checks that the model was actually used (no fallback note), the engine and model are reported correctly, the score is 0 to 100 and equals the sum of the seven category scores, and there is a verdict and recommendations.

Steps 2 and 3 make two small Gemini calls (the free tier is fine), and step 3 sends the fictional tiny CV to Google. Without a key, all three are skipped with a message saying how to configure one.

Known issue recorded by the `xfail` test: if the model returns JSON with no usable subscores, the review correctly falls back to deterministic scores, but the report labels its engine "Hybrid ... reused semantic judgement" instead of "Deterministic".

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
