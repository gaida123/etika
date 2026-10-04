# StormHacks Compliance Navigator: PM Handoff

Oct 3, 2026 · @Freya

## 1. Overview

We are building a compliance navigator that tells a new BC sole proprietor exactly which registrations, tax accounts and employer obligations apply to them, why, and what to do next, with every claim linked to an official government source.

**Product in one sentence:** a business owner answers a few questions, three specialist AI agents check their situation against official BC and federal sources, and they get a readiness score, cited explanations, upcoming triggers, and direct links to act.

**Who it is for (MVP persona)**

- **Structure:** unincorporated sole proprietor, the default for most people starting out.
- **Stage:** pre-launch through the first year, when nearly every registration decision happens for the first time.
- **Size:** solo, or about to make a first hire or two.
- **Business type:** product or service businesses run from home, online, or both (handmade goods shop, freelance designer, tutor, photographer, small online store).
- **Situation:** no lawyer, accountant or HR person. They piece things together from government websites, Reddit and friends.

**Jurisdiction:** City of Vancouver, Province of BC, and federal (CRA) rules that apply to a Vancouver-based sole proprietor.

**The three legal areas in scope**

1. Registration and licensing: "Am I allowed to exist and operate here?"
2. Tax registration: "Do I have to charge tax, and when?"
3. Employer obligations: "What changes the day I hire someone?"

**Why we win against what exists today**

| Alternative | What it does | What it misses |
| --- | --- | --- |
| BizPaL | Lists permits and licences that may apply, with links | Does not say what does apply, no next steps, no triggers |
| Ownr | Registers a sole proprietorship name ($49 + GST) | Registration only; GST registration in Ownr is for corporations only |
| Small Business BC checklist | Generic startup checklist | Not personalised, no triggers |
| DIY (gov sites, Reddit, friends) | Free | Scattered, mixed quality, no one flags thresholds |
| Accountant | Tax and payroll advice | Costly; rarely covers licensing; only knows what you tell them |

We are the only option that covers all three areas, says what applies and why, cites the official source, gives the next action with a direct link, and flags new triggers (first hire, $10,000 PST line, $30,000 GST line).

**Hackathon prize tracks we are targeting**

| Track | How we qualify | Owner |
| --- | --- | --- |
| TiDB x AI Open Build | TiDB vector search (and full-text/hybrid if region allows) powers retrieval; agent traces stored in TiDB | Developer 1 |
| MLH Best Use of Gemini API | Gemini Flash runs intake, the three agents, chat and drafts; Gemini embeddings | Developer 2 |
| SSSS Python track | Entire backend is Python (FastAPI) | Both devs |
| MLH Best .Tech Domain | Register a .tech domain for the deployed app | PM |
| Enactus UNSDG track | Pitch framing: SDG 8.3 (small business formalization), 16.3 (access to justice), 17 (built on government open data) | Business |
| IATSU Best Design | Figma design turned into the front end | Designer |

Check StormHacks rules on how many sponsor tracks one project can enter and whether pre-event designs or research are allowed.

## 2. Business logic (the most important section)

The product is only trustworthy if these rules are implemented exactly as written. Code decides what applies and calculates the score; AI only explains, cites and flags. The research owner must validate every rule below against official sources before it is coded.

### 2.1 Registration and licensing: "Am I allowed to exist and operate here?"

- **Business name registration (BC Registries):** required only if the owner trades under a name other than their own legal name. Provincial registration fee is $40, after a name approval request.
- **City of Vancouver business licence:** required to operate in Vancouver. Research owner must confirm how this applies to home-based and online-only businesses.
- **CRA business number:** needed before opening a GST account or a payroll account.
- **Why it matters:** everything else (bank account, tax registrations, operating legally) sits on top of this. It is also the cheapest stage to fix, roughly $150 in total fees (research owner to confirm the Vancouver licence fee before we quote this).

### 2.2 Tax registration: "Do I have to charge tax, and when?"

This is where new businesses most often go wrong, because BC has two sales taxes with different triggers.

| Tax | Trigger | Key details |
| --- | --- | --- |
| BC PST (provincial) | Applies almost immediately to anyone selling taxable goods | Small seller exemption only if BOTH: gross sales of $10,000 or less over the past 12 months (rolling window, not calendar year) AND no established business premises. Some seller types never qualify. |
| GST (federal) | Must register once over $30,000 | Test is $30,000 in a single calendar quarter or over four consecutive quarters (research owner to confirm wording against CRA). Voluntary registration earlier is allowed. |

Rules the engine must respect:

- **Goods vs services matters.** PST mostly applies to goods; most services in our persona (designer, tutor, photographer) are not PST-taxable. As of October 1, 2026, PST expanded to certain professional services (accounting, architecture, engineering and others). The tax logic must ask "goods, services or both?" first.
- **Rolling windows.** One busy season can end PST small seller status. Calculators must use monthly revenue, not a single annual number.
- **Gray area to flag, not resolve:** regular sales at markets or fairs may affect the "no established premises" condition. Flag for review.

### 2.3 Employer obligations: "What changes the day I hire someone?"

Hiring the first person is the biggest single jump in legal responsibility. On day one, these switch on:

1. WorkSafeBC registration.
2. A CRA payroll account (requires a business number).
3. Minimum wage of $18.25/hour (in effect since June 1, 2026).
4. A pay statement every payday.
5. Payroll records kept for the required period (we have stated four years; research owner must confirm the exact rule).

Gray area to flag: whether someone is an employee or a contractor. The agent explains the question and recommends checking; it never decides.

### 2.4 Rules that apply across everything

- **Unknown is never false.** If a fact is missing (for example revenue), the requirement is "undetermined" and we ask for it. We never assume the owner is fine.
- **Every requirement has a timing:** `now` (required today), `trigger` (switches on at a threshold or event), or `recommendation` (good practice, never counted in the score).
- **Dependencies set the order of next steps:** name registration, then business number, then GST or payroll accounts.
- **Links come only from the registry.** The AI never invents a URL, fee, deadline or form.
- **No official evidence, no claim.** If retrieval finds nothing, we say "we couldn't find an official source for this" and suggest who to ask.
- **We give legal information, not legal advice.** A disclaimer is shown, and gray areas route to a professional.

### 2.5 How the readiness score works

The score answers: "Of the things legally required of you today, how many have you done?"

- Only `required_now` legal obligations count toward the score.
- `upcoming` triggers, recommendations and undetermined items are shown separately and never lower the score.
- Each requirement has a priority weight: high = 3, medium = 2, low = 1.
- Status credit: done = 1.0, in progress = 0.5, not done = 0.
- Score = 100 x (sum of weight x credit) / (sum of weights), calculated per area and overall.
- Same answers always produce the same score. This is our main answer to "isn't this just ChatGPT?"

## 3. User workflow and demo persona

The owner goes from a short intake to a scored, cited action plan in one flow, and any confirmed change to their facts re-runs the whole assessment.

### 3.1 Step by step (what the owner experiences)

1. **Intake.** The owner fills a short form and optionally writes one or two sentences about their business.
2. **Confirm facts.** The system turns the description into proposed facts (for example "sells: both goods and services"). The owner confirms or edits each one.
3. **Follow-up questions.** If facts are missing (monthly revenue, trading name, hiring plans), the system asks targeted questions. The owner can skip; skipped facts stay "unknown".
4. **Assessment.** The three agents run and the owner sees a readiness score.
5. **Dashboard: now, next, later.**
   - Now: what is required today, each with a "Go here" link. This is what the score measures.
   - Next: approaching triggers ("you are at $8,200 of the $10,000 PST line; estimated to cross around March").
   - Later: what switches on when you hire.
6. **Why?** Each card expands to show the official source passage and link, plus the agent trace.
7. **Chat.** The owner asks questions; answers are grounded in official sources and cited.
8. **Actions.** Checklists, official links and inquiry email drafts. The owner sends drafts themselves; nothing is sent automatically.
9. **Update.** If the owner mentions a change in chat ("I'm hiring help next month"), the system proposes a fact update. Once confirmed, a new profile version is saved and the assessment re-runs.

### 3.2 Demo persona: Maya, "Wick & Co"

Maya makes candles in her Vancouver apartment and sells on Etsy and at weekend markets. One persona is used end to end so the story stays simple.

| Demo moment | What happens on screen | Area |
| --- | --- | --- |
| Trading name "Wick & Co" differs from her legal name | Name registration appears under Now, with the BC Registries link | Registration |
| Home-based in Vancouver | Business licence appears under Now (or flagged, depending on research findings) | Registration |
| About $8,200 in sales over the past 12 months, growing | PST small seller status holds today; PST registration shows under Next with an estimated crossing month | Tax |
| Regular weekend market sales | Flagged for review: may affect the "no established premises" condition | Tax |
| Well under $30,000 | GST shown as not yet required; voluntary registration shown as a recommendation | Tax |
| Mid-demo in chat: "I'm hiring help for the holidays" | Fact update proposed, confirmed, re-run: the five employer obligations move from Later to Now and the score updates | Employer |

The hiring moment is the climax of the demo: "five obligations switch on in one day", happening live.

## 4. System architecture and tech stack

One Python backend, one TiDB database and one Gemini model family; the only AI calls are intake, the three agents, chat and email drafts.

### 4.1 Tech stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.11 | Qualifies for the Python track |
| API | FastAPI + Uvicorn, Pydantic v2 | All routes and data contracts |
| Database | TiDB Cloud Starter | Relational data, vectors, full-text; one store only |
| DB access | SQLAlchemy 2 + PyMySQL, or the `pytidb` SDK for search | Pin `pytidb` version; its API changes quickly |
| LLM | Gemini Flash via `google-genai` | Model name in config; check current name on the day |
| Embeddings | `gemini-embedding-001` | One fixed model and dimension; 2,048-token input limit per chunk |
| Ingestion | `httpx`, BeautifulSoup, `lxml`, `pypdf` | Approved sources only |
| Tests | Pytest + FastAPI test client | Acceptance tests in section 10 |
| Front end | Figma design, built by the designer (React, TypeScript, Vite, Tailwind) | Calls the FastAPI routes in section 8 |
| Hosting | Backend on Render, Railway or Fly.io; front end on Vercel | `yourname.tech` to front end, `api.yourname.tech` to backend via CNAME |

Do not add LangChain, LangGraph, Celery, Redis, a second vector database or separate microservices.

**TiDB region warning:** full-text search (needed for hybrid search) is only available in certain TiDB Cloud Starter regions. Create the cluster in a supported region on day one and confirm the feature works. Vector search alone still qualifies for the TiDB track.

### 4.2 TiDB data model

| Table | What it holds | Owner |
| --- | --- | --- |
| `sources` | One row per official page or document: URL, authority, title, retrieved date, version, content hash | Developer 1 |
| `chunks` | Section-sized text pieces with metadata, embedding vector, full-text index | Developer 1 |
| `requirements` | The registry: every obligation with its rules, timing, dependencies, links (section 7) | Developer 1 (content approved by research owner) |
| `business_profiles` | Versioned facts per business; each fact has value + confirmed flag | Developer 2 |
| `revenue_entries` | Monthly revenue amounts per business, used by tax calculators | Developer 2 writes, Developer 1 reads |
| `assessments` | One row per run, tied to a profile version | Developer 1 |
| `findings` | One row per requirement per assessment: status, explanation, cited chunk IDs, flags, confidence | Developer 2 writes, Developer 1 scores |
| `agent_runs` | Every agent tool call and result (the "agent trace") | Developer 2 |
| `conversations` | Chat history: question, rewritten query, retrieved chunk IDs, claims, sources cited, proposed fact updates | Developer 2 |

### 4.3 Repository structure

```text
backend/app/contracts/       Shared Pydantic models (retrieval, findings, profile)
backend/app/knowledge/       Dev 1: ingestion, chunking, embeddings, retrieval
backend/app/assessment/      Dev 1: applicability rules, calculators, scoring, sequencing
backend/app/intake/          Dev 2: fact extraction from free text
backend/app/agents/          Dev 2: orchestrator, base agent, three agents, tools
backend/app/chat/            Dev 2: grounded answers, citation validation
backend/app/actions/         Dev 2: checklists, inquiry drafts
backend/app/api/             Dev 2: FastAPI routes
backend/app/core/            Shared settings, DB setup
backend/data/registry/       Requirement registry (CSV/JSON, reviewed)
backend/scripts/             Ingestion and registry loader scripts
backend/tests/               Tests per module
contracts/examples/          Sample JSON requests and responses for the front end
frontend/                    Designer-owned interface
```

## 5. AI design: intake, engine, orchestrator and three agents

Code decides what applies and how the score is calculated; three specialist agents read official evidence, explain it to the owner, and flag gray areas.

&#91;embedded content: assessment flow · intake to dashboard, 3 agents\]

Tinted boxes call Gemini; outlined boxes are deterministic code. Agents only reach TiDB through the shared tools, and their findings go straight to validation and scoring.

### 5.1 Who decides what

| Decision | Decided by | Why |
| --- | --- | --- |
| Does a rule apply? Is a threshold crossed? | Code (Developer 1) | Must be exact and repeatable |
| Turning a free-text description into facts | Gemini intake call; owner confirms | Messy language is what LLMs are good at |
| Which evidence supports a requirement, and what it means for this owner | Agent (Gemini + tools) | Reading and explaining legal text |
| Gray areas (employee vs contractor, home-based licence edge cases, market stalls) | Agent flags; never resolves | Honest handling of legal uncertainty |
| The score and the order of steps | Code (Developer 1) | Same answers always give the same score |
| Links, fees, next actions | Registry only | No invented URLs or numbers |

### 5.2 Intake (Developer 2)

- One Gemini Flash call with structured output (Pydantic schema) turns the owner's description into proposed facts, each with a confidence score.
- Example: "I sell candles on Etsy and do custom design work" proposes `sells = both`, `online = true`.
- The owner confirms or edits every proposed fact. Unconfirmed facts are never used as true.

### 5.3 Applicability engine and calculators (Developer 1, no AI)

The engine compares each requirement's `applies_if` rule with the confirmed facts and labels it `required_now`, `upcoming`, `not_applicable` or `undetermined` (with the list of missing facts).

Calculators are plain Python functions inside the engine:

- `pst_small_seller_test(profile)`: sums revenue over the rolling 12 months and checks the premises condition. Returns `exempt`, `must_register` or `undetermined`, plus the numbers used.
- `gst_small_supplier_test(profile)`: checks single-quarter and four-consecutive-quarter totals against $30,000.
- `project_crossing(profile, threshold)`: straight-line projection from recent months to estimate when a threshold will be crossed. Always labelled as an estimate.

Missing facts become follow-up questions (Developer 2 writes the wording). This loops until the owner has answered what they can.

### 5.4 Orchestrator (Developer 2, plain Python, not an LLM)

- **Registration agent:** always runs.
- **Tax registration agent:** always runs ("you are under the threshold" is useful too).
- **Employer agent:** full mode if `has_employees = true`; pre-hire mode ("what changes the day you hire") if `plans_to_hire` is true or unknown; skipped if the owner said no.
- Runs active agents in parallel with `asyncio`, collects findings, removes duplicates, and passes them to validation and scoring.

### 5.5 How each agent works

Each agent is a Python class with:

- **Scope:** only requirements whose `area` matches (registration, tax or employer).
- **System prompt:** written as that specialist, listing its known gray areas.
- **Tools:** Python functions Gemini can call (table below).
- **Step limit:** about 6 tool calls per run, so it cannot loop forever.

| Tool | Registration | Tax | Employer | Provided by |
| --- | --- | --- | --- | --- |
| `retrieve_evidence(requirement_id, query)` | Yes | Yes | Yes | Developer 1 retrieval service |
| `get_requirement(id)` | Yes | Yes | Yes | Developer 1 registry |
| `get_profile_fact(key)` | Yes | Yes | Yes | Developer 2 profile service |
| `get_calculator_result(name)` | No | Yes | No | Developer 1 calculators |
| `flag_for_review(requirement_id, reason)` | Yes | Yes | Yes | Developer 2 |

**Two-phase run (per agent):**

1. **Investigate:** Gemini Flash gets the agent's scope and applicability results, then calls tools: pulls evidence for each requirement, reads calculator outputs, checks facts, flags anything ambiguous. The `google-genai` SDK can run Python functions as tools automatically; cap the number of calls.
2. **Report:** a second Gemini call with structured output turns what it gathered into one finding per requirement.

Splitting the phases keeps tool use and strict JSON output from conflicting, and makes each phase easy to debug.

**Finding schema (agent output):**

```python
class Finding(BaseModel):
    requirement_id: str
    status: Literal["done", "in_progress", "not_done", "not_yet_required", "undetermined"]
    explanation: str              # plain English, for the owner
    claims: list[Claim]           # each claim cites source chunk IDs
    flags: list[str]              # gray areas sent for review
    confidence: float             # below ~0.6 becomes "check with a professional"
```

**Agent trace:** every tool call and result is saved to `agent_runs`. The UI shows it as a panel ("Tax agent read PST bulletin, ran the small seller test, flagged market stall sales"). This makes the agentic work visible to judges.

### 5.6 Agent specialisations

| Agent | Owns | Typical gray areas it flags |
| --- | --- | --- |
| Registration | Name registration, Vancouver business licence, CRA business number | Home-based or online-only licensing; using own name with a tagline |
| Tax registration | PST registration, GST registration, voluntary GST, charging tax correctly once registered | Goods vs services split; market stalls and the premises condition; revenue data missing |
| Employer | WorkSafeBC, payroll account, minimum wage, pay statements, payroll records, employee vs contractor | Contractor vs employee; family members helping out |

### 5.7 Validation, scoring and sequencing

- **Citation validation (Developer 2):** drop any claim citing a chunk the agent did not retrieve in this run, and any finding outside the agent's scope.
- **Scoring (Developer 1):** formula in section 2.5; only `required_now` obligations count.
- **Sequencing (Developer 1):** sort next actions by `depends_on` first, then by priority.

### 5.8 Chat and actions (Developer 2)

- A question is routed to the matching agent (a small classifier call or keyword rules), which uses the same tools and validation as the assessment, so chat and dashboard never disagree.
- If retrieval returns `insufficient_evidence`, the answer says so and suggests who to ask.
- If the owner mentions a new fact, the agent proposes a profile update; the owner confirms; the assessment re-runs.
- Inquiry email drafts use the company profile and the specific requirement. Shown with Copy and an "Open in email" link; never sent automatically.

### 5.9 Gemini usage and limits

- Gemini Flash is sufficient for intake, agents, chat and drafts; accuracy comes from the registry, retrieval and code-based scoring.
- Main risk is rate limits, not quality: three agents in parallel, each making several calls. Check quota, consider paid credits, and pre-run and cache the demo persona's assessment as a fallback.
- Keep temperature low for agents and validation-sensitive calls.

## 6. Knowledge base and RAG

About 10 approved official sources are cleaned, split by section, embedded and stored in TiDB; agents and chat only ever answer from what this retrieval returns.

### 6.1 How RAG works here

1. Official sources are collected and cleaned.
2. Each is split into section-sized chunks with metadata.
3. Each chunk is embedded with one fixed Gemini embedding model.
4. Chunks and vectors are stored in TiDB.
5. At run time, an agent asks the retrieval service for evidence for a specific requirement.
6. Retrieval filters by jurisdiction, requirement and date, then searches (vector, or hybrid if available).
7. It returns evidence chunks, or `insufficient_evidence`. It never returns a legal conclusion.

### 6.2 Approved sources (research owner finalises)

| Area | Source | Authority |
| --- | --- | --- |
| Registration | Proprietorship registration package and name request pages | BC Registries |
| Registration | Business licence pages, including home-based business rules | City of Vancouver |
| Registration | Business number page | CRA |
| Tax | PST registration pages and Small Sellers bulletin (PST 003) | BC Ministry of Finance |
| Tax | GST registration and small supplier pages | CRA |
| Employer | Employer registration pages | WorkSafeBC |
| Employer | Employment Standards Act sections on pay statements and records | BC Laws |
| Employer | Minimum wage page | Province of BC |
| Employer | Payroll account page | CRA |
| All | OneStop Business Registration overview (registers business, GST, PST, WorkSafeBC and payroll in one flow) | Province of BC |

Source rules:

- Official government, regulator or legislation sources only. Blogs, Reddit, law-firm summaries and AI summaries can help find topics but are never the authority.
- Every source keeps: URL, authority, title, retrieved date, version or effective date, section heading, original text.
- Do not bulk-scrape CanLII; its terms prohibit it. BC Laws offers an official XML API and an open licence.

### 6.3 Ingestion and chunking (Developer 1)

- **BC Laws:** fetch statute XML through the CiviX document API (add `/xml` to the document URL), parse sections with `lxml`.
- **Government web pages:** fetch the approved URL list with `httpx`, strip navigation with BeautifulSoup, split by heading.
- **Chunk by legal structure** (Act, part, section, or page heading), not fixed token sizes. Keep each chunk well under the 2,048-token embedding limit; split long sections at subsections and repeat the section header.
- **Target:** about 40 to 80 meaningful chunks.

### 6.4 Chunk metadata

`source_id`, `chunk_id`, `authority`, `jurisdiction_ids` (`CA`, `CA-BC`, `CA-BC-VANCOUVER`), `area`, `document_type`, `section_path`, `source_version`, `effective_from`, `effective_to`, `retrieved_at`, `review_status`, `requirement_ids`, `embedding_model`.

### 6.5 Retrieval contract (Developer 1 exposes, Developer 2 consumes)

```python
class RetrievalRequest(BaseModel):
    query: str
    jurisdiction_ids: list[str]
    segment_id: str                 # "home_online_sole_prop"
    area: str | None = None         # registration | tax | employer
    requirement_ids: list[str] = []
    as_of: datetime
    limit: int = 5

class RetrievedChunk(BaseModel):
    chunk_id: str
    source_id: str
    text: str
    title: str
    section_path: str | None
    url: str
    source_version: str
    effective_from: datetime | None
    effective_to: datetime | None
    score: float | None

class RetrievalResult(BaseModel):
    status: Literal["supported", "insufficient_evidence"]
    chunks: list[RetrievedChunk]
    query_used: str
    filters_applied: dict[str, Any]
    limitations: list[str]
```

The retrieval service returns evidence only, never a legal conclusion. No one creates a second vector store or asks Gemini to answer from general knowledge.

## 7. Requirement registry

The registry is the checklist the whole system works from: about 15 to 18 reviewed requirements, written by the research owner in a shared sheet and loaded into the TiDB `requirements` table by a script.

**Why a sheet:** reading laws and writing requirements is research, not code. A sheet lets the business side write and review rows in parallel; `backend/scripts/load_registry.py` loads it into TiDB and is re-run whenever the sheet changes.

### 7.1 Fields

| Field | Example | Notes |
| --- | --- | --- |
| `id` | `TAX-01` | Format: `AREA-NN` |
| `area` | `tax` | `registration`, `tax` or `employer`; decides which agent owns it |
| `title` | Register for BC PST | Plain English |
| `requirement_type` | `legal_obligation` | Or `recommendation` (never scored) |
| `timing` | `trigger` | `now`, `trigger` or `recommendation` |
| `applies_if` | `{"all":["sells in [goods, both]"]}` | Simple JSON rule over confirmed facts |
| `trigger_rule` | `pst_small_seller_test` | Which calculator decides it, if any |
| `required_fact_keys` | `sells, monthly_revenue, has_established_premises` | Missing ones become follow-up questions |
| `depends_on` | `REG-03` | Requirements that must come first |
| `priority` | high | high = 3, medium = 2, low = 1 in the score |
| `source_chunk_ids` | `bc-pst-small-sellers-s2` | Evidence that supports it |
| `action_url` | Official page or form | The only place links come from |
| `preparation_items` | Gather sales records for the past 12 months | Checklist shown to the owner |
| `review_flags` | Market stalls and premises | Known gray areas for the agent |
| `last_verified_at` | 2026-10-03 | When the research owner last checked it |

### 7.2 Starter rows (all need research owner validation)

| ID | Requirement | Timing | Applies when | Depends on |
| --- | --- | --- | --- | --- |
| REG-01 | Register business name with BC Registries | now | Trading under a name other than own legal name | none |
| REG-02 | Get a City of Vancouver business licence | now | Operating in Vancouver, incl. from home (verify home-based and online-only) | none |
| REG-03 | Get a CRA business number | trigger | Needed before GST or payroll accounts | none |
| TAX-01 | Register for BC PST | trigger | Sells taxable goods and fails small seller test | none |
| TAX-02 | Register for GST | trigger | Fails small supplier test | REG-03 |
| TAX-03 | Consider voluntary GST registration | recommendation | Below threshold with significant business purchases | REG-03 |
| TAX-04 | Charge and show the correct tax on invoices once registered | trigger | Registered for PST or GST | TAX-01 or TAX-02 |
| EMP-01 | Register with WorkSafeBC | trigger | First hire | none |
| EMP-02 | Open a CRA payroll account | trigger | First hire | REG-03 |
| EMP-03 | Pay at least $18.25/hour | trigger | First hire | none |
| EMP-04 | Give a pay statement every payday | trigger | First hire | none |
| EMP-05 | Keep payroll records for the required period | trigger | First hire (verify retention period) | none |
| EMP-06 | Check employee vs contractor status | recommendation | Paying anyone for regular work | none |

### 7.3 Fact dictionary (profile)

| Fact | Type | Example | Used by |
| --- | --- | --- | --- |
| `legal_name` | text | Maya Chen | Registration |
| `trading_name` | text | Wick & Co | Registration |
| `trading_name_differs_from_legal_name` | bool | true | Registration |
| `operates_in_vancouver` | bool | true | Registration |
| `home_based` | bool | true | Registration, Tax |
| `online_only` | bool | false | Registration |
| `sells` | goods / services / both | both | Tax |
| `monthly_revenue` | list of month + amount | 12 entries | Tax calculators |
| `has_established_premises` | bool | false | Tax (PST test) |
| `sells_at_recurring_markets` | bool | true | Tax (flag) |
| `has_employees` | bool | false | Employer |
| `plans_to_hire` | bool | true | Employer |
| `planned_hire_date` | month | 2026-12 | Employer |

Every fact is stored as `{value, confirmed}`. Unknown or unconfirmed facts are never treated as false.

## 8. Front end, design brief and API contract

The designer builds from Figma (then into code with Claude Opus) against the API shapes below, so the screens match real data from day one.

### 8.1 Screens

1. **Intake:** one question per screen, plus an optional "describe your business" box.
2. **Confirm facts:** proposed facts as editable chips (confirm, edit, skip).
3. **Results dashboard:**
   - Large score ring with three area subscores (Registration, Tax, Employer).
   - Three columns or tabs: **Now**, **Next**, **Later**.
   - Action cards: priority colour, one-line reason, cost or time note, "Go here" button, "Ask about this", "Draft email".
   - Expandable "Why?" with the cited official passage and source link.
   - "Agent trace" panel showing what each agent checked.
   - Threshold progress bars for PST ($10,000) and GST ($30,000) with the projected crossing month.
4. **Chat:** side panel with cited answers and "confirm this change" prompts for proposed fact updates.
5. **Disclaimer:** visible "general information, not legal advice" note.

### 8.2 API routes (Developer 2 owns)

| Route | In | Out |
| --- | --- | --- |
| `POST /intake/parse` | Free-text description | Proposed facts with confidence |
| `POST /profile` | Confirmed facts + monthly revenue | Profile ID + version |
| `GET /profile/{id}/questions` |  | Follow-up questions for missing facts |
| `POST /assess/{profile_id}` |  | Assessment: overall score, area scores, now/next/later lists, findings |
| `GET /requirements/{id}` |  | Requirement details, citation, action link |
| `GET /assessments/{id}/trace` |  | Agent trace entries |
| `POST /chat` | Question + profile ID | Grounded answer, claims, sources, proposed fact update |
| `POST /profile/{id}/confirm-update` | Proposed update ID | New profile version, triggers re-assessment |
| `POST /draft-email` | Requirement ID + profile ID | Draft subject and body |

### 8.3 Example assessment response (share with designer)

```json
{
  "assessment_id": "a-102",
  "profile_version": 3,
  "score": 67,
  "area_scores": {"registration": 50, "tax": 100, "employer": null},
  "now": [
    {"requirement_id": "REG-01", "title": "Register your business name", "status": "not_done",
     "priority": "high", "explanation": "You trade as Wick & Co, which is not your legal name...",
     "action_url": "https://...", "sources": [{"title": "...", "url": "https://..."}]}
  ],
  "next": [
    {"requirement_id": "TAX-01", "title": "Register for BC PST", "status": "not_yet_required",
     "progress": {"current": 8200, "threshold": 10000, "estimated_crossing": "2027-03"}}
  ],
  "later": [
    {"requirement_id": "EMP-01", "title": "Register with WorkSafeBC", "trigger": "first_hire"}
  ],
  "flags": [{"requirement_id": "TAX-01", "reason": "Regular market sales may affect the premises condition"}],
  "disclaimer": "General information, not legal advice."
}
```

Example values are illustrative only. Store a full set of examples in `contracts/examples/`.

## 9. Task breakdown by owner

The critical path is registry content, then retrieval, then agents, then the dashboard; the research owner and both developers start in parallel in hour one.

### 9.1 Roles

| Role | Owns |
| --- | --- |
| PM | Task assignment, rules check, demo script, pitch, .tech domain, UNSDG framing |
| Research owner (business) | Sources, requirement registry content, fact dictionary, threshold rules, gray areas, test questions |
| Developer 1: knowledge and assessment engine | TiDB, ingestion, chunking, embeddings, retrieval, registry loader, applicability rules, calculators, scoring, sequencing |
| Developer 2: agents and application | Intake, orchestrator, three agents and tools, validation, chat, actions, profile versioning, API routes, trace logging |
| Designer | Figma screens, front end build, deployment of front end |

### 9.2 Phases

1. **Phase 0, setup (first 2 hours):** TiDB cluster in a supported region, Gemini key and quota check, repo skeleton, shared contracts, first source end to end.
2. **Phase 1, foundations (rest of day 1):** registry draft, ingestion, retrieval, calculators, intake, base agent class, Figma screens.
3. **Phase 2, agents and engine (day 2 morning):** three agents, orchestrator, scoring, sequencing, API routes, front end wired to example JSON.
4. **Phase 3, integration and demo (day 2 afternoon):** end-to-end Maya flow, chat and fact update loop, polish, deploy, rehearse.

### 9.3 Task list

| ID | Task | Owner | Phase | Depends on |
| --- | --- | --- | --- | --- |
| PM-01 | Confirm StormHacks rules: track limits, pre-event design and research | PM | 0 | none |
| PM-02 | Register .tech domain, set up DNS | PM | 0 | none |
| PM-03 | Write demo script around Maya (section 3.2) | PM | 2 | RES-03 |
| PM-04 | Pitch deck: problem, comparison table, workflow, UNSDG framing, "same answers, same score" line | PM | 3 | none |
| PM-05 | Run acceptance test checklist before demo | PM | 3 | all |
| RES-01 | Finalise approved source list (section 6.2) with URLs | Research | 0 | none |
| RES-02 | Confirm exact PST small seller and GST small supplier conditions from official pages | Research | 1 | RES-01 |
| RES-03 | Write and validate 15 to 18 registry rows in the shared sheet | Research | 1 | RES-01 |
| RES-04 | Resolve flagged items: Vancouver licence for home-based and online-only, licence fee, payroll record retention, market stalls | Research | 1 | RES-01 |
| RES-05 | Write 15 to 25 test questions, incl. at least 3 with no official answer | Research | 1 | RES-01 |
| RES-06 | Write Maya's full demo profile and 12 months of revenue | Research | 1 | none |
| D1-01 | Create TiDB cluster in a full-text-supported region; verify vector and full-text search | Dev 1 | 0 | none |
| D1-02 | Create tables (section 4.2) and shared Pydantic contracts with Dev 2 | Dev 1 | 0 | D1-01 |
| D1-03 | Ingest first source end to end (fetch, chunk, embed, store, retrieve) | Dev 1 | 0 | D1-02 |
| D1-04 | Ingest all approved sources with full metadata | Dev 1 | 1 | RES-01, D1-03 |
| D1-05 | Retrieval service per contract (filters, vector or hybrid search, insufficient\_evidence) | Dev 1 | 1 | D1-03 |
| D1-06 | Registry loader script (sheet to TiDB) | Dev 1 | 1 | D1-02 |
| D1-07 | Applicability engine: `applies_if` rules, statuses, missing facts | Dev 1 | 1 | D1-06 |
| D1-08 | Calculators: PST small seller test, GST small supplier test, projected crossing | Dev 1 | 1 | RES-02 |
| D1-09 | Scoring (section 2.5) and sequencing by `depends_on` | Dev 1 | 2 | D1-07 |
| D1-10 | Retrieval evaluation against test questions | Dev 1 | 2 | RES-05, D1-05 |
| D2-01 | FastAPI skeleton, settings, Gemini client, rate limit check | Dev 2 | 0 | none |
| D2-02 | Profile service with versioning and `{value, confirmed}` facts | Dev 2 | 1 | D1-02 |
| D2-03 | Intake: free text to proposed facts (structured output) | Dev 2 | 1 | D2-01 |
| D2-04 | Follow-up question wording from missing facts | Dev 2 | 1 | D1-07 |
| D2-05 | Base agent class: tools, two-phase loop, step limit, trace logging to `agent_runs` | Dev 2 | 1 | D1-05 |
| D2-06 | Registration, Tax and Employer agents (prompts, scopes, tools, gray areas) | Dev 2 | 2 | D2-05, RES-03 |
| D2-07 | Orchestrator: agent selection, parallel runs, merge | Dev 2 | 2 | D2-06 |
| D2-08 | Citation validation | Dev 2 | 2 | D2-06 |
| D2-09 | API routes (section 8.2) and example JSON in `contracts/examples/` | Dev 2 | 2 | D1-09, D2-07 |
| D2-10 | Chat with agent routing, insufficient-evidence answers, fact update proposals | Dev 2 | 3 | D2-07 |
| D2-11 | Inquiry email drafts | Dev 2 | 3 | D2-09 |
| D2-12 | Cache Maya's assessment as demo fallback | Dev 2 | 3 | D2-09 |
| DES-01 | Figma: intake, confirm facts, dashboard (now/next/later), card "Why?", trace, chat | Designer | 1 | none |
| DES-02 | Build front end against example JSON | Designer | 2 | DES-01, D2-09 |
| DES-03 | Wire to live API, deploy to Vercel, connect domain | Designer | 3 | DES-02, PM-02 |

### 9.4 First joint session (30 minutes, before splitting up)

1. Pick one official source and one answerable question (for example: "Do I need to register Wick & Co?").
2. Extract three to five chunks and add metadata together.
3. Manually mark which chunk supports the answer.
4. Dev 1 walks through embed, store, filter, retrieve.
5. Dev 2 walks through agent tools, Gemini prompt, citation validation.
6. Test one unsupported question and agree on the insufficient-evidence wording.

Done when everyone can tell apart: poor retrieval, correct retrieval but unsupported answer, grounded answer, missing facts, wrong jurisdiction, outdated source.

## 10. Acceptance tests, non-goals, risks and open decisions

The MVP is done when the Maya flow runs end to end and every test below passes; anything not listed here is out of scope.

### 10.1 Acceptance tests

**Business logic**

- [ ] Owner trading under their own legal name gets no name registration requirement; "Wick & Co" does.
- [ ] $8,200 rolling 12-month sales with no premises: PST shows as not yet required, with a projected crossing month.
- [ ] Crossing $10,000 in a rolling 12 months moves PST registration to Now, even mid-year.
- [ ] A services-only owner does not get PST registration as required (outside the specified professional services).
- [ ] Missing revenue makes tax requirements undetermined, never "fine".
- [ ] Confirming a first hire moves all employer obligations from Later to Now and changes the score.
- [ ] Recommendations and upcoming items never change the score.
- [ ] Same profile always produces the same score.
- [ ] Next actions respect dependencies (business number before GST or payroll account).

**Retrieval**

- [ ] A Vancouver question returns Vancouver, BC or federal evidence, never another city's.
- [ ] Requirement filters restrict results correctly.
- [ ] Unsupported questions return `insufficient_evidence`.
- [ ] Every chunk has source metadata and a working URL.

**Agents and chat**

- [ ] Every compliance claim cites a chunk retrieved in that run.
- [ ] No invented fees, deadlines, forms or links.
- [ ] Gray areas appear as flags, not conclusions.
- [ ] Agent trace shows each tool call.
- [ ] A fact mentioned in chat becomes a proposed update, applied only after confirmation.

### 10.2 Non-goals for the MVP

- Incorporated businesses, partnerships, other cities or provinces.
- Food service, liquor, building permits, signage or other industry permits.
- Automated filings or sending emails automatically.
- Legal certification or advice.
- Continuous monitoring of law changes.
- Open web research during chat.
- Multi-agent debate (agents never argue; they each own their area and code merges results).
- A second vector store.

### 10.3 Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| TiDB full-text unavailable in our region | Use vector search only; still qualifies for the TiDB track |
| `pytidb` embedding wiring fails | Call Gemini embeddings directly and insert vectors via SQLAlchemy |
| Gemini rate limits during demo | Paid credits; cached Maya assessment |
| Registry not finished in time | Cut to 10 requirements (3 to 4 per area), keep the hiring moment |
| Legal facts wrong in front of judges | Research owner verifies every threshold and link; "general information, not legal advice" disclaimer visible |
| Dead action links | Link checker script run the night before |

### 10.4 Open decisions for the team

- [ ] Exact source list and URLs (RES-01).
- [ ] Exact PST and GST test wording (RES-02).
- [ ] Vancouver licence treatment for home-based and online-only businesses (RES-04).
- [ ] Whether to use Google's Agent Development Kit or hand-rolled agent classes (default: hand-rolled, simpler to debug).
- [ ] Which StormHacks tracks we formally submit to (PM-01).
