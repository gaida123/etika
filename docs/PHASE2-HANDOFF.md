# Phase 2 handoff: prefetch + single-call agents

**Branch:** `feat/phase2-prefetch-single-call-agents` · **Owner:** Developer 2 · **Status:** done, 78 tests green
**Reader:** Developer 1 (Phase 1, TiDB hybrid search). **Q1-Q9 are answered and applied.**

> Developer 1's decisions are in `PHASE2-ANSWERS.md`. Every one of them is now reflected in the code
> on this branch; §5 below records each answer and the change it caused. What Phase 1 still owes
> Phase 2 is in §7.

---

## 1. What landed

Code now gathers all the evidence an agent needs ("prefetch"), then each agent makes **exactly one**
`generate_structured` call to write its findings. The Gemini tool loop survives only as a bounded
escalation path for weak findings, and as the chat path (unchanged).

| Flow | Before | After | Proven by |
| --- | --- | --- | --- |
| First assessment (3 agents in scope) | 8-15 requests | **3** | `test_first_run_three_calls` |
| Prefetch itself | n/a | **0** | `test_prefetch_makes_no_llm_calls` |
| Retrieval calls per agent | 1 per query | **1 batch** | `test_prefetch_batches_the_whole_scope` |
| Low-confidence agent | n/a | +1 round, capped | `test_escalation_bounded` |
| Chat question | 3-5 | unchanged | existing `test_chat.py` |

Nothing about *decisions* moved to Gemini. Status, score, scope, Now/Next/Later, citations and
threshold progress are still computed in code, from applicability and the calculators.

## 2. Your files were not touched

```
$ git diff --name-only main...HEAD
backend/.env.example
backend/app/agents/base.py
backend/app/agents/models.py              (new)
backend/app/agents/retrieval_adapter.py   (new)
backend/app/agents/tools.py
backend/app/core/settings.py
backend/tests/conftest.py
backend/tests/fake_gemini.py
backend/tests/test_agents.py
backend/tests/test_prefetch.py            (new)
```

(Plus `docs/PHASE2-ANSWERS.md` and this file.) Untouched: `app/knowledge/*` (retrieval + registry
stubs), `app/contracts/*` (including `services.py`, where your `retrieve_many` and
`knowledge_base_version` go), `app/assessment/stubs.py`
(applicability, calculators, scoring), `data/registry/requirements.json`, every seed/embedding path.
**Your branch and mine should merge without a single conflict** unless you edit `agents/` or `tests/`.

## 3. File-by-file

| File | What it does |
| --- | --- |
| `agents/models.py` | `RequirementEvidence` (requirement_id, read-only applicability, details, gray_areas, chunks, relevant_facts) and `EvidencePack` (agent, mode, requirements, calculators, profile_summary) |
| `agents/retrieval_adapter.py` | Maps your `RetrievedChunk` onto the frozen `Chunk` contract. Holds `kb_version()`, `CHUNKS_PER_REQUIREMENT = 6`, `default_queries()` and `fact_keys()` |
| `agents/base.py` | `prefetch()`, `_report_prompt_from_pack()`, `_escalate_weak_findings()`; `run()` dispatches on `AGENT_MODE`; the old path is preserved verbatim as `_run_legacy()`; `investigate()` gained an optional `max_tool_calls` |
| `agents/tools.py` | `call()`/`log()` take an optional `source` label, plus `retrieve_evidence_many()` (Q6). This is the only shared file I edited |
| `core/settings.py` | `AGENT_MODE = "prefetch" \| "legacy"` (default `prefetch`), `ESCALATION_ENABLED` (default true) |
| `tests/fake_gemini.py` | Per-agent report counter, captured prompts, and switches for low confidence / injected status / a 429 |

### How prefetch works, per in-scope requirement

1. `toolbox.retrieve_evidence_many([...])` **once for the whole scope** — every requirement's default
   queries in one batch, so you get to batch the query embeddings (Q6). Dedupe by chunk id within a
   requirement, cap at 6
2. `toolbox.get_requirement(req_id)` → details (no links, no fees)
3. `toolbox.get_profile_fact(key)` for the requirement's `required_fact_keys` (memoized per run)
4. Tax agent only: `toolbox.get_calculator_result()` for both PST and GST
5. One trace entry per step, labelled `source="prefetch"` — including one per `(requirement, query)`
   pair inside the batch, so the trace reads the same either way

**Everything goes through `AgentToolbox`, never through `services.retrieval` directly.** That is
deliberate: the toolbox is what registers retrieved chunks, and the strict citation filter only
accepts chunks registered in the current run. Please keep that invariant if you ever touch
`tools.py`.

## 4. The contract I coded against, vs. what exists today

You froze this:

```python
class Chunk(BaseModel):
    id: str; requirement_id: str; text: str
    source_title: str; source_url: str
    section_ref: str | None = None; score: float | None = None

def retrieve(requirement_id: str, query: str, k: int = 4) -> list[Chunk]: ...
def retrieve_many(requests: list[tuple[str, str]], k: int = 4) -> dict[str, list[Chunk]]: ...
KB_VERSION: str
```

Today's code returns `RetrievedChunk` from `retrieve(RetrievalRequest)`. Rather than edit your
module, I put the mapping in `agents/retrieval_adapter.py`:

| Contract | Today | Note |
| --- | --- | --- |
| `Chunk.id` | `RetrievedChunk.chunk_id` | rename only |
| `Chunk.source_title` | `.title` | rename only |
| `Chunk.source_url` | `.url` | currently always `"TODO-official-url"` |
| `Chunk.section_ref` | `.section_path` | rename only |
| `Chunk.requirement_id` | **absent** | I set it from the call site (I know which requirement I asked for) |
| `retrieve(req_id, query, k)` | `retrieve(RetrievalRequest)` | staying as-is (Q7); the toolbox builds the request, `k` is `EVIDENCE_LIMIT = 3` **per query** (Q5) |
| `retrieve_many(...)` | **absent** | prefetch calls it when the service exposes it, else falls back to sequential `retrieve` (Q6) |
| `KB_VERSION` | **absent** | `kb_version(services.retrieval)` calls `knowledge_base_version()` when present, else `"stub"` (Q3) |

---

## 5. Questions and answers

> Developer 1's full answers are in `PHASE2-ANSWERS.md`. Each `**Answer:**` below is the decision
> plus the change it caused on this branch.

### Q1. `depends_on` collision — the one that actually matters
The plan's §3.1/§3.3 say to add `depends_on` to each requirement as a list of **profile fact keys**.
But `Requirement.depends_on` already exists and holds **prerequisite requirement IDs**
(`TAX-02.depends_on == ["REG-03"]`). If you overload that field, Phase 3's cache key hashes
requirement IDs as if they were fact keys, and prefetch would look up a fact literally named
`"REG-03"`.

- **What I did:** read fact keys from `required_fact_keys`, with a `getattr(req, "depends_on_facts", ...)`
  hook that takes priority if you add it. I did not add any registry field.
- **Options:** (a) new field `depends_on_facts`, (b) reuse `required_fact_keys` and drop the plan's
  new field, (c) rename the existing one to `prerequisite_requirement_ids` and free up `depends_on`.
- **My preference:** (b) if `required_fact_keys` is already complete and reviewed, else (a).

**Answer:** (b). `Requirement.required_fact_keys: list[str]` is canonical and is populated for every
requirement; `depends_on` stays the ordered list of prerequisite requirement IDs. No
`depends_on_facts` field. **Changed:** dropped the `getattr(req, "depends_on_facts", ...)` hook from
`retrieval_adapter.fact_keys()`.

---

### Q2. `default_queries`
Plan §1.6 says you'll add 2-3 query phrasings per requirement. The registry has none yet.

- **What I did:** `default_queries(req)` reads `req.default_queries` if present, otherwise falls back
  to `[req.title, "do I need to <lowercased title> as a sole proprietor"]`. The fallback is crude and
  I'd like to delete it.
- **Asking:** are you adding `default_queries` to `requirements.json`, and under exactly that name?
  Any chance of it landing this week, or should I keep the fallback for the demo?

**Answer:** not before the demo. Keep the fallback; TiDB's semantic ranking makes title-based queries
acceptable for this corpus. If it ever lands the name will be `Requirement.default_queries: list[str]`,
after research-owner review — until then it must not be treated as available. **Changed:** removed the
speculative `getattr(req, "default_queries", ...)` read so the function has one documented behaviour.

---

### Q3. `KB_VERSION` — where does it live?
I read it as `getattr(app.knowledge.stubs, "KB_VERSION", "stub")`. One line to change if it lands
elsewhere, but Phase 3's cache keys need it for real, so I'd rather agree now.

- **Asking:** which module and which exact name? (`app.knowledge.retrieval.KB_VERSION`? a settings
  value? a DB row?)

**Answer:** neither a constant nor a settings value — it has to change whenever the live corpus does.
Phase 1 adds `RetrievalService.knowledge_base_version() -> str`, returning a digest of the sorted
current `(chunk_id, source_version)` pairs; the stub returns `"stub-v1"`. Lands before Phase 3, not
before the demo (the finding cache isn't in the demo path). **Changed:** the import-time `KB_VERSION`
constant became `kb_version(retrieval)`, which calls `knowledge_base_version()` when the service has
it and returns `"stub"` otherwise.

---

### Q4. Chunk ID stability across re-seeds
Every finding we persist stores `cited_chunk_ids`, and the citation filter accepts only chunk IDs
retrieved in the current run. If a re-seed renumbers chunks, old findings silently lose their
sources and Phase 3's cache has to treat them as misses.

- **Asking:** are chunk IDs deterministic (e.g. `sha1(source_id + section_ref)`) or generated per
  ingest run? Do they stay stable when only the *text* of a section changes?

**Answer:** today's `chk_...` IDs carry **no** documented cross-reseed guarantee, and no re-seed is
planned before the demo. Before any cache rollout, ingestion will use
`make_chunk_id(source_id, section_ref)` — a `chk_`-prefixed digest of the normalised source and legal
location — so a text-only edit keeps its ID and a moved section gets a new one; `source_version` plus
the KB version then invalidate stale entries. **Changed:** nothing in Phase 2; noted in §7 as owed.

---

### Q5. `k` semantics and chunk volume per assessment
The toolbox passes `limit = EVIDENCE_LIMIT = 3`. With 2 default queries per requirement and a cap of
6 chunks per requirement, a full Maya assessment issues **26 retrieval queries** (13 requirements ×
2), sequentially.

- **Asking:** is 26 sequential hybrid queries fine against your cluster? Your Phase 1 "done when"
  says 3-4 chunks per requirement in **under 1 second total** — at ~100 ms per hybrid query we'd be
  at ~2.6 s. If that's a problem, see Q6.
- Also: is `k` per query (so 2 queries can return 6 distinct chunks) or a per-requirement budget?

**Answer:** `limit` is **per query**, so two phrasings can yield up to six distinct chunks and the cap
of 6 per requirement is right. 26 sequential semantic queries are *not* the demo path — each one also
needs its own Gemini query embedding, so the "under 1 second" goal isn't reliably met. Fix is Q6; do
not raise `EVIDENCE_LIMIT`. **Changed:** `EVIDENCE_LIMIT` is now commented as per-query, and prefetch
sends all 26 pairs as one batch.

---

### Q6. Do we want batched retrieval, and who wires it?
`retrieve_many` is in your contract but prefetch can't call it today, because every retrieval has to
go through `AgentToolbox.retrieve_evidence` to stay citable. Using it means:
1. you add a batch method to the `RetrievalService` protocol, and
2. I add a `retrieve_evidence_many` to the toolbox that registers all chunks and writes one trace
   entry per `(requirement, query)` pair.

- **Asking:** worth doing before the demo, or leave the 26 sequential calls? If yes, I'll do step 2
  as a follow-up commit on my branch — just tell me the signature.

**Answer:** yes, before the demo. Phase 1 adds to `app.contracts.services.RetrievalService` and
implements in both services:

```python
def retrieve_many(self, requests: Sequence[RetrievalRequest]) -> list[RetrievalResult]:
    """Return one result per request, in exactly the input order."""
```

An ordered list, not a dict, because two requests can share a requirement ID or query. TiDB batches
the query embedding, then runs the metadata-filtered rankings, preserving every request's
jurisdiction, segment, area, requirement IDs, `as_of` and limit.

**Changed (Developer 2's half, done):** `AgentToolbox.retrieve_evidence_many(pairs, source=...)`
returns one result per input pair in order, registers every chunk, and writes one trace entry per
`(requirement, query)` pair. It calls `retrieve_many` when the service exposes it and falls back to
sequential `retrieve` until Phase 1 lands, so the stub keeps working today — covered by
`test_prefetch_batches_the_whole_scope` and `test_sequential_fallback_matches_the_batched_result`.
Agents still never touch `services.retrieval` directly.

---

### Q7. Are you changing the `RetrievalService.retrieve` signature?
If you move to the flat `retrieve(requirement_id, query, k)` form, exactly one function needs
updating: `AgentToolbox.retrieve_evidence` in `app/agents/tools.py`. Nothing else in my code calls
retrieval directly.

- **Asking:** keeping `retrieve(RetrievalRequest)` (my preference — it carries jurisdiction, segment,
  area and `as_of`, which the flat signature drops), or flipping? If flipping, I'll do the toolbox
  edit so we don't both touch that file.

**Answer:** keeping `retrieve(request: RetrievalRequest) -> RetrievalResult`. `RetrievalRequest` is
deliberate: the flat form would drop mandatory evidence-safety filters. **Changed:** nothing; the
toolbox still builds the request (now via one `_request()` helper shared with the batch path).

---

### Q8. Does `requirement_id` filtering stay exact?
The stub matches a chunk if `requirement_ids` *intersects* the request. Your `LegalChunk` has a
single `requirement_id` column.

- **Asking:** can one chunk serve several requirements? If yes, does the hybrid filter use `IN` on a
  join table, and can the same chunk ID come back under two different requirements in one run?
  (It's safe either way for me — I tag `Chunk.requirement_id` from the call site — but it changes
  whether prefetch dedupes across requirements.)

**Answer:** one chunk may support several requirements, so the same chunk ID can come back under more
than one requirement in a run. Production will use a `chunk_requirement_mappings` join table
(`chunk_id`, `requirement_id`, review status) and filter on the exact requested `requirement_id` — never
arbitrary same-area chunks. Current exact-intersection behaviour stays for the demo. **Changed:**
dedupe stays scoped to one requirement's pack, now stated in `AgentToolbox._register`.

---

### Q9. Real `source_url`, and `insufficient_evidence`
Two smaller ones:
- Every `action_url` and chunk `url` is still `"TODO-official-url"`. `_enrich()` builds the results
  page's source links from `RetrievedChunk.url`, so the demo shows placeholder links until you seed
  real ones. Still on track?
- Is `RetrievalResult.status == "insufficient_evidence"` staying? Prefetch treats "zero chunks" as an
  escalation trigger, and the citation filter turns it into the "no official source found" copy.

**Answer:** chunk `url`s are already real official URLs in the live TiDB corpus; the registry's
`action_url` values are still draft placeholders pending research-owner review (plus a known `REG-02`
City of Vancouver source gap) — Phase 1 content work. `status` keeps its
`Literal["supported", "insufficient_evidence"]` shape, and zero chunks must stay an escalation and a
"no official source" condition, never licence for Gemini to invent one. **Changed:** nothing; this is
already the behaviour.

---

## 6. Concerns I resolved myself — FYI, no action needed

| Concern | What I did |
| --- | --- |
| Trace has no `source` field, and `agent_runs` would need a migration | Put the label inside `tool_input`, which is already persisted and returned by `GET /trace`. No schema change |
| `asyncio.gather` over prefetch lookups | Not needed. Retrieval is one batch (Q6); the rest stays sequential because the toolbox mutates shared per-run state and the service is synchronous, so `gather` buys nothing and `to_thread` would race |
| ~80 trace entries per agent if every fact lookup is logged | Memoized fact lookups per run, so each distinct key is fetched and logged once. ~18 entries per agent |
| Escalation could loop | `_escalate_weak_findings` is called once from `run()`, so the cap is structural, not a flag. Investigate is capped at 3 tool calls; on failure the original drafts survive |
| Gemini might smuggle a `status` into the report | `AgentReport`/`FindingDraft` still have no status field; a test injects one and asserts the schema drops it and that the final status equals applicability |
| Unknown facts rendering as `False` | Unknown renders as *"unknown (we don't know this yet; never treat it as false)"* in the prompt. A test asserts `plans_to_hire` never appears as `False`, while confirmed-false `has_employees` still does |
| Flipping the default would break the old tests | `tests/test_agents.py` pins `AGENT_MODE="legacy"`, so both paths stay covered. `AGENT_MODE=legacy` restores the old behaviour at runtime too |

## 7. Merge checklist

- [x] Q1-Q9 answered (`PHASE2-ANSWERS.md`) and applied here
- [ ] Phase 1 merged first (it only adds/replaces files in `app/knowledge/` + `contracts/services.py`)
- [ ] Then this branch; expect zero conflicts
- [x] `pytest` in `backend/` — 78 tests, all green
- [ ] Run one real assessment with `AGENT_MODE=prefetch` and confirm 3 Gemini requests

### Still owed by Phase 1 — nothing here blocks the merge

Phase 2 feature-detects all three, so it works before and after they land.

| Owed | Phase 2 behaviour until then | Needed by |
| --- | --- | --- |
| `RetrievalService.retrieve_many(Sequence[RetrievalRequest]) -> list[RetrievalResult]` (Q6) | falls back to sequential `retrieve`, same chunks, same trace | demo |
| `RetrievalService.knowledge_base_version() -> str` (Q3) | `kb_version()` returns `"stub"` | Phase 3 cache keys |
| `make_chunk_id(source_id, section_ref)` at ingest (Q4) | current IDs are fine, no re-seed planned | before any cache rollout |
| Reviewed `Requirement.action_url`s + the `REG-02` City of Vancouver source (Q9) | placeholder action links on the results page | demo content pass |

When `retrieve_many` lands, nothing in `agents/` needs editing: `AgentToolbox._retrieve_batch` picks it
up on its own. Please keep the invariant that retrieval goes through the toolbox, since that is what
registers chunks for the strict citation filter.

## 8. Next up (Developer 2, not in this branch)

Phase 0 (call ledger) is still unbuilt, so `generate_structured` has no `purpose`/`agent` kwargs —
the "3 requests" number is currently proven by tests, not by a badge on screen. Phase 3
(per-requirement `finding_cache`) is now unblocked on Q1 and waits only on `knowledge_base_version()`.
