"use client";

// A compact, inspectable record of the tools the agents used for this assessment.
// The backend stores these entries in TiDB; the UI intentionally renders summaries rather than
// raw prompts or model output.

import type { AgentTraceEntry } from "@/lib/api";

const AGENT_LABEL: Record<string, string> = {
  orchestrator: "Orchestrator",
  registration: "Registration agent",
  tax: "Tax agent",
  employer: "Employer agent",
};

const TOOL_LABEL: Record<string, string> = {
  plan: "Planned the check",
  retrieve_evidence: "Read official evidence",
  retrieve_evidence_many: "Read official evidence",
  get_requirement: "Read a requirement",
  get_profile_fact: "Checked a business fact",
  get_calculator_result: "Ran a calculator",
  flag_for_review: "Flagged an item for review",
  validate_citations: "Validated citations",
};

function summaryContext(entry: AgentTraceEntry): string | null {
  const requirement = entry.tool_input.requirement_id;
  const calculator = entry.tool_input.name;
  if (typeof requirement === "string") return requirement;
  if (typeof calculator === "string") return calculator.replace(/_/g, " ");
  return null;
}

function time(iso: string): string | null {
  const date = new Date(iso);
  return Number.isNaN(date.valueOf())
    ? null
    : date.toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit" });
}

export function AgentTrace({ trace }: { trace: AgentTraceEntry[] }) {
  return (
    <section id="agent-trace" aria-labelledby="trace-h" className="box scroll-mt-6 overflow-hidden">
      <div className="flex flex-wrap items-baseline justify-between gap-2 bg-panel px-5 py-4">
        <div>
          <h2 id="trace-h" className="m-0 text-base font-medium">
            Agent trace
          </h2>
          <p className="muted mt-1 mb-0 text-[13px]">What the agents checked for this assessment.</p>
        </div>
        <span className="muted text-sm">{trace.length} {trace.length === 1 ? "step" : "steps"} saved</span>
      </div>

      {trace.length === 0 ? (
        <p className="muted m-0 p-5 text-sm">
          No saved agent steps were returned for this assessment. Source citations are still shown on each requirement.
        </p>
      ) : (
        <ol className="m-0 list-none divide-y divide-line-soft p-0">
          {trace.map((entry, index) => {
            const context = summaryContext(entry);
            const label = TOOL_LABEL[entry.tool_name] ?? entry.tool_name.replace(/_/g, " ");
            const createdAt = time(entry.created_at);
            return (
              <li key={`${entry.agent}-${entry.step}-${index}`} className="flex flex-col gap-1.5 px-5 py-4 text-sm">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="font-medium">{AGENT_LABEL[entry.agent] ?? entry.agent}</span>
                  <span className="muted">{label}{context ? ` · ${context}` : ""}</span>
                  {createdAt && (
                    <time className="muted ml-auto text-[13px]" dateTime={entry.created_at}>
                      {createdAt}
                    </time>
                  )}
                </div>
                <p className="m-0">{entry.tool_output_summary}</p>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
