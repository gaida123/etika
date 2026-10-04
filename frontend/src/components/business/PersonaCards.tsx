"use client";

// Phase 7: one card per specialist. The handle and the line it says are presentation only; what
// applies to the owner, its status and its sources are decided in code and shown unchanged below.
// "Plain" hides the voiced lines, for anyone who just wants the facts.

import { useState } from "react";
import type { AgentRun } from "@/lib/api";
import { AREAS } from "@/lib/assessment";
import { useBusiness } from "./BusinessProvider";
import { PersonaAvatar } from "./icons";

export function PersonaCards() {
  const { assessment, rows } = useBusiness();
  const [plain, setPlain] = useState(false);
  if (!assessment) return null;

  const order = new Map(AREAS.map((a, i) => [a.id, i]));
  const agents = assessment.agents
    .filter((a) => a.persona)
    .sort((a, b) => (order.get(a.agent) ?? 9) - (order.get(b.agent) ?? 9));
  if (!agents.length) return null;

  return (
    <section aria-labelledby="who-h" className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="who-h" className="sec">
          Who checked your business
        </h2>
        <div role="group" aria-label="Voice" className="flex items-center gap-2">
          <span className="muted text-[13px]">Voice</span>
          <button type="button" aria-pressed={!plain} className={`btn btn-s ${plain ? "btn-soft" : "btn-on"}`} onClick={() => setPlain(false)}>
            Full
          </button>
          <button type="button" aria-pressed={plain} className={`btn btn-s ${plain ? "btn-on" : "btn-soft"}`} onClick={() => setPlain(true)}>
            Plain
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-4">
        {agents.map((agent) => (
          <PersonaCard
            key={agent.agent}
            agent={agent}
            checked={rows.filter((r) => r.area === agent.agent).length}
            plain={plain}
          />
        ))}
      </div>

      <p className="muted m-0 max-w-[820px] text-[13px]">
        Each specialist has a name and a manner, nothing more: their wording never changes what
        applies to you, your status or the sources shown. {assessment.disclaimer} Confirm with the
        issuing office or a professional.
      </p>
    </section>
  );
}

function PersonaCard({ agent, checked, plain }: { agent: AgentRun; checked: number; plain: boolean }) {
  const persona = agent.persona!;
  const label = AREAS.find((a) => a.id === agent.agent)?.label ?? persona.role_title;

  return (
    <article className="box flex min-w-0 flex-[1_1_280px] flex-col gap-3 p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-12 shrink-0 items-center justify-center overflow-hidden rounded-full bg-brand-tint">
          <PersonaAvatar avatar={persona.avatar} size={46} />
        </span>
        <div className="min-w-0">
          <div className="leading-[1.25] font-medium">{persona.display_name}</div>
          <div className="muted text-[13px] leading-[1.35]">{persona.role_title}</div>
        </div>
      </div>

      <p className="muted m-0 text-[13px] leading-[1.45]">{persona.specialty}.</p>

      {!plain && agent.summary && (
        <p className="m-0 rounded-[2px] border-l-2 border-brand bg-brand-tint px-3.5 py-2.5 text-[14px] leading-[1.5]">
          {agent.summary}
        </p>
      )}

      {agent.error && (
        <p className="m-0 text-[13px] leading-[1.45]">
          Couldn&apos;t reach official sources this time. What applies to you was still decided by our rules.
        </p>
      )}

      <div className="muted mt-auto flex flex-col items-start gap-1.5 border-t border-line-soft pt-2.5 text-[13px]">
        <span>
          {checked} {checked === 1 ? "requirement" : "requirements"} in {label.toLowerCase()}
        </span>
        {/* Always takes the line, hidden when empty, so every card's footer is the same height. */}
        <span
          className={`pill pill-mute h-[20px] text-xs font-normal ${agent.cached_findings > 0 ? "" : "invisible"}`}
          aria-hidden={agent.cached_findings > 0 ? undefined : true}
        >
          {agent.cached_findings} unchanged since your last check
        </span>
      </div>
    </article>
  );
}
