# Etika: Compliance Navigator

Compliance navigator for new Vancouver, BC sole proprietors. Spec: [`docs/HANDOFF.md`](docs/HANDOFF.md).

## Layout

```text
backend/app/contracts/   Shared Pydantic contracts (Dev 1 + Dev 2)
backend/app/knowledge/   Dev 1: retrieval + registry (stubs only for now)
backend/app/assessment/  Dev 1: applicability, calculators, scoring (stubs only for now)
backend/app/intake/      Dev 2: profile versioning, intake
backend/app/agents/      Dev 2: orchestrator + agents
backend/app/chat/        Dev 2: chat + citation validation
backend/app/actions/     Dev 2: checklists, email drafts
backend/app/api/         Dev 2: FastAPI routes
backend/app/core/        Settings, DB, Gemini wrapper, service factory
backend/data/registry/   requirements.json (draft rows)
backend/scripts/         Loader scripts
backend/tests/           Pytest suite
contracts/examples/      Example JSON (Maya demo persona)
```

## Setup (Windows PowerShell)

Python 3.11+ is required.

```powershell
cd backend
py -3.11 -m venv .venv          # or any Python >= 3.11
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env     # then set GEMINI_API_KEY (and DATABASE_URL for TiDB)
```

macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, then the same `pip` and `cp .env.example .env`.

## Run

```powershell
cd backend
uvicorn app.api.main:app --reload
```

- API docs: http://127.0.0.1:8000/docs
- `GET /health`: liveness
- `GET /health/gemini`: one tiny structured Gemini call (needs `GEMINI_API_KEY`)
- `POST /profile`, `GET /profile/{business_id}[?version=N]`
- `POST /intake/parse`: free text to proposed (unconfirmed) facts; with `business_id` it also stores a proposal
- `POST /profile/{business_id}/confirm-update`: apply accepted/edited facts from a proposal as a new version
- `POST /assess/{business_id}[?version=N]`: run the three agents; returns score, now/next/later, findings
- `GET /assessments/{assessment_id}/trace`: every agent tool call (the "agent trace")
- `GET /requirements/{requirement_id}`: registry entry (incl. action link) plus supporting evidence

Live smoke scripts (real Gemini, stub knowledge base), run from `backend/`:

```powershell
python scripts/smoke_workflow.py      # health, intake, confirm-update
python scripts/smoke_assess.py        # full Maya assessment
python scripts/smoke_assess.py --hire # with a confirmed first hire (demo climax)
```
- `POST /dev/load-demo`: loads Maya from `contracts/examples/maya_profile.json` (only when `USE_STUBS=true`)

Tables are created automatically on startup. With the default `DATABASE_URL=sqlite:///./reegal.db`
nothing else is needed; for TiDB use `mysql+pymysql://user:pass@host:4000/db` (TLS is enabled automatically).

## Test

```powershell
cd backend
pytest
```

Tests use in-memory SQLite and never call Gemini.

## Stubs

With `USE_STUBS=true`, `app.core.services.get_services()` returns placeholder versions of Developer 1's
services (`app/knowledge/stubs.py`, `app/assessment/stubs.py`). All stub evidence is fake and every
registry `action_url` is `TODO-official-url` until the research owner fills in reviewed values.
