# Etika: Compliance Navigator

Compliance navigator for new Vancouver, BC sole proprietors. Spec: [`docs/HANDOFF.md`](docs/HANDOFF.md).

## Layout

```text
backend/app/contracts/   Shared Pydantic contracts (Dev 1 + Dev 2)
backend/app/knowledge/   Dev 1: TiDB retrieval + registry
backend/app/assessment/  Dev 1: deterministic applicability, calculators, scoring
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
- `PATCH /profile/{business_id}`: save owner-confirmed dashboard answers as a new profile version; send raw `facts` values and/or monthly revenue entries
- `POST /intake/parse`: free text to proposed (unconfirmed) facts; with `business_id` it also stores a proposal
- `POST /profile/{business_id}/confirm-update`: apply accepted/edited facts from a proposal as a new version
- `POST /assess/{business_id}[?version=N]`: run the three agents; returns score, now/next/later, findings. If any agent fails, the last full result for the same facts is returned with `cached=true`
- `GET /assessments/{assessment_id}/trace`: every agent tool call (the "agent trace")
- `GET /requirements/{requirement_id}`: registry entry (incl. action link) plus supporting evidence
- `GET /profile/{business_id}/questions`: follow-up questions for facts that block a decision
- `POST /chat`: grounded answer from one routed agent; new facts mentioned come back as a proposal to confirm
- `POST /draft-email`: creates an unsent, deterministic inquiry draft from a saved profile and registry requirement; it never sends email

## Front end

```powershell
cd frontend
npm ci
npm run dev
```

The browser app runs on http://127.0.0.1:3000 and proxies `/api/*` to
`http://127.0.0.1:8000` by default. For deployment, set `API_URL` to the
public HTTPS backend URL in the frontend host's environment. Run `npm run build`
before deploying; `npm run lint` is the quick local type/style gate.

## Smoke checks

Run from `backend/`:

```powershell
python scripts/smoke_retrieval.py      # live TiDB vector retrieval; read-only
python scripts/smoke_assess.py         # full Maya API flow with the configured service bundle
python scripts/smoke_assess.py --hire  # persist a confirmed first hire, then assess
```

`smoke_workflow.py`, `warm_demo_cache.py`, and `POST /dev/load-demo` are retained
as stub-only helpers; they are intentionally unavailable when `USE_STUBS=false`.

Tables are created automatically on startup. With the default `DATABASE_URL=sqlite:///./reegal.db`
nothing else is needed. For TiDB, copy the Console's PyMySQL URI into `backend/.env`; it uses
`mysql+pymysql://<instance-prefix>.root:<url-encoded-password>@<host>:4000/<database>` and may include
`ssl_ca`, `ssl_verify_cert=true`, and `ssl_verify_identity=true`. TLS is verified automatically.

Verify the TiDB connection, negotiated TLS, and current schema bootstrap without making a Gemini call:

```powershell
python scripts/smoke_db.py
```

For staged testing of the live TiDB corpus while the other Developer 1 services remain stubs, set
`USE_TIDB_RETRIEVAL=true` in `backend/.env` and run `python scripts/smoke_retrieval.py`. To use the
backfilled Gemini/TiDB semantic path, also set `USE_TIDB_SEMANTIC_RETRIEVAL=true`. The one-time setup
commands are `python scripts/migrate_vector_schema.py --apply`, then
`python scripts/backfill_embeddings.py --apply`, then
`python scripts/migrate_vector_schema.py --apply --create-index`. Do not set `USE_STUBS=false` until
the real registry, applicability, calculator and scoring services are wired.

To run the real Phase 1 service bundle, load the registry first:

```powershell
python scripts/load_registry.py --apply
```

Then set `USE_STUBS=false`. Production exposes only registry rows marked `approved`; the current
demo registry is deliberately enabled through `ALLOW_DRAFT_REGISTRY=true` in the local environment.
Draft `TODO-*` action URLs are stored as unavailable (`null`) so the UI must disable their action
button. `REG-02` (Vancouver business licence) remains an intentional `insufficient_evidence` gap
until an official City of Vancouver source is ingested and mapped.

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
