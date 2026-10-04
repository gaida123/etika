# Etika: Legal Team, Decoded.

> **Code decides. Gemini explains.**
> A compliance navigator for new Vancouver, BC sole proprietors: three specialist AI agents check your situation against official government sources and tell you what applies to *you*, why, and what to do next.

---

## Inspiration

A friend spent a whole weekend working out whether her candle business needed to register for PST. Four government sites, a Reddit thread and a phone call later, the answer was "not yet, but close." Compliance information isn't missing, it's **fragmented**: BizPaL lists permits that *may* apply, Ownr only registers a name, and an accountant only knows what you tell them. Nobody says what applies to you, why, and what to do next, and the thresholds move underneath you the whole time.

So we built Etika.

**Under the hood, Etika is a RAG pipeline we built ourselves on TiDB:** we scraped and curated official data from multiple government sources (BC Registries, the CRA, BC Ministry of Finance, WorkSafeBC, the BC Employment Standards Branch and BC Laws), chunked and embedded it into TiDB's vector store, and every answer is retrieved from it and cited back to the source.

---

## What is Etika?

You answer a short intake. Three specialist agents (**Registration**, **Tax** and **Employer**) check your answers against a corpus of official BC and federal sources and return:

- a **requirement-by-requirement check** (13 requirements today) with a plain-English explanation and the official sources behind it,
- a **Now / Next / Later** plan, each item linked to the real government page,
- **threshold tracking** for BC PST and GST, including how close your sales are and when you're projected to cross,
- a **grounded chat** ("Ask etika") that answers only from those sources, and says so when it can't.

Mention a change in chat, like *"I've hired a helper"*, and Etika **proposes** a fact update. Confirm it and the whole assessment re-runs: the five employer obligations flip from Later to Now.

---

## Features

- 🧭 **3-step intake**: business basics, what you do, and a "check our understanding" review. Only questions you actually answered become facts.
- ✅ **Compliance dashboard**: progress, "do this next", open questions, the three specialists, and every requirement grouped by area as collapsible sections with the official source on each row.
- 🧑‍🤝‍🧑 **Three named specialists**: *The Registrar*, *The Counter* and *The Foreman*, each with an avatar and a voice, and a Full/Plain toggle that hides the voiced lines.
- 💬 **Ask etika**: a framed chat with a scrolling conversation, a pinned input, a live sources panel, and an in-chat card when an answer depends on a fact we don't have yet.
- 🔁 **Confirm-before-change**: the model can *propose* new facts from chat, but nothing changes your profile without your OK.
- 📈 **Rolling-window thresholds**: PST's $10,000 small-seller test uses a rolling 12 months, GST's $30,000 small-supplier test uses four consecutive quarters, both with a straight-line crossing projection.
- 🔍 **Agent trace**: a collapsible record of every tool step the agents took for an assessment.
- 🚦 **Honest gaps**: when no official source supports a claim, the answer says so instead of guessing.
- ⚡ **Cheap to run**: a first check is about one Gemini call per agent, a repeat check with the same facts costs none, and a built-in rate limiter smooths bursts.
- 🎬 **Demo mode**: `/b/demo` runs on local sample data with no backend.

---

## How it works

```
 Intake wizard (Next.js)
        │  facts the owner confirmed (unanswered ≠ false)
        ▼
 FastAPI ──► versioned business profile in TiDB
        │
        ▼
 Deterministic engine (pure Python, no model)
   applicability · PST/GST calculators · scoring · Now/Next/Later
   decides WHICH requirements apply and their status
        │
        ▼
 Orchestrator ── splits the 13 requirements by area and launches all 3 agents at once
        │
        ├───────────────────────────┬───────────────────────────┐
        ▼  (in parallel)            ▼                           ▼
 ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
 │ REGISTRATION AGENT  │  │      TAX AGENT      │  │    EMPLOYER AGENT   │
 │ "The Registrar"     │  │   "The Counter"     │  │    "The Foreman"    │
 │ REG-01 · 02 · 03    │  │ TAX-01 · 02 · 03 ·04│  │ EMP-01 · 02 · 03 ·  │
 │ (3 requirements)    │  │ (4 requirements)    │  │ 04 · 05 · 06 (6)    │
 │                     │  │                     │  │                     │
 │ 1 cache check       │  │ 1 cache check       │  │ 1 cache check       │
 │ 2 TiDB retrieval    │  │ 2 TiDB retrieval    │  │ 2 TiDB retrieval    │
 │ 3 ONE Gemini call   │  │ 3 ONE Gemini call   │  │ 3 ONE Gemini call   │
 │ 4 citation filter   │  │ 4 citation filter   │  │ 4 citation filter   │
 └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘
            └────────────────────────┼────────────────────────┘
                                     ▼  (results merged)
 Assessment: score · Now/Next/Later · findings · sources · specialist summaries ──► dashboard
                                     │
                                     ▼
 Ask etika: route to ONE agent → retrieve → ONE Gemini call → citation filter
            → answer (+ any proposed facts, which you confirm)
```

### Meet the agents

The three agents are independent and run **concurrently**, so a check takes about as long as the slowest agent, not the sum of all three. Their launches are offset by a few seconds to avoid a burst against Gemini's shared capacity, and every Gemini call goes through the shared rate limiter.

| Agent | Persona | Owns | What it does | Official sources it reads |
|---|---|---|---|---|
| **Registration agent** | The Registrar | REG-01 business name, REG-02 City of Vancouver licence, REG-03 CRA business number | Explains which registrations you need and in what order, and why | BC Registries, CRA business number pages |
| **Tax agent** | The Counter | TAX-01 BC PST, TAX-02 GST, TAX-03 voluntary GST, TAX-04 charging tax | Reports the PST and GST threshold results the calculators produced, and how close your sales are, with any crossing month labelled an estimate | BC Ministry of Finance, CRA |
| **Employer agent** | The Foreman | EMP-01 WorkSafeBC, EMP-02 CRA payroll, EMP-03 minimum wage, EMP-04 pay statements, EMP-05 payroll records, EMP-06 employee vs contractor | Explains what to set up before a first hire, or what applies now if you already have staff | WorkSafeBC, CRA, BC Employment Standards Branch, BC Laws |

Every agent runs the same four steps:

1. **Cache check.** A requirement whose facts, applicability, corpus revision, prompt and model are all unchanged is answered from the finding cache with **no Gemini call**.
2. **Retrieval.** For the rest, code searches TiDB for evidence on each requirement. All of an agent's queries go out in one batched embedding call.
3. **One Gemini call.** The agent writes a cited explanation for each remaining requirement. It never decides applicability, status or numbers.
4. **Citation filter.** Any claim citing a chunk that wasn't retrieved in this run is dropped.

Each agent also writes one voiced `summary` line in its persona's manner. Personas change wording only, never a status, score or source.

### The core rule: code decides, Gemini explains

Everything that could be wrong in a way that matters is **deterministic Python**:

- **Applicability.** Whether a requirement applies is decided by rules over your facts, never by the model.
- **Status, score and the Now/Next/Later columns** come from code. The same facts always produce the same score, so you can't talk Etika into a wrong answer.
- **Thresholds** are calculated in code. The model is handed the numbers and told to report them exactly.
- **Unknown is never false.** A fact you haven't answered is `known=false`. It blocks a decision and triggers a follow-up question instead of silently counting as "no".

Gemini only ever writes the **human-facing explanation** of evidence that code already retrieved and validated.

### The rules engine

| Requirement | Applies when |
|---|---|
| REG-01 Register your business name | you trade under a name other than your legal name |
| REG-02 City of Vancouver business licence | you operate in the City of Vancouver |
| REG-03 CRA business number | GST registration or a payroll account is required or coming up |
| TAX-01 Register for BC PST | you sell goods and fail the **small seller test** (over $10,000 in a rolling 12 months, *or* you have established premises) |
| TAX-02 Register for GST | you fail the **small supplier test** (over $30,000 in any single quarter or in four consecutive quarters) |
| TAX-03 Voluntary GST registration | you're under the GST line (a recommendation, not an obligation) |
| TAX-04 Charge and show tax on invoices | PST or GST registration applies |
| EMP-01 to EMP-05 WorkSafeBC, CRA payroll account, minimum wage, pay statements, payroll records | you have employees (now) or plan to hire (upcoming) |
| EMP-06 Employee vs contractor | a recommendation for anyone who has or plans to have workers |

Scoring only counts **required-now legal obligations**, weighted by the registry, with credit of 1.0 / 0.5 / 0 for done / in progress / not done. Employer obligations that only switch on at a first hire sit in **Later**. Items are sequenced by dependency and priority.

---

## The RAG pipeline

We built the whole source-to-citation process ourselves: a RAG pipeline on **TiDB**, fed by data we **scraped from multiple government sources**.

1. **Scrape and collect.** Official pages were scraped and curated from BC Registries, the CRA, BC Ministry of Finance, WorkSafeBC, the BC Employment Standards Branch and BC Laws.
2. **Chunk by legal section.** Each page is split along its section structure, keeping its `section_path`, authority, URL, effective dates and source version.
3. **Embed.** Every chunk is embedded with `gemini-embedding-001` (3,072 dimensions) and stored beside its metadata in **TiDB's vector column**, so relational filters and vector search share one store.
4. **Gate.** Retrieval only returns chunks that are current, effective on the date asked, mapped to the requirement being checked, and (outside the demo) marked **reviewed and approved** by the research owner. Nothing unreviewed is allowed to be cited in production mode.
5. **Search.** Queries are ranked by **cosine distance** inside TiDB. All of an agent's queries go out in **one batched embedding call**, and if Gemini embeddings are unavailable, retrieval **falls back to lexical ranking** rather than failing.
6. **Cite strictly.** A claim is kept only if every chunk ID it cites was retrieved **in the current run**. Anything else is dropped, and a finding left with no valid claim gets the standard "we couldn't find an official source" explanation, a flag and low confidence.
7. **Escalate, boundedly.** A finding with low confidence, or a requirement with no chunks, gets at most **one** extra investigate-and-re-report round per agent.

Current corpus: **240 chunks from 19 official pages** (CRA 136, BC Ministry of Finance 43, BC Registries 20, BC Employment Standards Branch 17, WorkSafeBC 13, BC Laws 11).

### Where the call budget goes

The first version let each agent run a Gemini tool loop, costing **8 to 15 requests per assessment**. We rebuilt it so code does the retrieval and the model only writes:

| Path | Gemini requests |
|---|---|
| Cold assessment | one generation per agent (3), plus one batched embedding call each; escalation adds a bounded extra round |
| Repeat with the same facts | **0** (every finding comes from the finding cache) |
| Answering one dashboard question | only the agents whose facts changed re-ask |
| One chat question | 1 embedding + 1 generation |

The **finding cache** is keyed on the requirement's facts, its resolved applicability, the corpus revision, the prompt version and the model, so changing a prompt, a model or the knowledge base invalidates old answers automatically. A cache hit re-registers its cached chunks on the current run, so the strict citation filter still applies to it.

A shared **rate limiter** keeps bursts from hitting 429s: every generation attempt, retries included, takes a slot from a rolling per-minute window (`GEMINI_RPM`), chat jumps the queue, a call that would wait too long fails with a clear "busy" message, and a 429 pauses everyone briefly. It is sized for an MVP or demo (one process, in memory).

### Specialist personas

Each agent has an original character, **The Registrar**, **The Counter** and **The Foreman**. A persona shapes **exactly one field**, the human-facing `summary`. It cannot change a status, score, scope or source, and three guardrails are enforced in code:

1. banned phrases (a global list plus per-persona ones: no "guarantee", "fully compliant", "you're registered", "you owe", "tax-free"),
2. no invented figures: every number and month in a voiced line must already appear in that run's findings or calculator results,
3. **reject means template, never retry**: a failing line is replaced by a code-written template, so personas cost no extra Gemini calls.

---

## What we built

- A **FastAPI backend** with versioned profiles, an intake parser, a deterministic rules engine, a three-agent orchestrator, grounded chat, an agent trace and a finding cache.
- A **RAG pipeline on TiDB**: data scraped from multiple government sources, chunked by legal section and embedded into **240 chunks from 19 official pages**, with a review-gated retrieval service, strict citation checking and a lexical fallback.
- A **Next.js frontend**: intake wizard, compliance dashboard, per-requirement pages, the Ask etika chat, specialist cards, an offline demo mode and a full set of favicons and app icons.
- A **Gemini request layer**: counting every billable request, retries through a shared rate limiter, and a fallback model after repeated 503s.
- **Tooling**: a registry loader, vector-migration and embedding-backfill scripts, smoke checks, and a **demo prewarm script**.
- **132 automated tests** that run on in-memory SQLite with a fake Gemini and never call the live API.

---

## Tech stack

### Backend
| Technology | Role |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI + Uvicorn | API server |
| Pydantic v2 | Contracts and validation |
| SQLAlchemy 2 + PyMySQL | Data access (TiDB over TLS, or SQLite locally) |
| `google-genai` | Gemini generation and embeddings |
| pytest + pytest-asyncio | Test suite |

### Data and AI
| Technology | Role |
|---|---|
| TiDB Cloud | Relational data and vector search in one store |
| Gemini Flash | Intake parsing, agent explanations, chat and the router fallback |
| `gemini-embedding-001` | 3,072-dimension chunk and query embeddings |
| Deterministic Python | Applicability, calculators, scoring, sequencing, citation validation |

### Frontend
| Technology | Role |
|---|---|
| Next.js 16 + React 19 | App framework (App Router) |
| TypeScript | Type safety |
| Tailwind CSS v4 | Styling |

---

## Repository layout

```text
backend/app/contracts/    Shared Pydantic contracts (facts, registry, assessment, retrieval, trace)
backend/app/knowledge/    TiDB retrieval, embeddings, registry loader, stub corpus
backend/app/assessment/   Deterministic applicability, calculators, scoring, sequencing
backend/app/intake/       Fact dictionary, profile versioning, intake parsing, follow-up questions
backend/app/agents/       Orchestrator, specialists, prefetch, finding cache, personas, tools
backend/app/chat/         Router, grounded answers, citation validation
backend/app/actions/      Checklists and unsent inquiry email drafts
backend/app/api/          FastAPI routes
backend/app/core/         Settings, database, Gemini wrapper and rate limiter, service factory
backend/data/registry/    requirements.json (the 13 requirements)
backend/scripts/          Loaders, smoke checks, demo prewarm
backend/tests/            Pytest suite
frontend/src/app/         Routes: intake, dashboard, requirement, Ask etika
frontend/src/components/  Intake wizard and business UI
contracts/examples/       Example JSON (the Maya demo persona)
docs/                     Spec, upgrade plan and handoffs, Devpost writeup
```

---

## Getting started

**Prerequisites:** Python 3.11+, Node 20+, a Gemini API key, and (optionally) a TiDB Cloud cluster. With the default settings Etika runs on local SQLite and stub data, so you can try it with no database at all.

### 1. Backend

```powershell
cd backend
py -3.11 -m venv .venv          # or any Python >= 3.11
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env     # then set GEMINI_API_KEY (and DATABASE_URL for TiDB)
uvicorn app.api.main:app --reload
```

macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, then the same `pip` and `cp .env.example .env`.

- API docs: http://127.0.0.1:8000/docs
- To see every Gemini request, start through a wrapper that calls `logging.basicConfig(level=logging.INFO)` first, because the app configures no logging itself.

### 2. Frontend

```powershell
cd frontend
npm ci
npm run dev
```

The app runs on http://localhost:3000 and proxies `/api/*` to `http://127.0.0.1:8000`. For deployment set `API_URL` to the public backend URL. Open `/b/demo` for a backend-free preview on sample data.

### 3. Environment variables (`backend/.env`)

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `sqlite:///./etika.db` locally, or the TiDB `mysql+pymysql://...` URI (TLS is verified automatically) |
| `GEMINI_API_KEY` | Required for live runs |
| `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL` | Generation model, and the backup used after repeated 503s |
| `GEMINI_EMBEDDING_MODEL`, `GEMINI_EMBEDDING_DIMENSIONS` | Must match the TiDB `VECTOR(D)` column |
| `GEMINI_RPM`, `GEMINI_MAX_WAIT_SECONDS` | Rate limit (requests per rolling minute, 0 = off) and the longest a call waits for a slot |
| `USE_STUBS` | `true` uses placeholder services and fake evidence; `false` uses the real engine and corpus |
| `AGENT_MODE` | `prefetch` (code gathers evidence, one call per agent) or `legacy` (Gemini tool loop) |
| `ESCALATION_ENABLED` | One bounded extra round for weak findings |
| `USE_TIDB_RETRIEVAL`, `USE_TIDB_SEMANTIC_RETRIEVAL` | Read the real corpus, and rank it by vector distance |
| `ALLOW_UNREVIEWED_KNOWLEDGE`, `ALLOW_CANDIDATE_REQUIREMENT_MAPPINGS`, `ALLOW_DRAFT_REGISTRY` | Demo-only gates. Keep `false` in production |

### 4. Going live on the real corpus

Run from `backend/`:

```powershell
python scripts/smoke_db.py                                  # TiDB connection, TLS and schema, no Gemini call
python scripts/migrate_vector_schema.py --apply             # one-time vector schema
python scripts/backfill_embeddings.py --apply               # embed every stored chunk
python scripts/migrate_vector_schema.py --apply --create-index
python scripts/load_registry.py --apply                     # load the 13 requirements
```

Then set `USE_STUBS=false`, `USE_TIDB_RETRIEVAL=true` and `USE_TIDB_SEMANTIC_RETRIEVAL=true`.

### 5. Preparing a demo

```powershell
python scripts/demo_prewarm.py          # fills the finding cache for the demo scenarios
python scripts/demo_prewarm.py --chat   # also smoke-tests the demo chat questions
```

It builds the demo business the way the app does, runs each scenario cold, then re-runs it and checks the repeat costs **0** generation requests. Re-run it after changing prompts, models or the corpus, since each of those invalidates the cache on purpose.

### 6. Tests and checks

```powershell
cd backend && pytest                    # 132 tests, in-memory SQLite, never calls Gemini
cd frontend && npx tsc --noEmit && npm run lint
python scripts/smoke_assess.py          # full Maya API flow with the configured services
python scripts/smoke_assess.py --hire   # persist a confirmed first hire, then assess
python scripts/smoke_retrieval.py       # live TiDB retrieval, read-only
```

---

## API

- `GET /health`, `GET /health/gemini`: liveness, and one tiny structured Gemini call
- `POST /profile`, `GET /profile/{business_id}[?version=N]`: versioned business profiles
- `PATCH /profile/{business_id}`: save owner-confirmed dashboard answers (facts and/or monthly sales) as a new version
- `POST /intake/parse`: free text to proposed, unconfirmed facts
- `POST /profile/{business_id}/confirm-update`: apply accepted or edited facts from a proposal as a new version
- `GET /profile/{business_id}/questions`: follow-up questions for facts that block a decision
- `POST /assess/{business_id}[?version=N]`: run the three agents; returns the score, now/next/later, findings and specialist summaries. If an agent fails, the last full result for the same facts is returned with `cached=true`
- `GET /assessments/{assessment_id}/trace`: every agent tool step
- `GET /requirements/{requirement_id}`: registry entry with its action link and supporting evidence
- `POST /chat`: grounded answer from one routed agent; facts you mention come back as a proposal to confirm
- `POST /draft-email`: an unsent, deterministic inquiry draft from a saved profile; it never sends email

---

## Known limitations

- **The corpus is awaiting formal review.** All 240 chunks are marked `pending_research_owner_review`. The demo runs with the review gates relaxed through the `ALLOW_*` flags. A production launch needs the research owner to review and approve each source first.
- **No City of Vancouver licence source yet.** REG-02 has no official City source, so it shows as an honest `insufficient_evidence` gap, and chat answers about a home-based licence are hedged. Closing it also removes an extra Gemini round on every cold run.
- **A stale minimum-wage figure in the corpus.** The BC Employment Standards Act text still states $16.75, while the government minimum-wage page states the current $18.25. The Act figure should be marked superseded.
- **Scope is narrow on purpose.** Vancouver sole proprietors only; 13 requirements across registration, tax and employer obligations. Food safety, liquor, zoning, signage, incorporated businesses and other cities are not covered.
- **No accounts yet.** A business is identified by the ID in its URL, and the rate limiter is single-process. Both are fine for an MVP or demo, not for production.

---

## Challenges

- **The law was harder than the code.** PST's exemption depends on a *rolling* 12-month window, not a calendar year, so one good month can flip your status.
- **Building the knowledge base from scratch.** We collected the official pages, chunked them by legal section, and gated every chunk behind a review status before it could be cited.
- **Keeping the model on a leash.** The hard part was narrowing each agent so it could only answer from retrieved evidence and nothing else, so Gemini never filled a gap with something that sounded right but wasn't sourced.
- **Three parallel agents burned through Gemini's rate limit.** That pushed us to rebuild the pipeline so code prefetches evidence and each agent makes one call, then add a finding cache and a rate limiter.

## What we learned

Reliability came from deciding what the model is *not* allowed to do. Moving applicability, scoring and thresholds into code, validating every citation after the fact, and treating "unknown" as its own state made the system predictable, and made it cheaper at the same time.

## What's next

- Pre-filled government forms generated from the saved profile
- Auto-generated policy documents (privacy, refund, workplace)
- A renewal and deadline calendar
- Per-business agent memory and a "what changed since last time" view
- City of Vancouver licence coverage, and expansion to other BC cities and business structures

---

## Documentation

- [`docs/HANDOFF.md`](docs/HANDOFF.md): the original spec
- [`docs/Etika Agent Upgrade Plan - Gemini Call + Itdb.md`](docs/Etika%20Agent%20Upgrade%20Plan%20-%20Gemini%20Call%20+%20Itdb.md): the phased plan for cutting Gemini usage
- [`docs/PHASE7-HANDOFF.md`](docs/PHASE7-HANDOFF.md): finding cache, personas and the call budget
- [`docs/DEVPOST.md`](docs/DEVPOST.md): the project writeup
