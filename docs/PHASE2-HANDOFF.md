# Phase 2 handoff: prefetch + single-call agents

**Branch:** `feat/phase2-prefetch-single-call-agents` · **Owner:** Developer 2 · **Status:** done, 74 tests green
**Reader:** Developer 1 (Phase 1, TiDB hybrid search). **Action needed:** answer Q1-Q9 below before we merge.

> **If you are the agent implementing Phase 1, read this first.**
> Treat §5 as a form. For each question, write under its `**Answer:**` line: the decision, the exact
> module/field/signature name you will ship, and whether it lands before the demo. Say "not doing it"
> where that's the answer — a clear no is more useful than silence. Where you disagree with an
> assumption in §4 or §6, say so explicitly; I built fallbacks for all of them, so changing your mind
> costs me one line each.
> Do **not** edit any file listed in §2 (`app/agents/*`, `app/core/settings.py`, `tests/*`) — those are
> Phase 2's and we'd conflict. Edit this file only. If a question can't be answered without changing
> a Phase 2 file, say which one and why, and I'll make the change on my branch.

---

## 1. What landed

Code now gathers all the evidence an agent needs ("prefetch"), then each agent makes **exactly one**
`generate_structured` call to write its findings. The Gemini tool loop survives only as a bounded
escalation path for weak findings, and as the chat path (unchanged).

| Flow | Before | After | Proven by |
| --- | --- | --- | --- |
| First assessment (3 agents in scope) | 8-15 requests | **3** | `test_first_run_three_calls` |
| Prefetch itself | n/a | **0** | `test_prefetch_makes_no_llm_calls` |
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

Untouched: `app/knowledge/*` (retrieval + registry stubs), `app/assessment/stubs.py`
(applicability, calculators, scoring), `data/registry/requirements.json`, every seed/embedding path.
**Your branch and mine should merge without a single conflict** unless you edit `agents/` or `tests/`.

## 3. File-by-file

| File | What it does |
| --- | --- |
| `agents/models.py` | `RequirementEvidence` (requirement_id, read-only applicability, details, gray_areas, chunks, relevant_facts) and `EvidencePack` (agent, mode, requirements, calculators, profile_summary) |
| `agents/retrieval_adapter.py` | Maps your `RetrievedChunk` onto the frozen `Chunk` contract. Holds `KB_VERSION`, `CHUNKS_PER_REQUIREMENT = 6`, `default_queries()` and `fact_keys()` fallbacks |
| `agents/base.py` | `prefetch()`, `_report_prompt_from_pack()`, `_escalate_weak_findings()`; `run()` dispatches on `AGENT_MODE`; the old path is preserved verbatim as `_run_legacy()`; `investigate()` gained an optional `max_tool_calls` |
| `agents/tools.py` | `call()`/`log()` take an optional `source` label. **21 lines, no behaviour change.** This is the only shared file I edited |
| `core/settings.py` | `AGENT_MODE = "prefetch" \| "legacy"` (default `prefetch`), `ESCALATION_ENABLED` (default true) |
| `tests/fake_gemini.py` | Per-agent report counter, captured prompts, and switches for low confidence / injected status / a 429 |

### How prefetch works, per in-scope requirement

1. `toolbox.get_requirement(req_id)` → details (no links, no fees)
2. `toolbox.retrieve_evidence(req_id, q)` for each of its default queries; dedupe by chunk id, cap at 6
3. `toolbox.get_profile_fact(key)` for the requirement's fact keys (memoized per run)
4. Tax agent only: `toolbox.get_calculator_result()` for both PST and GST
5. One trace entry per step, labelled `source="prefetch"`

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
| `retrieve(req_id, query, k)` | `retrieve(RetrievalRequest)` | the toolbox builds the request; `k` comes from `EVIDENCE_LIMIT = 3` |
| `retrieve_many(...)` | **absent** | not used yet, see Q6 |
| `KB_VERSION` | **absent** | read as `getattr(app.knowledge.stubs, "KB_VERSION", "stub")` |

---

## 5. Questions for you — please answer inline and commit this file

> Each one has what I assumed so nothing is blocked if you disagree later; I just want it on the
> record before we merge.

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

**Answer:**

---

### Q2. `default_queries`
Plan §1.6 says you'll add 2-3 query phrasings per requirement. The registry has none yet.

- **What I did:** `default_queries(req)` reads `req.default_queries` if present, otherwise falls back
  to `[req.title, "do I need to <lowercased title> as a sole proprietor"]`. The fallback is crude and
  I'd like to delete it.
- **Asking:** are you adding `default_queries` to `requirements.json`, and under exactly that name?
  Any chance of it landing this week, or should I keep the fallback for the demo?

**Answer:**

---

### Q3. `KB_VERSION` — where does it live?
I read it as `getattr(app.knowledge.stubs, "KB_VERSION", "stub")`. One line to change if it lands
elsewhere, but Phase 3's cache keys need it for real, so I'd rather agree now.

- **Asking:** which module and which exact name? (`app.knowledge.retrieval.KB_VERSION`? a settings
  value? a DB row?)

**Answer:**

---

### Q4. Chunk ID stability across re-seeds
Every finding we persist stores `cited_chunk_ids`, and the citation filter accepts only chunk IDs
retrieved in the current run. If a re-seed renumbers chunks, old findings silently lose their
sources and Phase 3's cache has to treat them as misses.

- **Asking:** are chunk IDs deterministic (e.g. `sha1(source_id + section_ref)`) or generated per
  ingest run? Do they stay stable when only the *text* of a section changes?

**Answer:**

---

### Q5. `k` semantics and chunk volume per assessment
The toolbox passes `limit = EVIDENCE_LIMIT = 3`. With 2 default queries per requirement and a cap of
6 chunks per requirement, a full Maya assessment issues **26 retrieval queries** (13 requirements ×
2), sequentially.

- **Asking:** is 26 sequential hybrid queries fine against your cluster? Your Phase 1 "done when"
  says 3-4 chunks per requirement in **under 1 second total** — at ~100 ms per hybrid query we'd be
  at ~2.6 s. If that's a problem, see Q6.
- Also: is `k` per query (so 2 queries can return 6 distinct chunks) or a per-requirement budget?

**Answer:**

---

### Q6. Do we want batched retrieval, and who wires it?
`retrieve_many` is in your contract but prefetch can't call it today, because every retrieval has to
go through `AgentToolbox.retrieve_evidence` to stay citable. Using it means:
1. you add a batch method to the `RetrievalService` protocol, and
2. I add a `retrieve_evidence_many` to the toolbox that registers all chunks and writes one trace
   entry per `(requirement, query)` pair.

- **Asking:** worth doing before the demo, or leave the 26 sequential calls? If yes, I'll do step 2
  as a follow-up commit on my branch — just tell me the signature.

**Answer:**

---

### Q7. Are you changing the `RetrievalService.retrieve` signature?
If you move to the flat `retrieve(requirement_id, query, k)` form, exactly one function needs
updating: `AgentToolbox.retrieve_evidence` in `app/agents/tools.py`. Nothing else in my code calls
retrieval directly.

- **Asking:** keeping `retrieve(RetrievalRequest)` (my preference — it carries jurisdiction, segment,
  area and `as_of`, which the flat signature drops), or flipping? If flipping, I'll do the toolbox
  edit so we don't both touch that file.

**Answer:**

---

### Q8. Does `requirement_id` filtering stay exact?
The stub matches a chunk if `requirement_ids` *intersects* the request. Your `LegalChunk` has a
single `requirement_id` column.

- **Asking:** can one chunk serve several requirements? If yes, does the hybrid filter use `IN` on a
  join table, and can the same chunk ID come back under two different requirements in one run?
  (It's safe either way for me — I tag `Chunk.requirement_id` from the call site — but it changes
  whether prefetch dedupes across requirements.)

**Answer:**

---

### Q9. Real `source_url`, and `insufficient_evidence`
Two smaller ones:
- Every `action_url` and chunk `url` is still `"TODO-official-url"`. `_enrich()` builds the results
  page's source links from `RetrievedChunk.url`, so the demo shows placeholder links until you seed
  real ones. Still on track?
- Is `RetrievalResult.status == "insufficient_evidence"` staying? Prefetch treats "zero chunks" as an
  escalation trigger, and the citation filter turns it into the "no official source found" copy.

**Answer:**

---

## 6. Concerns I resolved myself — FYI, no action needed

| Concern | What I did |
| --- | --- |
| Trace has no `source` field, and `agent_runs` would need a migration | Put the label inside `tool_input`, which is already persisted and returned by `GET /trace`. No schema change |
| `asyncio.gather` over prefetch lookups | Left it sequential: the toolbox mutates shared per-run state and your retrieval service is synchronous, so `gather` buys nothing and `to_thread` would race. Revisit with Q6 |
| ~80 trace entries per agent if every fact lookup is logged | Memoized fact lookups per run, so each distinct key is fetched and logged once. ~18 entries per agent |
| Escalation could loop | `_escalate_weak_findings` is called once from `run()`, so the cap is structural, not a flag. Investigate is capped at 3 tool calls; on failure the original drafts survive |
| Gemini might smuggle a `status` into the report | `AgentReport`/`FindingDraft` still have no status field; a test injects one and asserts the schema drops it and that the final status equals applicability |
| Unknown facts rendering as `False` | Unknown renders as *"unknown (we don't know this yet; never treat it as false)"* in the prompt. A test asserts `plans_to_hire` never appears as `False`, while confirmed-false `has_employees` still does |
| Flipping the default would break the old tests | `tests/test_agents.py` pins `AGENT_MODE="legacy"`, so both paths stay covered. `AGENT_MODE=legacy` restores the old behaviour at runtime too |

## 7. Merge checklist

- [ ] Q1-Q9 answered above
- [ ] Phase 1 merged first (it only adds/replaces files in `app/knowledge/`)
- [ ] Then this branch; expect zero conflicts
- [ ] `pytest` in `backend/` — 74 tests, all green
- [ ] Run one real assessment with `AGENT_MODE=prefetch` and confirm 3 Gemini requests
- [ ] If Q1 lands as `depends_on_facts`, delete the `required_fact_keys` fallback in
      `retrieval_adapter.py:fact_keys()`
- [ ] If Q2 lands, delete the query fallback in `retrieval_adapter.py:default_queries()`

## 8. Next up (Developer 2, not in this branch)

Phase 0 (call ledger) is still unbuilt, so `generate_structured` has no `purpose`/`agent` kwargs —
the "3 requests" number is currently proven by tests, not by a badge on screen. Phase 3 (per-requirement
`finding_cache`) is blocked on Q1 and Q3.
