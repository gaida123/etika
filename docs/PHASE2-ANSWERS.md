# Phase 2 handoff answers — Developer 1

This records decisions against `PHASE2-HANDOFF.md`. It does not modify Developer
2's Phase 2 files.

> Developer 2 note: every answer below is applied on
> `feat/phase2-prefetch-single-call-agents`. See §5 of `PHASE2-HANDOFF.md` for
> what changed per question, and §7 for what Phase 1 still owes
> (`knowledge_base_version()`, `retrieve_many()`, `make_chunk_id`, reviewed
> `action_url`s).

## Q1. `depends_on` collision

**Decision:** use `Requirement.required_fact_keys` for profile fact dependencies.
Do **not** overload `Requirement.depends_on`: it remains the ordered list of
prerequisite requirement IDs. Do not add `depends_on_facts` before the demo.

**Exact contract:** `app.contracts.registry.Requirement.required_fact_keys:
list[str]` is the canonical field. The reviewed real registry must populate it
for every requirement. Phase 2 should keep its `required_fact_keys` fallback;
the optional `depends_on_facts` hook is not needed.

**Before demo:** yes; this is already the correct registry contract and is
populated in the current draft registry.

## Q2. `default_queries`

**Decision:** do not add reviewed `default_queries` to the registry before the
demo. Keep Phase 2's `default_queries(req)` fallback for the demo.

**Exact contract:** no new `Requirement.default_queries` field will land in the
current Phase 1 branch. If we later add it, the name will be
`Requirement.default_queries: list[str]`, with research-owner review, but it
must not be treated as available now.

**Before demo:** not doing it. The live TiDB retrieval already receives the
requirement ID, jurisdiction, area, and query; its semantic ranking makes the
title-based fallback acceptable for this small corpus.

## Q3. `KB_VERSION`

**Decision:** do not use a static module constant or a settings value. The
version must change whenever the live current corpus changes.

**Exact interface to add before Phase 3:**

```python
class RetrievalService(Protocol):
    def knowledge_base_version(self) -> str: ...
```

`app.knowledge.tidb_retrieval.TiDBRetrievalService.knowledge_base_version()`
will return a deterministic digest of the current corpus identity/version (the
sorted current `(chunk_id, source_version)` pairs). The stub will return a
separate stable literal, e.g. `"stub-v1"`.

**Before demo:** no, because the finding cache is not in the demo path. It is
required before Phase 3 cache keys are enabled. Phase 2 should retain its
current fallback until that interface lands.

## Q4. Chunk ID stability across re-seeds

**Decision:** do not assume the current opaque `chk_...` IDs have a documented
cross-reseed stability guarantee. No re-seed is planned before the demo.

**Required ingestion contract before cache rollout:** create IDs from the
stable source and legal location, not body text:

```python
make_chunk_id(source_id: str, section_ref: str) -> str
```

Its value will be a `chk_`-prefixed digest of normalized `source_id` and
`section_ref`. A text-only update at the same legal section therefore keeps the
same ID; a moved/renamed legal section receives a new ID. `source_version` and
the KB version then invalidate stale cache entries.

**Before demo:** not doing a corpus re-seed. Existing IDs remain valid for the
current stored corpus and live citations.

## Q5. `k` semantics and query volume

**Decision:** `RetrievalRequest.limit` is a **per-query** limit. Its current
value of 3 means two query phrasings may yield up to six distinct chunks for a
requirement; Phase 2's per-requirement cap of 6 remains correct.

Twenty-six sequential semantic queries are not the desired demo path: each one
also needs a Gemini query embedding. The current 240-row corpus works
correctly, but this does not meet the handoff's under-one-second retrieval goal
reliably.

**Before demo:** add batch retrieval as decided in Q6. Until it lands, keep the
Phase 2 cap and sequential fallback; do not increase `EVIDENCE_LIMIT`.

## Q6. Batched retrieval

**Decision:** yes, implement it before the demo.

**Developer 1 interface:** add this to
`app.contracts.services.RetrievalService` and implement it in both the TiDB and
stub services:

```python
def retrieve_many(self, requests: Sequence[RetrievalRequest]) -> list[RetrievalResult]:
    """Return one result per request, in exactly the input order."""
```

An ordered list is intentional: a dictionary can collide if two requests share
a requirement ID or query. The TiDB implementation will batch the Gemini query
embedding call, then perform the corresponding metadata-filtered vector
rankings. It must preserve every request's jurisdiction, segment, area,
requirement IDs, `as_of`, and limit.

**Developer 2 follow-up:** add
`AgentToolbox.retrieve_evidence_many(...)`, register every returned chunk in the
current run, and write one trace item for each original `(requirement, query)`
pair. Do not call the retrieval service directly from agents.

**Before demo:** yes. Developer 1 owns the protocol/implementations; Developer
2 owns the toolbox/trace wrapper after the interface lands.

## Q7. `RetrievalService.retrieve` signature

**Decision:** keep the current signature:

```python
def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...
```

`RetrievalRequest` is deliberately retained because it carries jurisdiction,
segment, area, requirement IDs, effective date, and limit. The flat
`retrieve(requirement_id, query, k)` form would drop mandatory evidence-safety
filters.

**Before demo:** yes; this is already the live TiDB signature. Phase 2 should
continue constructing the request through `AgentToolbox.retrieve_evidence`.

## Q8. Exact requirement filtering and multi-requirement chunks

**Decision:** one chunk may support more than one requirement. The current TiDB
corpus uses `mapped_requirement_ids` as a list; the temporary candidate list is
only a staging fallback. A chunk may therefore be returned under multiple
requirement calls in the same run.

**Exact production model:** use a `chunk_requirement_mappings` join table with
at least `chunk_id`, `requirement_id`, and mapping/review status. Retrieval
filters by the exact requested `requirement_id` through that mapping, alongside
current/date/jurisdiction/area filters. It must not select arbitrary
same-area chunks.

**Before demo:** retain the current exact intersection behavior. Phase 2 may tag
the same chunk ID with each call-site requirement and should only dedupe within
one requirement's evidence pack.

## Q9. Official source URLs and `insufficient_evidence`

**Decision:** `RetrievedChunk.url` is already populated from the real TiDB
corpus and returns official URLs in the live semantic smoke test. The registry
`Requirement.action_url` values are still draft placeholders and must be
replaced by research-owner-approved official action links before production.

**Exact status contract:** keep
`RetrievalResult.status: Literal["supported", "insufficient_evidence"]`.
Phase 2 should continue treating zero chunks / `insufficient_evidence` as an
escalation and no-official-source condition, never as permission for Gemini to
invent an answer.

**Before demo:** source citation URLs are ready. Reviewed registry action URLs
and the known `REG-02` City of Vancouver source gap remain Phase 1 content work.
