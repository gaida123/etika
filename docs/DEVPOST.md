# Etika — Compliance, Decoded.

A friend spent a whole weekend trying to figure out if her candle business needed to register for PST. Four government sites, a Reddit thread, and a phone call later — the answer was "not yet, but close." Compliance info isn't missing, it's fragmented: BizPaL lists permits that *may* apply, Ownr just registers a name, an accountant only knows what you tell them. Nobody says what applies to *you*, why, and what to do next — and the thresholds move underneath you the whole time.

So we built Etika.

## What it does

Etika is a compliance navigator for new Vancouver sole proprietors. You answer a few questions, three specialist AI agents (Registration, Tax, Employer) check your situation against official government sources, and you get a readiness score, cited explanations, and a Now/Next/Later action plan — each item with a direct link to the real form.

Mention a change in chat — "I'm hiring next month" — and the system proposes a fact update. Confirm it, and the assessment re-runs live: five employer obligations flip from Later to Now, score and all.

## How we built it

- **Backend:** Python 3.11, FastAPI, Pydantic v2
- **Database:** TiDB Cloud (vector + relational, one store)
- **AI:** Gemini Flash for intake parsing, agent explanations, and chat; `gemini-embedding-001` for retrieval
- **Frontend:** Next.js, TypeScript, Tailwind

The core rule: **code decides, Gemini explains.** Applicability, scoring, and thresholds are deterministic Python — rolling-window PST/GST tests, straight-line crossing projections, dependency-ordered sequencing. Gemini only ever writes the human-facing explanation of evidence that code already retrieved and already validated. Citations are checked after every agent call and anything not actually retrieved gets dropped.

## Challenges

The law was harder than the code — PST's exemption depends on a *rolling* 12-month window, not a calendar year, so one good month can flip your status. We also had to build our own knowledge base from scratch: collecting official BC Registries, CRA, WorkSafeBC and City of Vancouver pages by hand, chunking them by legal section, and gating every chunk behind a reviewed/approved status before it was ever allowed to be cited, so nothing unverified could reach an agent. The hardest part wasn't collecting the data — it was narrowing the agents' focus enough that they could only answer from that evidence and nothing else, so Gemini never filled a gap with something that sounded right but wasn't sourced. On top of that, three parallel agents blew through Gemini's rate limit fast, which pushed us to rebuild the pipeline so code prefetches all evidence and each agent makes exactly one call — cutting Gemini usage from 8–15 requests per assessment down to 3.

## What we're proud of

The RAG pipeline is what we're most proud of — we built the entire source-to-citation process ourselves: scraping and reviewing official government sources, chunking and embedding them, and gating retrieval so an agent can only cite evidence it actually pulled in that run. Combined with the fact that status comes from code, not the model, it means you can't talk it into a wrong answer — the same facts always produce the same score. And the hiring moment — typing one sentence in chat and watching five legal obligations switch on live — is the best 10 seconds of the demo.

## What's next

Pre-filled government forms generated straight from the saved profile, auto-generated policy documents (privacy, refund, workplace), a renewal/deadline calendar, and expansion beyond Vancouver sole proprietors to other BC cities and business structures.
