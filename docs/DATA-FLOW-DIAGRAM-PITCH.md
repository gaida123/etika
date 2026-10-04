# Etika data & decision flow — pitch notes

The diagram is the architecture behind Etika’s trust promise: **we use AI to understand and explain; deterministic code decides what applies.**

## How the pieces fit together

1. **The owner starts in the Next.js app.** They complete a short intake, can add a plain-English business description, then see a dashboard, ask questions and request an email draft.
2. **The FastAPI trust layer separates suggestions from facts.** Gemini can turn free text into *proposed* facts, but the owner must confirm them. Each confirmation creates an immutable new version of that business profile; a missing answer stays unknown rather than being assumed false.
3. **The deterministic engine makes the legal-state decision.** It evaluates the confirmed profile against the reviewed requirements registry, runs tax-threshold calculators, resolves prerequisites, and computes the readiness score. This makes two identical profiles produce the same outcome.
4. **The orchestrator assigns the work to three scoped specialists.** The Registrar covers registration and licensing, the Counter covers PST/GST, and the Foreman covers hiring and payroll. They do not decide whether a rule applies; they explain the engine’s result.
5. **TiDB Cloud is the system of record and evidence layer.** It stores business state, proposed updates, reviewed requirements, official-source chunks and embeddings, agent findings, traces, conversations and safe reuse caches. Retrieval is filtered by jurisdiction, area, review status and requirement before it reaches an agent.
6. **Gemini has bounded jobs.** It extracts structured intake proposals, writes plain-language explanations and grounded chat answers, and creates query embeddings for semantic retrieval. Its factual claims must cite chunks retrieved in that run; unsupported claims are dropped.
7. **The dashboard turns the output into an action plan.** The owner receives a readiness score, prioritized Now / Next / Later items, official links from the registry, source passages, and an inspectable agent trace. Actions are owner-controlled: Etika drafts but never sends an email or submits a form.

## 45-second talk track

“Etika starts with a few confirmed facts about a Vancouver sole proprietor. We save those facts as versioned business profiles, so when the business changes — for example, when they hire someone — we can re-run the assessment against the exact new situation. Our deterministic rules engine, not the LLM, decides which registrations, tax accounts and employer obligations apply, calculates thresholds, and produces the readiness score. Then three focused AI specialists retrieve only approved official evidence from TiDB and turn that result into clear, cited explanations. TiDB is both our evidence layer and our audit trail: it holds the source chunks, requirements, findings and agent traces. The owner ends with a sequenced Now, Next and Later plan they can inspect and act on themselves.”

## The answer to “isn’t this just ChatGPT?”

“No. ChatGPT can generate an answer, but Etika has a versioned profile, a reviewed requirements registry, deterministic applicability and scoring, calculators for legal thresholds, filtered official-source retrieval, citation validation and an audit trail. AI explains the result; it does not make the compliance decision.”

## Useful callouts during a demo

- **Trust:** An unanswered question stays unknown; Etika asks a follow-up rather than quietly treating it as ‘no.’
- **Personalization:** Confirming a fact update creates a new profile version and re-runs the whole assessment.
- **Evidence:** Every explanation is constrained to official chunks retrieved for that specific run.
- **Actionability:** The score only reflects what is required now. Future triggers are visible, but do not unfairly lower it.
- **Control:** Email drafts and official links help the owner act; Etika never acts on their behalf.
