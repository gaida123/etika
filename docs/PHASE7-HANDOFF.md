# Handoff: finding cache, personas, and the Gemini call budget

Date: 2026-10-04. Branch: `main`. Scope of this document: everything done in the session that
landed Phase 3 and Phase 7, plus the open question it ended on (proving the per-run Gemini call
count) and the work queued behind it.

Read alongside `docs/Etika Agent Upgrade Plan - Gemini Call + Itdb.md`, which is the phase plan
this follows. Phase numbers below refer to that document.

---

## 1. Where the repo stands

Six commits pushed, `dc6773e..bf321f2`:

| hash | message |
|---|---|
| `75ea694` | `chore: ignore local scratch output and editor state` |
| `e329a71` | `fix(db): fall back to certifi when the TiDB CA bundle path is missing` |
| `c364902` | `feat(agents): reuse findings per requirement instead of re-asking Gemini` |
| `65def5a` | `feat(agents): give each specialist a named voice, at no extra cost` |
| `112a376` | `feat(frontend): show the three specialists on the dashboard` |
| `bf321f2` | `docs: add the agent upgrade plan and the Devpost writeup` |

Each commit is a working tree on its own — Phase 3 and Phase 7 were entangled in `base.py`,
`orchestrator.py` and `schemas.py`, so the Phase 7 parts were stripped out, Phase 3 was committed
and verified green on its own 111 tests, then Phase 7 was restored and committed.

Green: backend `125 passed` (111 before Phase 7, +14 persona tests). Frontend `tsc --noEmit` and
`eslint` both clean.

**Uncommitted and intentional** (section 4): `backend/app/core/llm.py`,
`backend/app/knowledge/embeddings.py`.

**Uncommitted and unrelated**: `frontend/package-lock.json` — 114 deleted `libc` metadata lines,
pure npm-version churn from a different machine. Left dirty on purpose; do not fold it into a
feature commit.

---

## 2. What Phase 3 changed (`c364902`)

A per-requirement finding cache. A cache hit bypasses Gemini completely.

The key is built from `Requirement.required_fact_keys` + the resolved applicability + jurisdictions
+ segment + `knowledge_base_version()` + `PROMPT_VERSION` + the model + the corpus review gates.
So changing a prompt, a model or the corpus invalidates old answers automatically rather than
silently serving stale ones.

On a hit, the cached chunks are **re-registered on the current run** before the finding is returned,
so the strict citation filter ("only chunks retrieved in this run may be cited") still runs against
a hit exactly as it does against a fresh answer. This is the subtle part — skipping it would let a
cached finding cite a chunk the run never saw.

`PROMPT_VERSION` is now `"p7-persona-1"`. Persona is deliberately **not** in the cache key:
findings are cached neutral and the voice is applied separately, so adding or revising a persona
never splits the cache.

---

## 3. What Phase 7 changed (`65def5a`, `112a376`)

Three named specialists. The design constraint was that persona must cost nothing and must not be
able to change a single fact.

### The three

| agent | handle | role | specialises in |
|---|---|---|---|
| `registration` | **The Registrar** | Registration & licensing | BC Registries name registration, the City of Vancouver business licence, CRA business number |
| `tax` | **The Counter** | Sales tax thresholds | BC PST and GST/HST registration, the small seller and small supplier tests, how close revenue is to each threshold |
| `employer` | **The Foreman** | Hiring & payroll | WorkSafeBC, CRA payroll account, minimum wage, pay statements, payroll records, employee vs contractor |

### How it is kept safe

Persona shapes **exactly one field**: `AgentReport.summary`. Status, score, scope, columns and
progress are still decided by code alone. Three guardrails, all enforced in code
(`backend/app/agents/personas.py`):

1. **Banned phrases.** A global list (`guarantee`, `fully compliant`, `as your lawyer`,
   `legal advice`, `i promise`, …) plus a per-persona list (The Registrar may not say
   "you're registered"; The Counter may not say "you owe" or "tax-free"; The Foreman may not say
   "nobody checks" or "just pay cash").
2. **No invented figures.** Every number and every month name in the summary must already appear in
   that run's findings or calculator results. `MONTH_RE` deliberately omits "may" and "march" —
   as bare words they are far more often English than dates, and a real date carries a day or year
   that rule 2 already catches.
3. **Reject means template, never retry.** A failing summary is replaced by the persona's
   code-written template line and a `persona_voice` entry is logged to the trace. No second Gemini
   call is ever made to fix a voice. This is what makes the feature free.

`_set_summary` in `backend/app/agents/base.py:303` is the single place this is applied. A run where
every finding came from the cache made zero Gemini requests, so there is no voiced line to check
and the template is written instead — the persona is still present at 0 requests
(`summary_source: "template"`).

### Frontend

- `PersonaCards.tsx` — a "Who checked your business" section with a Full/Plain toggle, the voiced
  line, the requirement count and an "N unchanged since your last check" pill driven by
  `cached_findings`.
- `icons.tsx` — three chibi avatars built from shared `Shoulders`/`Head`/`Face` primitives, keyed
  off `persona.avatar` (`registrar` = spectacles + bow tie, `counter` = accountant's eyeshade,
  `foreman` = hard hat + hi-vis stripes). **Never visually verified** — the preview screenshot tool
  failed three times and this was explicitly waived. Worth one look.
- `Dashboard.tsx` — each area group header shows its specialist's chibi and handle.
- `demo.ts` carries matching persona and summary data so the demo mode still type-checks.

---

## 4. Uncommitted: the request log ("Phase 0-lite")

**The problem.** There are two paths that spend Gemini quota and **neither logged anything**:

- `backend/app/core/llm.py::generate_content` — every generation. Retries up to 4 attempts on
  429/503, so retries silently inflate the real request count above the logical one.
- `backend/app/knowledge/embeddings.py::embed_many` → `client.models.embed_content` — query
  embeddings for retrieval. A second, easily forgotten quota consumer.

So the call count could only be *inferred* from the trace, never proven.

**The change.** A module-level counter plus a `count_request(kind, model)` helper in `llm.py`,
called at both chokepoints. Three lines of behaviour:

```
INFO app.core.llm gemini request #1 kind=embed model=gemini-embedding-001
INFO app.core.llm gemini request #2 kind=generate model=gemini-3.5-flash
```

This is the only part of Phase 0 actually needed to answer "how many calls was that?". The full
Phase 0 DB ledger (per-request rows, cost attribution, before/after tables) is still unbuilt and
is still worth building for the Devpost numbers — but it is not a prerequisite for testing.

**Caveat for whoever runs the server.** The app configures no logging, and uvicorn's default log
config gives the root logger no handler, so app-level INFO never prints. Start the backend through
a wrapper that calls `logging.basicConfig(level=logging.INFO)` first, or add a `basicConfig` to
`app/api/main.py`. Also note the ASGI path is `app.api.main:app`, not `app.main:app`.

---

## 5. The call budget, honestly

This is the part that needs a decision. **Phase 8 is not required to test** — it only smooths
bursts so the free tier's 5 req/min wall is not hit. Without it a burst can 429 and retry, which
*inflates* the count, which is itself useful to observe.

Measured structure of a cold run, from the code:

| step | requests |
|---|---|
| prefetch retrieval, per agent | 1 `embed` (all of that agent's queries are batched into one embedding call) |
| report, per agent | 1 `generate` |
| **cold run, no escalation** | **3 embed + 3 generate = 6** |
| per escalating agent | +2 `generate` investigate turns, +1 `generate` re-report, +≥1 `embed` |

`default_queries` produces 2 queries per requirement (13 requirements → 26 queries), but
`RetrievalService.retrieve_many` coalesces them into one embedding call per agent, so the query
count does not drive cost.

**The ceiling is genuinely at risk.** Escalation targets are
`(low-confidence findings | requirements with no chunks) & in_pack`
(`base.py:359`) — so **any requirement with zero retrieved chunks always escalates**. REG-02 has no
City-of-Vancouver corpus coverage, so registration escalates on every cold run.

- Best case, nothing escalates: **3 generate**, 6 billable requests.
- Expected, registration escalates: **6 generate**, ~10 billable requests.
- Two agents escalate: **9 generate** — over the target.

So "3-6" holds for generation calls if and only if at most one agent escalates. Fixing the REG-02
corpus gap is the single highest-leverage change for the call budget, because it removes the one
escalation that fires every single time.

---

## 6. The test as set up

Prior instances were killed (frontend PID 24132 on :3000, backend PID 29576 on :8000) and one
fresh pair started. Backend `USE_STUBS=false`, live Gemini, `agent_mode=prefetch`,
`finding_cache_enabled=true`, logging to `tmp/backend.log`.

**The cache is confirmed cold.** `finding_cache` holds 25 rows, all at `p2-prefetch-1`; nothing at
`p7-persona-1`. The next run is a genuine first run. Do not run an assessment "just to check" —
it warms the cache and destroys the measurement.

### Intake data

Chosen so that the first run determines as many facts as possible, which puts two of the three
personas on the model-voiced path and one on the template path — covering both branches of
`_set_summary` in a single run.

**Step 1 — Business basics**

| field | value |
|---|---|
| Business name | `Maya Makes` |
| What kind of business is it? | Handmade or crafted goods |
| How is the business set up? | Sole proprietorship |
| City | City of Vancouver (locked) |
| Street address | `1455 Quebec St` |
| Where do you run it from? | From home |
| Are you open yet? | Already open |

**Step 2 — What you do**

| field | value |
|---|---|
| Activities | **Make or sell products** and **Sell at markets, fairs or pop-ups** (both, nothing else) |
| Does anyone besides you work in the business? | **Not yet, but planning to hire** → month `March 2027` |
| Do you sell online? | Marketplaces like Etsy or Amazon |
| Sales in the past 12 months | `$10,000 to $30,000` |
| Website / documents | leave empty |

The two activity choices matter: `markets` is what sets `online_only = false`, and
"planning to hire" is what sets `plans_to_hire = true`. Without them REG-02 and all six EMP
requirements come back undetermined and the run tests much less.

**Step 3 — Check our understanding**

| question | answer |
|---|---|
| Will you trade under a name other than your own legal name? | **Yes** |

The GST question does not appear, because step 2 gave a sales band instead of "Not sure yet".
Confirm and start the check.

This posts: `operates_in_vancouver=true`, `home_based=true`, `sells="goods"`,
`sells_at_recurring_markets=true`, `online_only=false`, `has_employees=false`,
`plans_to_hire=true`, `planned_hire_date="2027-03"`,
`trading_name_differs_from_legal_name=true`, `trading_name="Maya Makes"`.
Sales band is **not** a fact key and is not sent, so `monthly_revenue` is unknown on run 1.

### Expected result, run 1

- 13 requirements: 3 registration, 4 tax, 6 employer.
- `cached_findings` **0 / 0 / 0** on all three agents. Any non-zero means the cache was already
  warm and the measurement is void.
- **The Registrar** — REG-01, REG-02, REG-03 all resolved; `summary_source: "model"`, a voiced
  line naming a real requirement, no invented numbers.
- **The Foreman** — six employer requirements in `pre_hire` mode (because `plans_to_hire=true`,
  `has_employees=false`); `summary_source: "model"`.
- **The Counter** — all four tax requirements **undetermined**, because `monthly_revenue` is
  unknown; so `summary_source: "template"` and the `undetermined` template line. This is correct
  behaviour, not a bug.
- Follow-up questions offered: `online_only` (no — already set), `has_established_premises`,
  `monthly_revenue`.
- `tmp/backend.log`: expect 3 `kind=embed` + 3 `kind=generate`, plus 3 more `generate` and at least
  1 more `embed` if registration escalates on REG-02. Grep `gemini request`; the highest `#N` is
  the total.

### Stage 2 — proves the cache

On the dashboard, answer the remaining questions:

- Do you have a dedicated store, office or other business premises outside your home? → **No**
- Monthly gross sales, 12 months → `600, 750, 800, 950, 1100, 1250, 1400, 1600, 1850, 2100, 2400, 2800`
  (total **$17,600** — under the $30,000 small-supplier threshold but trending toward it, which is
  exactly what The Counter is supposed to talk about).

Note that answering a fact triggers a **full new assessment** (`BusinessProvider.tsx:167`). That is
the point: registration and employer facts did not change, so those agents should come back with
`cached_findings` 3 and 6, `tool_calls` 0, `summary_source: "template"`, and **zero** new
`generate` lines in the log. Only tax should re-ask Gemini — one `generate` call. If stage 2 costs
more than about 1 generate call, the cache key is too sensitive and that is the bug to chase.

---

## 7. Queued work, in priority order

1. **REG-02 corpus gap.** No City-of-Vancouver business-licence coverage, so REG-02 has zero
   chunks, so registration escalates on every cold run — 3 extra generation calls every time, and
   it is the only thing standing between the run and the ≤6 target. Fix the corpus, not the
   escalation threshold.
2. **Phase 8: rate limit hardening.** An asyncio token bucket at 4 requests per rolling 60s,
   priority lanes (chat > report > escalation > scripts), retries routed through the limiter rather
   than around it, and `scripts/demo_prewarm.py`. Keep the 503 fallback to the backup model but log
   `model_used`. Not needed to measure anything; needed so a live demo does not 429.
3. **Duplicate source links** from `orchestrator._enrich` — known, still unfixed, visible in the UI.
4. **Phase 0 proper.** The DB ledger, for real before/after numbers in the writeup. The log from
   section 4 is a stopgap, not a replacement.
5. **Verify the chibis render.** They have never been looked at.

---

## 8. Invariants not to break

These held before this work and still hold. Anything that violates one is a bug regardless of how
good it looks.

- Status, score, scope, columns and progress are decided by **code only**. Gemini never decides
  applicability.
- Only chunks retrieved — or deliberately re-registered — **in the current run** may be cited.
- An unknown fact is `known=false`. It is **never** `false`. Unanswered intake questions are
  omitted from the profile rather than sent as false.
- Persona shapes `summary` and nothing else.
- Tests use `tests/fake_gemini.py`. Never live Gemini.
- Exactly one Gemini generation call per agent in the happy path, and at most one escalation round
  per agent run.
