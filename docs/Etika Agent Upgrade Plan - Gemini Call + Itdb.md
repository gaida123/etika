# Reegal Agent Upgrade Plan

Oct 4, 2026 · @Freya

## Goals and call budget

Cut Gemini usage from 10 to 15 requests per assessment to 3 on a first run and 0 to 1 on a rerun, while keeping every finding cited and every status decided by code.

| Flow | Today (requests) | Target (requests) | How |
| --- | --- | --- | --- |
| First assessment | 8 to 15 | 3 (1 per agent) | Prefetch evidence, single report call |
| Rerun, same facts | 8 to 15 (or cached on failure) | 0 | Primary cache by fact hash |
| Rerun, one fact changed | 8 to 15 | 0 to 1 | Agent memory diff, only affected agent reruns |
| Low-confidence escalation | n/a | +1 per flagged agent | Optional investigate round |
| Chat question | 3 to 5 | 1 | Stored findings + hybrid retrieval, no tool loop |

**Guiding principles**

- Code decides, Gemini explains. Status, score, scope and citations stay deterministic (unchanged from today).
- Never ask Gemini for something code already knows. If a value is known before the call, put it in the prompt.
- Every Gemini call must earn its place: reasoning over evidence, or writing for a human. Lookups are code.
- Remember instead of redo. An agent that has already judged a requirement for these facts reuses its answer.
- Persona is a skin, not a brain. It changes tone in human-facing text only, never findings or citations.
- Every phase ships independently. If the hackathon clock runs out mid-plan, what landed still works.

## Architecture before vs after

Today every agent runs a Gemini tool loop plus a report call; after the upgrade, code handles planning, memory, caching and evidence, and Gemini is called once per agent only for requirements that missed every cache.

&#91;embedded content: assessment pipeline after the upgrade · 8 steps, 1 Gemini call per agent\]

Read top to bottom: everything except the accented box is plain code or TiDB, so a rerun with unchanged facts never reaches Gemini.

## Phase 0: Measure before you cut

Add a per-request Gemini counter first, so every later phase can prove its savings with a number on screen. Effort: about 30 minutes. Owner: Developer 2.

**Why:** "we cut calls from 12 to 3" is a demo line only if you can show it. It also tells you which phase gave the biggest win.

**Steps**

1. In `backend/app/core/llm.py`, add a `CallLedger` that records every real Gemini request: `request_id`, `purpose` (intake, report, investigate, chat, router, health), `agent`, `model`, `attempt`, `status_code`, `latency_ms`, `prompt_tokens`, `output_tokens`, `cache_hit` (bool).
2. Pass a `purpose` and optional `agent` argument into `generate_content` and `generate_structured`. Default `purpose="unknown"` so nothing breaks.
3. Scope the ledger per assessment with a `contextvars.ContextVar`, so parallel agents in `asyncio.gather` still log against the right `assessment_id`.
4. Persist a summary on the assessment: `gemini_requests`, `gemini_retries`, `cache_hits`, `tokens_in`, `tokens_out`.
5. Expose it: add the summary to `GET /assessments/{id}/trace` and a small "Gemini calls: 3 (saved 9)" badge in the UI.
6. Run 3 baseline assessments with the current code. Write the numbers into the table below.

```python
# core/llm.py (sketch)
_ledger: ContextVar[list[dict] | None] = ContextVar("gemini_ledger", default=None)

def record_call(**entry):
    ledger = _ledger.get()
    if ledger is not None:
        ledger.append(entry)
```

| Baseline run | Requests | Retries (429/503) | Tokens in | Latency (s) |
| --- | --- | --- | --- | --- |
| Sole prop, no employees |  |  |  |  |
| Sole prop, hiring soon |  |  |  |  |
| Has employees, over PST threshold |  |  |  |  |

**Done when:** the trace endpoint shows request count per assessment and the baseline table is filled.

## Phase 1: TiDB knowledge base upgrade

Replace the retrieval stub with pytidb hybrid search (keyword + vector in one query), filtered by requirement, so prefetch in Phase 2 returns the right chunks without Gemini choosing queries. Effort: 3 to 4 hours. Owner: Developer 1 (retrieval is theirs), Developer 2 consumes it.

**Why hybrid matters for legal text:** exact terms ("PST", "Employment Standards Act", "GST/HST registration") need keyword matching; plain-language questions ("do I need to charge tax") need semantic matching. Hybrid search fuses both rankings, using RRF or a weighted score ([TiDB hybrid search docs](https://docs.pingcap.com/ai/vector-search-hybrid-search)).

**Step 1.1: Check your cluster region (do this first, 5 minutes).** Full-text search is currently limited to TiDB Cloud Starter and Essential in certain regions ([full-text docs](https://docs.pingcap.com/ai/vector-search-full-text-search-python)). Open the TiDB Cloud console and confirm your region is on the supported list.

- Supported: go ahead with hybrid.
- Not supported: either create a new Starter cluster in a supported region and re-seed (best, about 30 minutes), or fall back to vector search plus a SQL keyword filter on a `keywords` column (Step 1.5).

**Step 1.2: Install and connect.** `pip install pytidb` (add `"pytidb[models]"` if you want the built-in embedding or reranker helpers). Connect with `TiDBClient` using the same credentials as today.

**Step 1.3: Define the chunks table.** One row per chunk of official source text, with metadata that lets agents filter before ranking.

```python
from pytidb.schema import TableModel, Field, FullTextField
from pytidb.embeddings import EmbeddingFunction

embed_fn = EmbeddingFunction("<provider/model you already use>")

class LegalChunk(TableModel):
    __tablename__ = "legal_chunks"
    id: str = Field(primary_key=True)          # stable chunk ID, used in citations
    requirement_id: str = Field()             # e.g. "bc_pst_registration"
    agent: str = Field()                      # registration | tax | employer
    jurisdiction: str = Field()               # city_vancouver | bc | federal
    source_title: str = Field()
    source_url: str = Field()
    section_ref: str = Field()                # e.g. "PSTA s.170"
    kb_version: str = Field()                 # bump when you re-seed
    keywords: str = Field()                   # fallback for Step 1.5
    text: str = FullTextField()
    text_vec: list[float] = embed_fn.VectorField(source_field="text")
```

PyTiDB embeds the `text` field automatically on insert and stores it in the vector field ([pytidb README](https://github.com/pingcap/pytidb)). Check that your embedding provider is supported by `EmbeddingFunction`; if not, keep your current embedding call and write vectors yourself.

**Step 1.4: Implement the retrieval service** that Phase 2 will call. Same signature Developer 2 already uses, plus a batch method.

```python
def retrieve(requirement_id: str, query: str, k: int = 4) -> list[Chunk]:
    return (
        chunks.search(query, search_type="hybrid")
        .filter({"requirement_id": requirement_id, "kb_version": KB_VERSION})
        .limit(k)
        .to_list()
    )

def retrieve_many(requests: list[tuple[str, str]], k: int = 4) -> dict[str, list[Chunk]]:
    # one entry per in-scope requirement; run concurrently or loop, no Gemini involved
    ...
```

**Step 1.5: Fallback if full-text is unavailable.** Vector search filtered by `requirement_id`, then boost rows whose `keywords` column contains the query's exact terms (simple SQL `LIKE` or Python re-sort). Same function signature, so nothing downstream changes.

**Step 1.6: Seed queries per requirement.** Add a `default_queries` list to each requirement in the registry (2 to 3 phrasings each: the official term, the plain-language question, the threshold phrasing). Prefetch uses these instead of asking Gemini what to search.

**Step 1.7 (optional): Reranking.** pytidb supports a reranker step after hybrid search ([TiDB hybrid search docs](https://docs.pingcap.com/ai/vector-search-hybrid-search)). It is an extra external API call per query, so only add it if retrieval quality is visibly poor in testing. Because results are filtered to one requirement, you probably do not need it.

**Step 1.8: Add a `kb_version` constant** (for example `"2026-10-04a"`). Bump it whenever chunks change. Phases 3 to 5 include it in cache keys so stale answers expire automatically.

**Done when:** `retrieve_many` returns 3 to 4 relevant chunks for every requirement in a test profile, with stable chunk IDs, in under 1 second total, with zero Gemini calls.

## Phase 2: Prefetch + single-call agents

Code gathers every piece of evidence an agent needs, then the agent makes exactly one structured Gemini call; the tool loop survives only as an escalation path. This is the biggest single saving (about 9 calls down to 3). Effort: 3 to 4 hours. Owner: Developer 2.

**Why it works:** scope is decided by code before any agent runs, so Gemini's investigate turns mostly re-request things code already knows (requirement details, profile facts, evidence for in-scope requirements). Prefetch does those lookups deterministically.

**Step 2.1: Add an `EvidencePack` model** in `agents/models.py`.

```python
class RequirementEvidence(BaseModel):
    requirement_id: str
    applicability: str              # from code, read-only for Gemini
    details: dict                   # get_requirement() output (no links, no fees)
    gray_areas: list[str]
    chunks: list[Chunk]             # hybrid search results, IDs are citable
    relevant_facts: dict[str, FactValue]   # known=false preserved

class EvidencePack(BaseModel):
    agent: str
    mode: str | None
    requirements: list[RequirementEvidence]
    calculators: dict[str, dict]    # tax only: PST/GST threshold results
    profile_summary: dict
```

**Step 2.2: Add `BaseAgent.prefetch(toolbox, profile, scope, mode)`.** For each in-scope requirement:

1. Call `toolbox.get_requirement(req_id)`.
2. Call `toolbox.retrieve_evidence(req_id, q)` for each of the requirement's `default_queries` (Phase 1.6), dedupe chunks by ID. Going through the toolbox keeps the "only retrieved chunks are citable" rule and the trace entries working unchanged.
3. Read the facts listed in the requirement's `depends_on` (Phase 3.1) via `toolbox.get_profile_fact`.
4. Tax agent only: run both calculators via `toolbox.get_calculator_result`.
5. Log one trace entry per step with `source="prefetch"`, so the trace view still shows the agent's work.

Zero Gemini calls happen in prefetch.

**Step 2.3: Change `BaseAgent.run`** to: prefetch, then one `generate_structured` call with the pack serialized into the prompt, then (optionally) escalate.

```python
async def run(self, assessment_id, profile, scope, mode=None) -> AgentRunOutput:
    output = AgentRunOutput(agent=self.name, mode=mode, scope=scope)
    toolbox = AgentToolbox(self.name, assessment_id, profile, self.services, output, self.tool_names)
    try:
        pack = await self.prefetch(toolbox, profile, scope, mode)
        report = await self.generate_structured(
            prompt=self._report_prompt_from_pack(pack),
            system=f"{self.system_prompt(mode)}\n\n{REPORT_RULES}",
            schema=AgentReport,
            purpose="report", agent=self.name,
        )
        output.drafts = report.findings
        if settings.ESCALATION_ENABLED:
            await self._escalate_weak_findings(toolbox, pack, output, mode)
    except Exception as exc:  # noqa: BLE001
        output.error = describe_error(exc)
        toolbox.log("error", {}, output.error)
    return output
```

**Step 2.4: Escalation (bounded).** After the report, find findings with `confidence < 0.6` or requirements whose pack had zero chunks. For those only:

1. Run the existing `investigate` loop with `max_tool_calls = 3` and a prompt naming just those requirement IDs.
2. Make one more structured call that re-reports only those requirements, and merge the results back in.
3. Cap: one escalation round per agent per assessment. Log `escalated=true` in the trace.

This keeps the "agent can go dig" behaviour for hard cases without paying for it on every run.

**Step 2.5: Feature flag.** `AGENT_MODE = "prefetch" | "legacy"` in settings. Keep the old path working until Phase 2 passes the tests in the Testing section, then flip the default.

**Step 2.6: Prompt hygiene for the single call.**

- Put the pack in a clearly delimited block (`<evidence>` ... `</evidence>`), one sub-block per requirement with its chunk IDs.
- Restate the rules: one finding per requirement ID in the pack, cite only chunk IDs shown, never output a status, say "no official source found" if chunks do not support a claim.
- Keep temperature 0.1.

**Considered and rejected for now: one call for all three agents.** It would make an assessment cost 1 request, but one malformed reply or 429 fails everything, and the prompt gets long. Three parallel calls fit the 5-requests-per-minute free tier and fail independently. Revisit if you move to a paid tier.

**Done when:** a first assessment makes 3 Gemini requests (ledger proves it), findings still cite valid chunk IDs, and the strict citation filter drops no more claims than the legacy path did.

## Phase 3: Fact dependencies and primary cache

Cache each finding by the exact facts it depends on, check that cache before any Gemini call, and only send cache misses to the model. Same facts means 0 requests. Effort: 2 to 3 hours. Owner: Developer 2 (cache), Developer 1 or whoever owns the registry (`depends_on`).

**Why per requirement, not per assessment:** today `with_cache` keys on the whole fact set and only kicks in on failure. Changing an unrelated fact (say, business phone number) throws away everything. Keying on each requirement's own facts keeps the rest valid.

**Step 3.1: Add `depends_on` to every requirement** in the registry: the profile fact keys that can change its applicability or its explanation.

| Requirement (example) | depends\_on |
| --- | --- |
| Vancouver business licence | business\_address\_city, business\_type, home\_based |
| BC PST registration | sells\_taxable\_goods\_or\_services, annual\_bc\_taxable\_sales, location |
| GST/HST registration | worldwide\_taxable\_revenue\_4q, revenue\_trend |
| WorkSafeBC registration | has\_employees, plans\_to\_hire, hire\_date |
| Payroll deductions (CRA) | has\_employees, plans\_to\_hire |

Replace the example keys with your real fact names. If a requirement is missing `depends_on`, treat it as depending on all facts (safe default, no caching benefit).

**Step 3.2: Create the cache table in TiDB.**

```sql
CREATE TABLE finding_cache (
  cache_key      CHAR(64) PRIMARY KEY,   -- sha256, see 3.3
  agent          VARCHAR(32)  NOT NULL,
  requirement_id VARCHAR(128) NOT NULL,
  draft_json     JSON         NOT NULL,  -- AgentReport finding (no status)
  cited_chunk_ids JSON        NOT NULL,
  kb_version     VARCHAR(32)  NOT NULL,
  prompt_version VARCHAR(32)  NOT NULL,
  created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  hit_count      INT DEFAULT 0,
  KEY idx_req (requirement_id)
);
```

**Step 3.3: Build the key.**

```python
def cache_key(agent, req, facts, mode) -> str:
    relevant = {k: facts.get(k) for k in sorted(req.depends_on)}
    payload = json.dumps({
        "agent": agent, "req": req.id, "mode": mode,
        "facts": relevant, "applicability": req.applicability_code,
        "kb": KB_VERSION, "prompt": PROMPT_VERSION, "model": PRIMARY_MODEL,
    }, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
```

Include `PROMPT_VERSION` and model so changing a prompt or model invalidates old answers automatically. Exclude persona (Phase 7): persona is applied separately so it never splits the cache.

**Step 3.4: Wire it into `run`.** Before prefetch, split scope into hits and misses.

1. Hits: load `draft_json`, add `source="cache"` to the trace, increment `hit_count`.
2. Misses: prefetch and report only those requirements (a smaller single call).
3. All hits: skip Gemini entirely for that agent.
4. After a successful report, write each new finding to the cache.

**Step 3.5: Keep citation validation honest for cached findings.** The strict filter accepts only chunks "retrieved in this run". For a cache hit, re-load its `cited_chunk_ids` from `legal_chunks` (current `kb_version`) and register them with the toolbox as retrieved. If a chunk no longer exists, treat the entry as a miss.

**Step 3.6: Keep the existing failure fallback.** `with_cache` still returns the last full result with `cached=true` when an agent fails. The new cache sits in front of it, not instead of it.

**Step 3.7: Never cache what code decides.** Status, score, Now/Next/Later columns and threshold progress are recomputed every run from applicability and calculators. Only Gemini's draft text and claims are cached.

**Done when:** running the same profile twice shows 3 requests then 0, and changing one tax-only fact reruns only the affected tax findings.

## Phase 4: Agent memory and incremental reassessment

Give each agent a per-business memory in TiDB so it knows what it concluded last time, what the owner has told it, and what changed since; on rerun only agents whose facts changed do any work. This is what makes them feel like real agents rather than prompts. Effort: 3 hours. Owner: Developer 2.

**Cache vs memory:** the Phase 3 cache is global and impersonal (any business with identical facts shares an answer). Memory is per business and per agent: it holds that owner's history, confirmations and completed steps, and it drives the "what changed" story in the UI and chat.

**Step 4.1: Create the memory table.**

```python
class AgentMemory(TableModel):
    __tablename__ = "agent_memory"
    id: str = Field(primary_key=True)
    business_id: str = Field()
    agent: str = Field()              # registration | tax | employer | shared
    kind: str = Field()               # snapshot | note | confirmation | completion | dismissal
    requirement_id: str | None = Field(default=None)
    content: str = FullTextField()    # human-readable line, searchable
    data: dict = Field(sa_type=JSON)  # structured payload
    assessment_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    content_vec: list[float] = embed_fn.VectorField(source_field="content")
```

The vector + full-text fields let chat recall relevant memories with the same hybrid search from Phase 1. If you are short on time, drop `content_vec` and filter by `business_id` + `agent` in SQL; recall still works for a single business.

**Step 4.2: What gets written, and when.**

| kind | Written when | Example content |
| --- | --- | --- |
| snapshot | End of every successful assessment, per agent | Facts used + finding IDs + cache keys |
| confirmation | Owner confirms a proposed fact (intake or chat) | "Owner confirmed: plans to hire in Jan 2027" |
| completion | Owner marks an action item done | "Owner says BC PST registration completed" |
| dismissal | Owner marks a finding not relevant, with reason | "Owner: does not sell taxable goods in BC" |
| note | Chat surfaces a durable detail | "Owner sells at weekend markets in Burnaby" |

All writes are plain code. Gemini never writes memory directly; proposed facts still need the owner's confirmation (unchanged rule).

**Step 4.3: The diff on reassessment.** In the orchestrator, before planning:

1. Load each agent's latest `snapshot` for this business.
2. Compare current facts to the snapshot's facts, per requirement, using `depends_on`.
3. Build a `ChangeSet`: changed facts, affected requirements, affected agents, and requirements newly in or out of scope.
4. Agents with no affected requirements return their snapshot findings directly (0 calls; still re-finalized so status and score are fresh).
5. Affected agents run only the affected requirements (and the Phase 3 cache may still catch some).

**Step 4.4: Feed memory into the prompt (cheaply).** For agents that do run, add a short `<memory>` block: the owner's confirmations, completions and dismissals for the requirements in this call. Cap at about 10 lines. This lets the explanation say "You told us you registered for PST in September, so this is marked done" without another call.

**Step 4.5: Surface it.** Return `changes_since_last` on the assessment response, for example "You added your first employee, so the employer agent re-checked 4 requirements. Registration and tax were unchanged." Show it at the top of the results page. Great demo moment.

**Step 4.6 (optional): mem9.** TiDB's mem9 is a managed memory layer with hybrid retrieval, built mainly for agent harnesses like OpenClaw, OpenCode and Claude Code ([How we built mem9](https://www.pingcap.com/blog/how-we-built-mem9-agent-memory-product/)). For this project a table in your own cluster is simpler and fully under your control. Mention mem9 in the pitch as the production path if judges ask about scaling memory.

**Done when:** adding one employee-related fact to a saved business reruns only the employer agent, the response explains what changed, and the ledger shows 0 to 1 requests.

## Phase 5: Precomputed requirement explanations

Generate a base explanation with citations for every requirement once, at seed time, and store it in TiDB; at runtime clear-cut requirements use the stored text with facts filled in, and only gray areas go to Gemini. Effort: 2 hours. Owner: Developer 1 or 2. Do this after Phases 2 to 4; it is a bonus saving, not a dependency.

**Why:** what a Vancouver business licence is, who issues it and what the official source says is the same for every user. Paying Gemini to rewrite it per assessment is waste.

**Step 5.1: Seed script** `scripts/precompute_explanations.py`. For each requirement in the registry, run Phase 1 retrieval with its `default_queries`, make one structured Gemini call, validate citations, and store the result. Run it once per `kb_version` bump (throttle to 4 requests per minute on the free tier).

```sql
CREATE TABLE requirement_explanations (
  requirement_id  VARCHAR(128) NOT NULL,
  kb_version      VARCHAR(32)  NOT NULL,
  summary         TEXT NOT NULL,        -- what it is, plain language
  why_it_applies  TEXT NOT NULL,        -- template with {fact} slots
  how_to_comply   TEXT NOT NULL,
  claims_json     JSON NOT NULL,        -- each claim + cited chunk IDs
  is_gray_area    BOOLEAN NOT NULL,
  PRIMARY KEY (requirement_id, kb_version)
);
```

**Step 5.2: Templates with fact slots.** `why_it_applies` uses slots filled by code, for example "Because your business is located in {business\_address\_city} and operates as a {business\_type}, ...". Missing facts render as "we don't know yet", never as false (same rule as `get_profile_fact`).

**Step 5.3: Routing rule at runtime.**

| Situation | Source of the explanation | Gemini calls |
| --- | --- | --- |
| Applicability is clear, not a gray area, explanation exists | Stored template + facts | 0 |
| Gray area, or `undetermined` applicability | Agent single call (Phase 2) | shared in 1 per agent |
| Low confidence after report | Escalation (Phase 2.4) | +1 |

In practice most required-now items for a simple sole proprietor are clear-cut, so an agent may have nothing left to send.

**Step 5.4: Citations still validate.** Stored claims cite chunk IDs from the same `kb_version`. At runtime, register those IDs with the toolbox as retrieved (same trick as Phase 3.5) so the strict filter keeps working unchanged.

**Done when:** a simple no-employee sole proprietor assessment makes 0 to 1 requests on a first run, and every stored explanation shows at least one valid citation.

## Phase 6: Chat at one call

Answer each chat question with one structured Gemini call, built from the business's stored findings, its agent memory and a hybrid search over the knowledge base; no investigate loop, and the classifier only on true ties. Effort: 2 hours. Owner: Developer 2.

**Step 6.1: Routing without Gemini (mostly).** Keep keyword rules. Add a second deterministic tier before the classifier: run hybrid search on the question across all chunks and route to the agent that owns the top-ranked chunks. Only if that still ties, call the Gemini classifier. Expected: classifier on under 10% of questions.

**Step 6.2: Build the chat context in code.**

1. The routed agent's latest findings for this business (from the snapshot, Phase 4).
2. The top 5 chunks from hybrid search on the question, scoped to that agent (Phase 1), registered as retrieved so citations validate.
3. Up to 5 relevant memory lines (confirmations, completions, notes) via hybrid search on `agent_memory` filtered by `business_id`.
4. The last 3 conversation turns (unchanged).

**Step 6.3: One structured call** returning `ChatAnswerDraft` (answer, claims with chunk IDs, proposed facts). Same citation filter and "no official source found, ask X" fallback as today. Proposed facts still need owner confirmation.

**Step 6.4: Answer cache for common questions.** Key on `sha256(normalized_question + agent + relevant fact hash + kb_version)`. Demo questions like "Do I need a business licence?" will repeat; answer them for free.

**Step 6.5: Escalate only on empty evidence.** If hybrid search returns nothing above a relevance cutoff, allow one investigate round (max 2 tool calls). Log it.

**Step 6.6: Chat writes memory.** When the owner confirms a proposed fact in chat, write a `confirmation` memory line and mark the affected requirements stale, so the next assessment reruns only those (Phase 4 diff).

**Done when:** a typical chat question costs 1 request (ledger), repeated demo questions cost 0, and answers still carry valid citations.

## Phase 7: persona\_voice

Give each agent an original named character whose voice shapes only the human-facing summary and chat tone, at zero extra Gemini calls; findings, claims, citations and status stay neutral and code-validated. Effort: 2 to 3 hours (half of it UI). Owner: Developer 2 (backend), whoever owns frontend (cards).

**Rules that do not bend**

- Original characters only. No Harvey Specter or any other existing character's name, likeness or catchphrases (that is someone else's IP). An archetype like "the sharp closer" is fine.
- Persona text never contains a legal claim that is not already in a validated finding. It re-voices, it does not add facts.
- Persona never says it is a lawyer, never promises outcomes, never says "you're fully compliant". The UI keeps a visible "Not legal advice" line.
- Persona never affects status, score, scope, confidence or which chunks are cited.

**Step 7.1: Define personas in code** (`agents/personas.py`). Names below are placeholders; rename them as a team.

```python
@dataclass(frozen=True)
class Persona:
    id: str
    agent: str
    display_name: str
    role_title: str
    avatar: str                     # path to an original illustration
    voice_rules: tuple[str, ...]    # 3 to 5 short style rules
    banned: tuple[str, ...]         # phrases and moves it must avoid
    templates: dict[str, str]       # zero-call lines, see 7.4

REGISTRAR = Persona(
    id="registrar_v1", agent="registration",
    display_name="<name TBD>", role_title="Registration specialist",
    avatar="/avatars/registrar.png",
    voice_rules=(
        "Precise and orderly; lists steps in the order an office would process them.",
        "Dry, understated humour, at most one light line per reply.",
        "Always names the issuing office (City of Vancouver, BC Registries).",
    ),
    banned=("guarantee", "you're fully compliant", "as your lawyer"),
    templates={"all_clear": "Your paperwork is in order for now. I'll flag it the moment that changes.",
               "n_open": "{n} filings need your attention. Start with {first_title}."},
)
# TAX_PERSONA: numbers-first, calm about thresholds, shows how close you are
# EMPLOYER_PERSONA: warm, practical HR lead, plain language about first hires
```

**Step 7.2: The prompt block.** Appended to the agent's system prompt only for the human-facing field.

```text
<persona_voice>
You are writing ONLY the `summary` field in the voice of {display_name}, {role_title}.
Style rules: {voice_rules}
Never use: {banned}
The summary is 1 to 2 sentences. It may only reference requirements, counts and facts that
appear in the findings you produced above. Do not add new legal claims, numbers or deadlines.
All other fields (explanation, claims, flags) stay neutral, factual and voice-free.
</persona_voice>
```

**Step 7.3: Schema change.** Add `summary: str` to `AgentReport` (agent level, not per finding) and keep `ChatAnswerDraft.answer` as the voiced field with `claims` neutral. Bump `PROMPT_VERSION`.

**Step 7.4: Zero-call voice for cached runs.** When an agent makes no Gemini call (Phase 3, 4 or 5 hit), build its summary from the persona's `templates` in code (`all_clear`, `n_open`, `changed_since_last`). The persona stays present even at 0 requests.

**Step 7.5: Cache interaction.** Findings are cached neutral (Phase 3 key excludes persona). The voiced `summary` is stored on the agent's memory snapshot (Phase 4) with `persona.id`, so changing a persona version only regenerates summaries, never findings.

**Step 7.6: Guardrail check in code** after every voiced field:

1. Reject if any banned phrase appears (case-insensitive).
2. Reject if the text contains a number, dollar amount or date that does not appear in the findings or calculator results.
3. On reject, fall back to the template line (7.4). No retry call.

**Step 7.7: Chat.** The routed agent's persona voices `answer`; the claims list underneath stays plain with source links. Add the persona name and avatar to each chat bubble so owners see who answered.

**Step 7.8: UI.**

- One card per agent on the results page: avatar, name, role, voiced summary, then the neutral findings below.
- A "Voice" toggle (Full / Plain). Plain hides the persona summary and shows the neutral findings only. Useful for judges who want the facts and as a safety valve.
- Keep "Not legal advice. Confirm with the issuing office or a professional." visible on every card.

**Done when:** each agent card shows a voiced summary, cached runs still show persona lines with 0 requests, and the guardrail test (Testing section) passes.

## Phase 8: Rate limit hardening

Add a client-side token bucket so the app never exceeds the free tier's 5 requests per minute in the first place, instead of discovering the limit through 429s and retries. Effort: 1 hour. Owner: Developer 2.

1. **Token bucket in `llm.py`.** One `asyncio` limiter shared by every call: 4 requests per rolling 60 seconds (leave 1 of headroom for the health check and teammates). Calls wait for a slot instead of firing and failing.
2. **Priority lanes.** Chat > assessment report > escalation > seed scripts. A waiting chat request jumps the queue so the demo never stalls on a background job.
3. **Retries count against the bucket.** Today a 429 retry can fire again immediately into the same wall; route retries through the limiter.
4. **Keep the 503 fallback** to the backup model, but log `model_used` in the ledger so you know which answers came from it. Include the model in cache keys (already in Phase 3.3).
5. **Demo mode.** A `DEMO_PREWARM` script that runs the 3 demo profiles and the 5 demo chat questions before you present, filling the caches. On stage, everything returns at 0 requests and instantly. Run a cold one live only to show the ledger.
6. **Graceful partial results.** If the bucket would make the user wait more than 20 seconds, return what is cached or templated now and stream the rest (or show "Tax specialist is still reviewing"), rather than blocking the whole page.

**Done when:** hammering the assess endpoint 5 times in a row produces zero 429s in the ledger.

## Testing and verification

Extend the existing `tests/fake_gemini.py` setup so every phase has a test that asserts the request count, not just the output. The fake already isolates tests from real Gemini; add a call counter to it.

| Test | Asserts | Phase |
| --- | --- | --- |
| `test_ledger_counts_calls` | Ledger records purpose, agent, retries | 0 |
| `test_retrieve_many_no_llm` | Prefetch retrieval makes 0 Gemini calls, returns stable chunk IDs | 1 |
| `test_first_run_three_calls` | Fresh profile = exactly 3 fake calls | 2 |
| `test_citations_unchanged` | Prefetch path drops no more claims than legacy path on the same fixture | 2 |
| `test_escalation_bounded` | Low-confidence finding triggers at most 1 extra round per agent | 2 |
| `test_same_facts_zero_calls` | Second identical run = 0 calls, same findings | 3 |
| `test_unrelated_fact_keeps_cache` | Changing a fact outside `depends_on` = 0 calls | 3 |
| `test_kb_bump_invalidates` | New `kb_version` = cache misses | 3 |
| `test_status_never_from_cache` | Cached draft + changed applicability still shows the new status | 3 |
| `test_incremental_employer_only` | Adding an employee fact reruns only employer agent | 4 |
| `test_changes_since_last` | Response explains the change set | 4 |
| `test_clear_cut_uses_template` | Non-gray requirement uses stored explanation, 0 calls | 5 |
| `test_chat_one_call` | Typical question = 1 call, repeated question = 0 | 6 |
| `test_persona_guardrail` | Summary with a banned phrase or a new number falls back to template | 7 |
| `test_persona_not_in_findings` | Explanations and claims contain no persona voice markers | 7 |
| `test_no_429_under_burst` | 5 rapid assessments produce no 429 in the ledger | 8 |

**Manual checks before demo**

- [ ] Run the 3 baseline profiles from Phase 0 and fill a before/after table with real ledger numbers.
- [ ] Read every voiced summary for the demo profiles out loud; nothing should sound like legal advice.
- [ ] Click every source link on the demo results page; each must open the official page.
- [ ] Flip the Voice toggle to Plain and confirm nothing factual disappears.

## Build order and checklist

Build in three tiers so the demo improves at every step: Must (biggest saving, about 8 hours), Should (memory and persona story, about 7 hours), Nice (extra savings, about 4 hours). Developer 1 runs Phase 1 in parallel with Developer 2's Phase 2; prefetch works against the current stub until hybrid search lands.

**Must: cut calls from about 12 to 3, then to 0 on repeats**

- [ ] Phase 0: ledger + baseline numbers (Dev 2)
- [ ] Phase 1.1: confirm cluster region supports full-text (Dev 1, do first)
- [ ] Phase 1.2 to 1.6: hybrid search + `retrieve_many` + `default_queries` (Dev 1)
- [ ] Phase 2: `EvidencePack`, `prefetch`, single report call, feature flag (Dev 2)
- [ ] Phase 2.4: bounded escalation (Dev 2)
- [ ] Phase 3: `depends_on` in registry + `finding_cache` (Dev 1 registry, Dev 2 cache)
- [ ] Phase 8.1 to 8.3: token bucket + retries through it (Dev 2)

**Should: the "real agents" story**

- [ ] Phase 7: personas, `summary` field, guardrail, templates (Dev 2)
- [ ] Phase 7.8: agent cards + Voice toggle (frontend)
- [ ] Phase 4: `agent_memory`, diff, `changes_since_last` (Dev 2)
- [ ] Phase 6: chat at 1 call + answer cache (Dev 2)
- [ ] Phase 8.5: demo prewarm script (anyone)

**Nice: squeeze the rest**

- [ ] Phase 5: precomputed explanations + seed script
- [ ] Phase 1.7: reranker, only if retrieval looks weak
- [ ] Phase 4.1: vector field on memory for semantic recall
- [ ] Phase 8.6: partial results streaming

**Dependencies to respect**

1. Phase 3 needs `depends_on` (3.1) before the cache can key correctly.
2. Phase 4 diff reuses `depends_on` and the snapshot written after Phase 2 runs.
3. Phase 7.5 stores summaries on the Phase 4 snapshot; until Phase 4 lands, store them on the assessment row.
4. Phase 6 context uses Phase 4 snapshots; until then, use the latest saved findings.

## Cursor prompts per phase

Paste one prompt per phase into Cursor with the listed files attached; each prompt names the constraint that must not break, so the AI does not "simplify" away your guardrails. Export this doc as Markdown and add it to the repo as `docs/agent-upgrade-plan.md` so Cursor can reference it with @.

**Context line to start every prompt**

```text
Read @docs/agent-upgrade-plan.md. Hard rules: status/score/scope come from code only; only chunks
retrieved in the current run (or re-registered from cache) may be cited; unknown facts are known=false,
never false; tests use tests/fake_gemini.py and must never call real Gemini.
```

**Phase 0** (attach `core/llm.py`, `agents/orchestrator.py`)

```text
Implement Phase 0. Add a contextvar-scoped CallLedger to core/llm.py that records every real Gemini
request (purpose, agent, model, attempt, status, latency, tokens, cache_hit). Add purpose/agent kwargs
to generate_content and generate_structured with safe defaults. Persist a summary on the assessment and
return it from GET /assessments/{id}/trace. Add test_ledger_counts_calls using the fake.
```

**Phase 1** (attach the retrieval stub, registry file)

```text
Implement Phase 1 steps 1.2 to 1.6 with pytidb. Create the LegalChunk table as specified, implement
retrieve() with search_type="hybrid" filtered by requirement_id and kb_version, and retrieve_many().
Keep the existing retrieval function signature. Add default_queries to each registry requirement.
If FULLTEXT_AVAILABLE=false, use the Step 1.5 fallback. Add test_retrieve_many_no_llm.
```

**Phase 2** (attach `agents/base.py`, `agents/tools.py`, `agents/tax.py`, `agents/employer.py`)

```text
Implement Phase 2. Add EvidencePack and BaseAgent.prefetch() that uses the existing AgentToolbox methods
(so retrieved-chunk tracking and trace entries keep working). Change run() to prefetch + one
generate_structured call, behind settings.AGENT_MODE ("prefetch" default after tests pass, "legacy"
keeps old path). Add bounded escalation per Step 2.4. Add tests: first_run_three_calls,
citations_unchanged, escalation_bounded.
```

**Phase 3** (attach `agents/orchestrator.py`, `agents/base.py`, registry)

```text
Implement Phase 3. Add depends_on to requirements, the finding_cache table, cache_key() exactly as in
Step 3.3, and hit/miss splitting in run(). Re-register cited chunk IDs for cache hits per Step 3.5.
Never cache status, score, columns or threshold progress. Keep with_cache as the failure fallback.
Add the four Phase 3 tests.
```

**Phase 4** (attach orchestrator, chat service)

```text
Implement Phase 4. Create agent_memory, write snapshot/confirmation/completion/dismissal entries from
code only, compute a ChangeSet from depends_on before planning, skip unaffected agents (still
re-finalize their findings), add a capped <memory> block to prompts, and return changes_since_last.
Add test_incremental_employer_only and test_changes_since_last.
```

**Phase 6** (attach `chat/router.py`, `chat/service.py`)

```text
Implement Phase 6. Add hybrid-search routing before the Gemini classifier, build chat context from
snapshot findings + scoped hybrid search + memory lines + last 3 turns, make one structured call, add
the answer cache, and allow one investigate round only when evidence is empty. Add test_chat_one_call.
```

**Phase 7** (attach `agents/base.py`, agent subclasses, chat service, results page component)

```text
Implement Phase 7. Create agents/personas.py with the Persona dataclass and three ORIGINAL personas
(no existing fictional characters). Add a persona_voice block that applies only to AgentReport.summary
and ChatAnswerDraft.answer. Add template-based summaries for zero-call runs and the Step 7.6
guardrail with template fallback. Bump PROMPT_VERSION. Add both persona tests. Then build agent
cards with avatar, name, role, summary, and a Full/Plain voice toggle.
```

**Phase 8** (attach `core/llm.py`)

```text
Implement Phase 8. Add a shared asyncio token bucket (4 requests / 60 s) with priority lanes
(chat > report > escalation > scripts); route retries through it; log model_used. Add
scripts/demo_prewarm.py for the 3 demo profiles and 5 demo questions. Add test_no_429_under_burst.
```

**Review prompt after each phase**

```text
Review the diff against the plan's "Done when" for this phase and the hard rules. List anything that
lets Gemini set status, cite an unregistered chunk, treat unknown as false, or call real Gemini in
tests. Do not refactor unrelated code.
```

## Demo and pitch talking points

Lead with one line: "Gemini only gets called when actual reasoning is needed; everything else is deterministic, cached or remembered." Then prove it with the ledger badge on screen.

**Demo script (about 90 seconds)**

1. Cold assessment of a new sole proprietor. Ledger badge: "Gemini calls: 3 (baseline 12)." Show the three persona cards.
2. Run it again. Badge: "Gemini calls: 0." Same results, instant.
3. Add "I'm hiring my first employee in January." Banner: "Employer specialist re-checked 4 requirements; registration and tax unchanged." Badge: 1.
4. Ask chat "Do I need WorkSafeBC coverage?" The employer persona answers in voice, with neutral cited claims and source links underneath. Badge: 1.
5. Flip Voice to Plain to show the facts never depended on the persona.

**Talking points by judging angle**

- Technical depth: hybrid keyword + vector retrieval in TiDB, per-requirement fact-dependency cache, per-business agent memory with incremental reassessment, bounded escalation.
- Trust: status from code, strict citation validation, unknown never treated as false, persona guardrails, "not legal advice" on every card.
- Cost and sustainability (UNSDG angle): about 75% fewer model calls on first run and near zero on repeats; works inside a free tier.
- Design: three characters make compliance feel less intimidating for first-time founders; the Plain toggle keeps it professional.
- Scale story: TiDB's Agent State Stack (TiDB Cloud Zero, mem9, drive9) is the production path for agent memory and state ([TiDB press release](https://www.pingcap.com/press-release/tidb-launches-agent-state-stack-super-ai-singapore/)).

**Likely judge questions**

- "Isn't this just a Gemini wrapper?" No: code owns scope, status, scoring, retrieval, caching and memory; Gemini writes cited explanations for the parts that need judgment.
- "What if the law changes?" Re-seed chunks and bump `kb_version`; every cached answer tied to the old version expires automatically.
- "What stops the persona from giving bad advice?" It can only re-voice validated findings, and a code check rejects new numbers, dates or banned phrases.

## Sources

- [pingcap/pytidb on GitHub](https://github.com/pingcap/pytidb)
- [TiDB hybrid search docs](https://docs.pingcap.com/ai/vector-search-hybrid-search)
- [TiDB full-text search with Python](https://docs.pingcap.com/ai/vector-search-full-text-search-python)
- [How we built mem9](https://www.pingcap.com/blog/how-we-built-mem9-agent-memory-product/)
- [TiDB Agent State Stack press release](https://www.pingcap.com/press-release/tidb-launches-agent-state-stack-super-ai-singapore/)
