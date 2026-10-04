"use client";

// Wireframe 03, Assessment dashboard.

import Link from "next/link";
import { useState } from "react";
import { LogoMark } from "@/components/ui";
import type { Area } from "@/lib/api";
import {
  AREAS,
  type Kind,
  type Row,
  appliesPill,
  confirmedFactCount,
  detailLine,
  kindOf,
  nextStep,
  priorityPill,
  progressOf,
  shortDate,
  statusText,
  summarize,
} from "@/lib/assessment";
import { useBusiness } from "./BusinessProvider";
import { AgentTrace } from "./AgentTrace";
import { FactQuestion } from "./FactQuestion";
import { PersonaAvatar } from "./icons";
import { PersonaCards } from "./PersonaCards";

type Filter = "all" | "action" | "input" | "done";

export function Dashboard() {
  const { businessId, profile, assessment, rows, marks, questions, rechecking, trace } = useBusiness();
  const [filter, setFilter] = useState<Filter>("all");
  if (!assessment || !profile) return null;

  const s = summarize(rows, marks);
  const next = nextStep(rows, marks);
  const name = profile.trading_name || profile.legal_name || "Your business";
  const failedAgents = assessment.agents.filter((a) => a.error).length;
  const base = `/b/${businessId}`;
  const filters: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "action", label: `Needs action (${s.action})` },
    { id: "input", label: `Needs input (${s.input})` },
    { id: "done", label: `Done (${s.done})` },
  ];

  return (
    <main className="inner flex w-full max-w-none flex-col gap-9">
      <div>
        <p className="pre">
          {name}, checked {shortDate(assessment.cached_at ?? new Date().toISOString())} with{" "}
          {confirmedFactCount(profile)} confirmed facts
        </p>
        <h1 className="hero">The results:</h1>
        <p className="mt-5 mb-0 max-w-[720px] text-[17px]">
          These are the requirements that may apply to your business based on what you told us, each backed by an
          official source.{" "}
          <a href="#input" className="text-ink underline-offset-[3px]">
            Update your facts
          </a>{" "}
          any time and we&apos;ll re-check.
        </p>
      </div>

      {(rechecking || failedAgents > 0 || assessment.cached) && (
        <div className="box flex items-center gap-2.5 bg-panel px-5 py-3 text-sm" role="status">
          {rechecking ? (
            <>
              <span className="spin" /> Re-checking with your new answers…
            </>
          ) : assessment.cached ? (
            <span>
              Showing your last full results from {shortDate(assessment.cached_at)} because a live check didn&apos;t
              finish. Same facts, same results.
            </span>
          ) : (
            <span>
              Explanations couldn&apos;t be checked against official sources this time ({failedAgents} of{" "}
              {assessment.agents.length} agents unavailable). What applies to you was still decided by our rules.
            </span>
          )}
        </div>
      )}

      <section aria-label="Summary" className="flex flex-wrap gap-4">
        <div className="box tile flex-[2_1_300px]">
          <span className="muted text-sm">Progress</span>
          <span className="num">
            {s.done} of {s.applicableNow} done
          </span>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={s.applicableNow}
            aria-valuenow={s.done}
            aria-label="Requirements done"
            className="mt-1.5 mb-1 h-1.5 overflow-hidden rounded-[3px] bg-line-soft"
          >
            <div className="h-full bg-brand" style={{ width: `${s.applicableNow ? (100 * s.done) / s.applicableNow : 0}%` }} />
          </div>
          <span className="muted text-[13px]">
            Of requirements that apply now.
            {s.input > 0 && ` ${s.input} more wait on your answers.`}
          </span>
        </div>
        <a className="box tile" href="#all" onClick={() => setFilter("action")}>
          <span className="muted text-sm">Needs action</span>
          <span className="num">{s.action}</span>
          <span className="text-[13px] underline underline-offset-[3px]">{s.doFirst} marked Do first</span>
        </a>
        <a className="box tile" href="#input">
          <span className="muted text-sm">Needs your input</span>
          <span className="num">{questions.length}</span>
          <span className="text-[13px] underline underline-offset-[3px]">
            {questions.length ? "Answer to finish" : "All answered"}
          </span>
        </a>
        <a className="box tile" href="#all" onClick={() => setFilter("all")}>
          <span className="muted text-sm">Coming up</span>
          <span className="num">{s.upcoming}</span>
          <span className="text-[13px] underline underline-offset-[3px]">See what switches on</span>
        </a>
      </section>

      {next ? (
        <section
          aria-labelledby="next-h"
          className="box callout flex flex-wrap items-center gap-5 p-7"
        >
          <div className="flex min-w-0 flex-[999_1_440px] flex-col gap-2.5">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="text-sm font-medium text-brand">Do this next</span>
              {next.priority === "high" && <span className="pill pill-fill">Do first</span>}
            </div>
            <h2 id="next-h" className="m-0 text-[28px] leading-[1.2] font-medium tracking-[-0.025em]">
              {next.title}
            </h2>
            {next.explanation && <p className="m-0 max-w-[820px]">{next.explanation}</p>}
            {next.sources[0] && (
              <p className="muted m-0 text-sm">Source: {next.sources.map((src) => src.title).join("; ")}</p>
            )}
          </div>
          <div className="flex flex-[1_1_220px] flex-wrap justify-end gap-2.5">
            <Link href={`${base}/r/${next.requirement_id}`} className="btn btn-p">
              {progressOf(next, marks) === "in_progress" ? "Continue this step" : "Start this step"}
            </Link>
          </div>
        </section>
      ) : (
        s.applicableNow > 0 && (
          <section className="box callout flex flex-col gap-1.5 p-7">
            <span className="text-sm font-medium text-brand">Do this next</span>
            <h2 className="m-0 text-[28px] leading-[1.2] font-medium tracking-[-0.025em]">
              You&apos;ve done everything that applies today.
            </h2>
            <p className="m-0">Keep an eye on what&apos;s coming up below.</p>
          </section>
        )
      )}

      <section id="input" aria-labelledby="input-h" className="flex scroll-mt-6 flex-col gap-3.5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="input-h" className="sec">
            Needs your input <span className="muted font-normal">({questions.length})</span>
          </h2>
          <span className="muted text-sm">Each answer finishes checking a requirement</span>
        </div>
        {questions.length ? (
          <div className="box overflow-hidden">
            {questions.map((q) => (
              <FactQuestion key={q.fact_key} question={q} variant="row" />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1.5 rounded-[2px] border border-dashed border-step-off bg-panel p-6 text-center">
            <LogoMark size={22} />
            <span className="font-medium">No open questions</span>
            <span className="muted text-[13px]">Every requirement in this check has the facts it needs.</span>
          </div>
        )}
      </section>

      <PersonaCards />

      <section id="all" aria-labelledby="all-h" className="flex scroll-mt-6 flex-col gap-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="all-h" className="sec">
              All {rows.length} requirements
            </h2>
            <p className="muted mt-1 mb-0 text-sm">
              Open any requirement for its steps and the official sources behind it.
            </p>
          </div>
          <div role="group" aria-label="Filter" className="flex flex-wrap gap-1.5">
            {filters.map((f) => (
              <button
                key={f.id}
                type="button"
                aria-pressed={filter === f.id}
                className={`btn btn-s ${filter === f.id ? "btn-on" : "btn-soft"}`}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {AREAS.map((area) => (
          <AreaGroup
            key={area.id}
            id={`area-${area.id}`}
            area={area.id}
            label={area.label}
            rows={rows.filter((r) => r.area === area.id)}
            filter={filter}
          />
        ))}
      </section>

      <AgentTrace trace={trace} />

      <section
        id="coverage"
        aria-labelledby="cov-h"
        className="box flex scroll-mt-6 flex-wrap gap-x-10 gap-y-3 border-line bg-side p-6"
      >
        <div className="flex-[1_1_260px]">
          <h2 id="cov-h" className="m-0 text-base font-medium">
            What this check covers
          </h2>
          <p className="mt-1.5 mb-0 text-sm">
            {rows.length} requirements for sole proprietors in the City of Vancouver, covering registration and
            licensing, tax registration, and employer obligations.
          </p>
        </div>
        <div className="flex-[2_1_380px]">
          <div className="text-base font-medium">Not covered</div>
          <p className="mt-1.5 mb-0 text-sm">
            Food safety and liquor licensing, zoning and building permits, signage, industry-specific permits,
            incorporated businesses and partnerships, and anything outside Vancouver. {assessment.disclaimer}
          </p>
        </div>
      </section>
    </main>
  );
}

const MATCHES: Record<Filter, (k: Kind) => boolean> = {
  all: () => true,
  action: (k) => k === "action",
  input: (k) => k === "input",
  done: (k) => k === "done",
};

function AreaGroup({
  id,
  area,
  label,
  rows,
  filter,
}: {
  id: string;
  area: Area;
  label: string;
  rows: Row[];
  filter: Filter;
}) {
  const { businessId, marks, assessment } = useBusiness();
  const persona = assessment?.agents.find((a) => a.agent === area)?.persona ?? null;
  const kinds = new Map(rows.map((r) => [r.requirement_id, kindOf(r, marks)]));
  const shown = rows.filter((r) => MATCHES[filter](kinds.get(r.requirement_id)!));
  if (!shown.length) return null;

  // Like the wireframe's "don't apply" fold: rows that only switch on later are collapsed.
  const open = shown.filter((r) => r.bucket !== "later" || kinds.get(r.requirement_id) !== "upcoming");
  const folded = shown.filter((r) => !open.includes(r));
  const applicable = rows.filter((r) => r.bucket === "now").length;
  const count = (k: Kind) => rows.filter((r) => kinds.get(r.requirement_id) === k).length;

  const summary = [
    applicable ? `${count("done")} of ${applicable} done` : null,
    count("input") ? `${count("input")} need input` : null,
    count("upcoming") ? `${count("upcoming")} coming up` : null,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <details id={id} open className="fold box scroll-mt-6 overflow-hidden">
      <summary className="flex flex-wrap items-center justify-between gap-2 bg-panel px-5 py-3.5">
        <h3 className="m-0 flex items-center gap-2 text-base font-medium">
          {label}
          {persona && (
            <span className="muted inline-flex items-center gap-1 text-[13px] font-normal">
              <PersonaAvatar avatar={persona.avatar} size={20} />
              {persona.display_name}
            </span>
          )}
        </h3>
        <span className="muted flex items-center gap-3 text-sm">
          {summary}
          <svg className="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </span>
      </summary>
      {open.length > 0 && (
        <>
          <div className="colh" aria-hidden="true">
            <span className="flex-[0_0_16px]" />
            <span className="c-name">Requirement</span>
            <span className="c-app">Applies to you</span>
            <span className="c-pri">Priority</span>
            <span className="c-st">Status</span>
            <span className="c-src">Official source</span>
          </div>
          {open.map((r) => (
            <RequirementRow key={r.requirement_id} row={r} kind={kinds.get(r.requirement_id)!} base={`/b/${businessId}`} />
          ))}
        </>
      )}
      {folded.length > 0 && (
        <details className="border-t border-line-soft">
          <summary className="muted cursor-pointer px-5 py-3 text-sm">
            Show {folded.length} that {folded.length === 1 ? "switches" : "switch"} on later
            {folded.every((r) => r.trigger === "first_hire") ? " when you hire" : ""}
          </summary>
          {folded.map((r) => (
            <RequirementRow key={r.requirement_id} row={r} kind={kinds.get(r.requirement_id)!} base={`/b/${businessId}`} />
          ))}
        </details>
      )}
    </details>
  );
}

function RequirementRow({ row, kind, base }: { row: Row; kind: Kind; base: string }) {
  const { marks } = useBusiness();
  const applies = appliesPill(row, kind);
  const priority = priorityPill(row, kind);
  const progress = progressOf(row, marks);
  // The trigger line repeats what the explanation already says; the sales progress line does not.
  const detail = row.progress || !row.explanation ? detailLine(row) : undefined;
  // The same page can be cited more than once; list each source a single time.
  const sources = [...new Map(row.sources.map((s) => [s.url || s.title, s])).values()];
  const dot =
    kind === "done" ? "dot dot-done" : kind === "input" ? "dot dot-dash" : progress === "in_progress" ? "dot dot-half" : "dot";

  return (
    <Link className="req" href={`${base}/r/${row.requirement_id}`}>
      <span className={dot} aria-hidden="true" />
      <span className="c-name">
        <span className="block font-medium">{row.title}</span>
        {detail && <span className="muted block text-[13px]">{detail}</span>}
        {row.explanation && (
          <span className="mt-0.5 line-clamp-2 block max-w-[720px] text-[13px] leading-[1.45] text-ink/80">
            {row.explanation}
          </span>
        )}
        {row.progress && (
          <span className="mt-1.5 block h-1 max-w-[240px] overflow-hidden rounded-sm bg-line-soft" aria-hidden="true">
            <span
              className="block h-full bg-brand"
              style={{ width: `${Math.min(100, (100 * row.progress.current) / row.progress.threshold)}%` }}
            />
          </span>
        )}
      </span>
      <span className="c-app">
        <span className={applies.className}>{applies.label}</span>
      </span>
      <span className="c-pri">{priority && <span className={priority.className}>{priority.label}</span>}</span>
      <span className="c-st">
        {kind === "done" ? (
          <span className="font-medium text-brand">Done</span>
        ) : (
          <span className="muted">{statusText(row, kind, marks)}</span>
        )}
      </span>
      <span className="c-src">
        {sources.length ? (
          <span className="line-clamp-2">{sources.map((s) => s.title).join("; ")}</span>
        ) : (
          "—"
        )}
      </span>
    </Link>
  );
}
