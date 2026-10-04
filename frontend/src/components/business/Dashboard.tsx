"use client";

// Wireframe 03, Assessment dashboard.

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { LogoMark } from "@/components/ui";
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

type Filter = "all" | "action" | "input" | "done";

// The results read as a short walk-through instead of one long page: each step answers one
// question, and Back/Next (or the step bar) moves between them. Finishing it opens the full
// dashboard, which has everything on one page. The view lives in ?step= so the sidebar,
// requirement pages and the browser's back button can all land on the right one.
export const STEPS = [
  { id: "overview", label: "Overview" },
  { id: "next", label: "Do this first" },
  { id: "input", label: "Your questions" },
  { id: "all", label: "All requirements" },
  { id: "coverage", label: "What we cover" },
] as const;
export type StepId = (typeof STEPS)[number]["id"] | "dashboard";

export const stepHref = (base: string, step: StepId) => (step === "overview" ? base : `${base}?step=${step}`);

export function useStep(): StepId {
  const param = useSearchParams().get("step");
  if (param === "dashboard") return "dashboard";
  return STEPS.find((s) => s.id === param)?.id ?? "overview";
}

export function Dashboard() {
  const { businessId, profile, assessment } = useBusiness();
  const step = useStep();
  if (!assessment || !profile) return null;

  const base = `/b/${businessId}`;
  if (step === "dashboard") return <FullDashboard base={base} />;

  const index = STEPS.findIndex((s) => s.id === step);
  const prev = STEPS[index - 1];
  const next = STEPS[index + 1];

  return (
    <main className="inner flex w-full max-w-none flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StepBar base={base} current={index} />
        <Link href={stepHref(base, "dashboard")} className="muted text-sm underline-offset-[3px]">
          Skip to dashboard
        </Link>
      </div>

      {step === "overview" && <OverviewStep base={base} />}
      {step === "next" && <NextStep base={base} />}
      {step === "input" && <InputStep />}
      {step === "all" && <AllStep />}
      {step === "coverage" && <CoverageStep />}

      <nav aria-label="Step navigation" className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-6">
        {prev ? (
          <Link href={stepHref(base, prev.id)} className="btn btn-soft">
            <Chevron dir="left" />
            Back
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={stepHref(base, next.id)} className="btn btn-p">
            Next: {next.label}
            <Chevron dir="right" />
          </Link>
        ) : (
          <Link href={stepHref(base, "dashboard")} className="btn btn-p">
            Finish and see my dashboard
            <Chevron dir="right" />
          </Link>
        )}
      </nav>
    </main>
  );
}

function Chevron({ dir }: { dir: "left" | "right" }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d={dir === "left" ? "m15 6-6 6 6 6" : "m9 6 6 6-6 6"} />
    </svg>
  );
}

function StepBar({ base, current }: { base: string; current: number }) {
  return (
    <nav aria-label="Results steps">
      <ol className="m-0 flex list-none flex-wrap gap-x-1 gap-y-2 p-0">
        {STEPS.map((s, i) => {
          const on = i === current;
          const past = i < current;
          return (
            <li key={s.id} className="flex items-center gap-1">
              <Link
                href={stepHref(base, s.id)}
                aria-current={on ? "step" : undefined}
                className={`inline-flex min-h-9 items-center gap-2 rounded-full px-3 text-sm no-underline transition-colors ${
                  on ? "bg-brand font-medium text-white hover:text-white" : "text-ink hover:bg-side hover:text-ink"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`inline-flex size-5 items-center justify-center rounded-full text-xs ${
                    on ? "bg-white text-brand" : past ? "bg-brand text-white" : "border border-step-off text-muted"
                  }`}
                >
                  {past ? <Tick size={11} /> : i + 1}
                </span>
                {s.label}
              </Link>
              {i < STEPS.length - 1 && <span aria-hidden="true" className="h-px w-4 bg-line max-[720px]:hidden" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Tick({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
      <path d="M3 8.5 6.5 12 13 4" />
    </svg>
  );
}

function StepHeading({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: React.ReactNode }) {
  return (
    <div>
      {eyebrow && <p className="pre">{eyebrow}</p>}
      <h1 className="m-0 text-[44px] leading-[1.06] font-medium tracking-[-0.035em] max-[720px]:text-[34px]">{title}</h1>
      {children && <p className="mt-4 mb-0 max-w-[680px] text-[17px]">{children}</p>}
    </div>
  );
}

function SectionHeading({ id, title, hint }: { id: string; title: string; hint?: string }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 id={id} className="sec">
        {title}
      </h2>
      {hint && <span className="muted text-sm">{hint}</span>}
    </div>
  );
}

// --- Shared pieces: used by the walk-through steps and by the full dashboard -----------------

function StatusBanner() {
  const { assessment, rechecking } = useBusiness();
  if (!assessment) return null;
  const failedAgents = assessment.agents.filter((a) => a.error).length;
  if (!rechecking && !failedAgents && !assessment.cached) return null;
  return (
    <div className="box flex items-center gap-2.5 bg-panel px-5 py-3 text-sm" role="status">
      {rechecking ? (
        <>
          <span className="spin" /> Re-checking with your new answers…
        </>
      ) : assessment.cached ? (
        <span>
          Showing your last full results from {shortDate(assessment.cached_at)} because a live check didn&apos;t finish.
          Same facts, same results.
        </span>
      ) : (
        <span>
          Explanations couldn&apos;t be checked against official sources this time ({failedAgents} of{" "}
          {assessment.agents.length} areas unavailable). What applies to you was still decided by our rules.
        </span>
      )}
    </div>
  );
}

function SummaryCards({ hrefs }: { hrefs: Record<"action" | "input" | "later", string> }) {
  const { rows, marks, questions } = useBusiness();
  const s = summarize(rows, marks);
  const cards = [
    {
      key: "action" as const,
      label: "To do now",
      value: s.action,
      hint: s.action ? `Start with ${s.doFirst || 1} marked Do first` : "Nothing left for today",
    },
    {
      key: "input" as const,
      label: "Questions for you",
      value: questions.length,
      hint: questions.length ? "Quick answers to finish your check" : "All answered",
    },
    { key: "later" as const, label: "For later", value: s.upcoming, hint: "Apply once something changes, like hiring" },
  ];
  return (
    <section aria-label="Summary" className="flex flex-wrap gap-4">
      {cards.map((c) => (
        <Link key={c.key} href={hrefs[c.key]} className="box tile flex-[1_1_220px]">
          <span className="muted text-sm">{c.label}</span>
          <span className="num">{c.value}</span>
          <span className="text-[13px] underline underline-offset-[3px]">{c.hint}</span>
        </Link>
      ))}
    </section>
  );
}

function ProgressBox() {
  const { rows, marks } = useBusiness();
  const s = summarize(rows, marks);
  return (
    <section aria-label="Progress" className="box flex flex-col gap-2 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-medium">Your progress</span>
        <span className="muted text-sm">
          {s.done} of {s.applicableNow} done
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={s.applicableNow}
        aria-valuenow={s.done}
        aria-label="Requirements done"
        className="h-1.5 overflow-hidden rounded-[3px] bg-line-soft"
      >
        <div
          className="h-full bg-brand transition-[width] duration-500"
          style={{ width: `${s.applicableNow ? (100 * s.done) / s.applicableNow : 0}%` }}
        />
      </div>
      <span className="muted text-[13px]">Counts the requirements that apply to you today.</span>
    </section>
  );
}

function NextCallout({ base }: { base: string }) {
  const { rows, marks } = useBusiness();
  const s = summarize(rows, marks);
  const next = nextStep(rows, marks);
  if (!next)
    return (
      <section className="box callout flex flex-col gap-1.5 p-7">
        <span className="text-sm font-medium text-brand">Do this next</span>
        <h2 className="m-0 text-[28px] leading-[1.2] font-medium tracking-[-0.025em]">
          {s.applicableNow > 0 ? "You've done everything that applies today." : "Nothing to do right now."}
        </h2>
        <p className="m-0">Keep an eye on what could switch on later.</p>
      </section>
    );
  return (
    <section aria-labelledby="next-h" className="box callout flex flex-wrap items-center gap-5 p-7">
      <div className="flex min-w-0 flex-[999_1_440px] flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="text-sm font-medium text-brand">Do this next</span>
          {next.priority === "high" && <span className="pill pill-fill">Do first</span>}
        </div>
        <h2 id="next-h" className="m-0 text-[28px] leading-[1.2] font-medium tracking-[-0.025em]">
          {next.title}
        </h2>
        {next.explanation && <p className="m-0 max-w-[820px]">{next.explanation}</p>}
        {next.sources[0] && <p className="muted m-0 text-sm">Source: {next.sources.map((src) => src.title).join("; ")}</p>}
      </div>
      <div className="flex flex-[1_1_220px] flex-wrap justify-end gap-2.5">
        <Link href={`${base}/r/${next.requirement_id}`} className="btn btn-p">
          {progressOf(next, marks) === "in_progress" ? "Continue this step" : "Start this step"}
        </Link>
      </div>
    </section>
  );
}

function QuestionList() {
  const { questions } = useBusiness();
  return questions.length ? (
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
  );
}

// Plain-language meaning of every label a requirement row can show.
const LEGEND: { pill: string; label: string; text: string }[] = [
  { pill: "pill", label: "Applies now", text: "Based on your answers, this likely applies to you today." },
  { pill: "pill pill-fill", label: "Do first", text: "Start with these. Other steps may depend on them." },
  { pill: "pill pill-dash", label: "Needs your input", text: "We need one more answer to know if it applies." },
  { pill: "pill pill-mute", label: "Coming up", text: "Not yet. It switches on later, for example when you hire." },
];

function RequirementList() {
  const { rows, marks } = useBusiness();
  const [filter, setFilter] = useState<Filter>("all");
  const s = summarize(rows, marks);
  const filters: { id: Filter; label: string }[] = [
    { id: "all", label: "All" },
    { id: "action", label: `To do (${s.action})` },
    { id: "input", label: `Need an answer (${s.input})` },
    { id: "done", label: `Done (${s.done})` },
  ];
  return (
    <div className="flex flex-col gap-3.5">
      <details className="fold box overflow-hidden">
        <summary className="flex items-center justify-between gap-2 bg-panel px-5 py-3.5">
          <span className="font-medium">What do the labels mean?</span>
          <svg className="chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </summary>
        <dl className="m-0 grid gap-x-6 gap-y-3 border-t border-line-soft p-5 sm:grid-cols-2">
          {LEGEND.map((l) => (
            <div key={l.label} className="flex items-start gap-3">
              <dt className="flex-none">
                <span className={l.pill}>{l.label}</span>
              </dt>
              <dd className="m-0 text-sm">{l.text}</dd>
            </div>
          ))}
        </dl>
      </details>

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

      {AREAS.map((area) => (
        <AreaGroup
          key={area.id}
          id={`area-${area.id}`}
          label={area.label}
          rows={rows.filter((r) => r.area === area.id)}
          filter={filter}
        />
      ))}
    </div>
  );
}

function CoverageBoxes() {
  const { rows } = useBusiness();
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="box flex flex-col gap-1.5 p-6">
        <h3 className="m-0 text-base font-medium">Covered</h3>
        <p className="m-0 text-sm">
          {rows.length} requirements for sole proprietors in the City of Vancouver: registration and licensing, tax
          registration, and employer obligations.
        </p>
      </div>
      <div className="box flex flex-col gap-1.5 border-line bg-side p-6">
        <h3 className="m-0 text-base font-medium">Not covered</h3>
        <p className="m-0 text-sm">
          Food safety and liquor licensing, zoning and building permits, signage, industry-specific permits, incorporated
          businesses and partnerships, and anything outside Vancouver.
        </p>
      </div>
    </div>
  );
}

// --- Walk-through steps ----------------------------------------------------------------------

function OverviewStep({ base }: { base: string }) {
  const { profile, assessment, rows } = useBusiness();
  if (!assessment || !profile) return null;
  const name = profile.trading_name || profile.legal_name || "your business";
  return (
    <>
      <StepHeading
        eyebrow={`Checked ${shortDate(assessment.cached_at ?? new Date().toISOString())} using ${confirmedFactCount(profile)} facts you confirmed`}
        title="Your results"
      >
        We found {rows.length} requirements that may apply to {name}. Each one is based on an official government
        source. Here&apos;s the short version. Use <strong className="font-medium">Next</strong> to go through it one
        step at a time.
      </StepHeading>
      <StatusBanner />
      <SummaryCards
        hrefs={{ action: stepHref(base, "next"), input: stepHref(base, "input"), later: stepHref(base, "all") }}
      />
      <ProgressBox />
    </>
  );
}

function NextStep({ base }: { base: string }) {
  const { rows, marks } = useBusiness();
  const next = nextStep(rows, marks);
  const after = rows
    .filter((r) => kindOf(r, marks) === "action" && r.requirement_id !== next?.requirement_id)
    .slice(0, 4);
  return (
    <>
      <StepHeading eyebrow="Step 2 of 5" title="Do this first">
        Start here. This is the most important thing to do right now. Open it for the steps, what to prepare and the
        official source.
      </StepHeading>
      <NextCallout base={base} />
      {after.length > 0 && (
        <section aria-labelledby="after-h" className="flex flex-col gap-3">
          <SectionHeading id="after-h" title="After that" />
          <div className="box overflow-hidden">
            {after.map((r) => (
              <Link
                key={r.requirement_id}
                href={`${base}/r/${r.requirement_id}`}
                className="flex items-center gap-3 border-t border-line-soft px-5 py-3.5 text-ink no-underline first:border-t-0 hover:bg-panel hover:text-ink"
              >
                <span className="min-w-0 flex-1 font-medium">{r.title}</span>
                {r.priority === "high" && <span className="pill pill-fill">Do first</span>}
                <Chevron dir="right" />
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function InputStep() {
  const { questions } = useBusiness();
  return (
    <>
      <StepHeading eyebrow="Step 3 of 5" title="A few questions for you">
        {questions.length
          ? `We need ${questions.length === 1 ? "one more answer" : `${questions.length} more answers`} to know whether some requirements apply to you. Each answer re-checks your results automatically.`
          : "We have everything we need. There's nothing for you to answer."}
      </StepHeading>
      <section id="input" aria-label="Your questions">
        <QuestionList />
      </section>
    </>
  );
}

function AllStep() {
  const { rows } = useBusiness();
  return (
    <>
      <StepHeading eyebrow="Step 4 of 5" title={`All ${rows.length} requirements`}>
        Everything that may apply to you, grouped by topic. Open any one for its steps and the official source it comes
        from.
      </StepHeading>
      <section id="all" aria-label="Requirements">
        <RequirementList />
      </section>
    </>
  );
}

function CoverageStep() {
  const { assessment, trace } = useBusiness();
  if (!assessment) return null;
  return (
    <>
      <StepHeading eyebrow="Step 5 of 5" title="What this check covers">
        So you know what we looked at, and what you may still need to check yourself.
      </StepHeading>
      <section id="coverage" aria-label="Coverage">
        <CoverageBoxes />
      </section>
      <p className="muted m-0 max-w-[820px] text-[13px]">{assessment.disclaimer}</p>
      <AgentTrace trace={trace} />
    </>
  );
}

// --- Needs your input: its own page, reached from the sidebar --------------------------------

export function NeedsInput() {
  const { businessId, assessment, questions, rows, marks } = useBusiness();
  if (!assessment) return null;
  const base = `/b/${businessId}`;
  const waiting = rows.filter((r) => kindOf(r, marks) === "input").length;

  return (
    <main className="inner flex w-full max-w-none flex-col gap-8">
      <StepHeading title="Needs your input">
        {questions.length
          ? `${questions.length === 1 ? "One question" : `${questions.length} questions`} left. Each answer tells us whether ${
              waiting === 1 ? "a requirement applies" : `${waiting} requirements apply`
            } to you, and your results re-check automatically.`
          : "You've answered everything. Your results are up to date."}
      </StepHeading>
      <StatusBanner />
      <section aria-label="Your questions">
        <QuestionList />
      </section>
      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-6">
        <Link href={stepHref(base, "dashboard")} className="btn btn-p">
          Back to my dashboard
        </Link>
      </div>
    </main>
  );
}

// --- The full dashboard: where the walk-through ends, with everything on one page ------------

function FullDashboard({ base }: { base: string }) {
  const { profile, assessment, rows, marks, questions, trace } = useBusiness();
  if (!assessment || !profile) return null;
  const s = summarize(rows, marks);
  const name = profile.trading_name || profile.legal_name || "Your business";

  return (
    <main className="inner flex w-full max-w-none flex-col gap-10">
      <section className="dash-hero relative overflow-hidden rounded-[2px] bg-brand px-8 py-9 text-white max-[720px]:px-5 max-[720px]:py-7">
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0 flex-[1_1_420px]">
            <span className="dash-badge inline-flex size-11 items-center justify-center rounded-full bg-white text-brand">
              <Tick size={20} />
            </span>
            <p className="mt-5 mb-2 text-[15px] text-white/75">
              {name}, checked {shortDate(assessment.cached_at ?? new Date().toISOString())}
            </p>
            <h1 className="m-0 text-[48px] leading-[1.04] font-medium tracking-[-0.04em] max-[720px]:text-[36px]">
              You&apos;re all set.
            </h1>
            <p className="mt-3 mb-0 max-w-[620px] text-[17px] text-white/85">
              This is your dashboard. Everything from your check is here in one place. Come back any time to tick
              things off or answer new questions.
            </p>
          </div>
          <div className="flex flex-col items-start gap-1">
            <span className="text-[40px] leading-none font-medium tracking-[-0.03em]">
              {s.done}
              <span className="text-white/55"> / {s.applicableNow}</span>
            </span>
            <span className="text-sm text-white/75">requirements done</span>
          </div>
        </div>
      </section>

      <StatusBanner />

      <SummaryCards hrefs={{ action: "#next", input: "#input", later: "#all" }} />

      <section id="next" aria-label="Do this next" className="flex scroll-mt-6 flex-col gap-3.5">
        <NextCallout base={base} />
      </section>

      <section id="input" aria-labelledby="input-h" className="flex scroll-mt-6 flex-col gap-3.5">
        <SectionHeading id="input-h" title={`Questions for you (${questions.length})`} hint="Each answer re-checks automatically" />
        <QuestionList />
      </section>

      <section id="all" aria-labelledby="all-h" className="flex scroll-mt-6 flex-col gap-3.5">
        <SectionHeading id="all-h" title={`All ${rows.length} requirements`} hint="Open any one for its steps and sources" />
        <RequirementList />
      </section>

      <section id="coverage" aria-labelledby="cov-h" className="flex scroll-mt-6 flex-col gap-3.5">
        <SectionHeading id="cov-h" title="What this check covers" />
        <CoverageBoxes />
        <p className="muted m-0 max-w-[820px] text-[13px]">{assessment.disclaimer}</p>
        <AgentTrace trace={trace} />
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-6">
        <Link href={base} className="btn btn-soft">
          Walk through my results again
        </Link>
        <Link href={`${base}/ask`} className="btn btn-p">
          Ask etika a question
        </Link>
      </div>
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
  label,
  rows,
  filter,
}: {
  id: string;
  label: string;
  rows: Row[];
  filter: Filter;
}) {
  const { businessId, marks } = useBusiness();
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
        <h3 className="m-0 flex items-center gap-2 text-base font-medium">{label}</h3>
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
