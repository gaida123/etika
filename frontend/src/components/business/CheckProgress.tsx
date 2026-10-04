"use client";

// Wireframe "Checking": the live check, from confirmed facts through the coordinator and one agent per
// area to the source check. POST /assess answers only once every agent is finished, so while it runs
// the agents' steps follow a timeline that mirrors the backend's staggered launches. Lanes finish and
// findings appear only once the real results are in.

import Link from "next/link";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { CheckIcon } from "@/components/ui";
import type { Area, BusinessProfile } from "@/lib/api";
import { AREAS, type Row, confirmedFactCount, kindOf } from "@/lib/assessment";
import { useBusiness } from "./BusinessProvider";
import { AreaIcon } from "./icons";

const TICK = 200;
const COORD = 1200; // coordinator splits the check
const STAGGER = 3000; // backend agent_start_stagger_seconds
const STEP = 6000; // time per scripted agent step while waiting
const MIN_WORK = 1400; // every lane is seen working before it finishes
const DONE_GAP = 450; // lanes finish one after another
const MERGE = 300;
const SOURCE = 1300; // source check

type Clock = { run: number; elapsed: number; resolvedAt: number | null };
type LaneState = "wait" | "work" | "done";
type Stage = 0 | 1 | 2 | 3;

export type Lane = {
  area: Area;
  label: string;
  state: LaneState;
  activity: string;
  step: number;
  /** 0–1 while working. */
  progress: number;
  failed: boolean;
  rows: Row[];
};

export type CheckRun = {
  stage: Stage;
  ready: boolean;
  lanes: Lane[];
  /** 0–100 */
  percent: number;
  checkStarted: boolean;
};

function schedule(resolvedAt: number | null) {
  const starts = AREAS.map((_, i) => COORD + i * STAGGER);
  if (resolvedAt === null) return { starts, dones: null, checkStart: Infinity, readyAt: Infinity };
  const dones: number[] = [];
  starts.forEach((start, i) => dones.push(Math.max(resolvedAt, start + MIN_WORK, i ? dones[i - 1] + DONE_GAP : 0)));
  const checkStart = dones[dones.length - 1] + MERGE;
  return { starts, dones, checkStart, readyAt: checkStart + SOURCE };
}

const ease = (t: number, tau: number) => 1 - Math.exp(-t / tau);

function activities(area: Area, profile: BusinessProfile | null): string[] {
  const staff = profile?.facts.has_employees?.value;
  const people = staff === false ? "owner only, no staff" : staff === true ? "has employees" : "your hiring facts";
  const sources: Record<Area, string> = {
    registration: "Searching City of Vancouver and BC Registries sources",
    tax: "Searching CRA and BC PST guidance",
    employer: "Searching WorkSafeBC and Employment Standards guidance",
  };
  const rules: Record<Area, string> = {
    registration: "Matching licence and registration rules to your facts",
    tax: "Checking sales thresholds against your revenue",
    employer: `Checking employer rules against: ${people}`,
  };
  return ["Reading your confirmed facts", sources[area], rules[area], "Writing up findings"];
}

export function useCheckRun(): CheckRun | null {
  const { checkRun, assessment, rows, profile } = useBusiness();
  const [clock, setClock] = useState<Clock | null>(null);
  const resolved = useRef(false);

  useEffect(() => {
    resolved.current = assessment !== null;
  }, [assessment]);

  useEffect(() => {
    if (checkRun === null) return;
    const start = performance.now();
    let resolvedAt: number | null = null;
    const tick = () => {
      const elapsed = performance.now() - start;
      if (resolvedAt === null && resolved.current) resolvedAt = elapsed;
      setClock({ run: checkRun, elapsed, resolvedAt });
      if (elapsed > schedule(resolvedAt).readyAt) clearInterval(id);
    };
    const id = setInterval(tick, TICK);
    return () => clearInterval(id);
  }, [checkRun]);

  if (checkRun === null) return null;
  const { elapsed: e, resolvedAt } = clock?.run === checkRun ? clock : { elapsed: 0, resolvedAt: null };
  const { starts, dones, checkStart, readyAt } = schedule(resolvedAt);

  const lanes: Lane[] = AREAS.map((a, i) => {
    const steps = activities(a.id, profile);
    const failed = !!assessment?.agents.find((x) => x.agent === a.id)?.error;
    const laneRows = rows.filter((r) => r.area === a.id);
    if (dones && e >= dones[i]) {
      const sources = new Set(laneRows.flatMap((r) => r.sources.map((s) => s.title))).size;
      const n = laneRows.length;
      return {
        area: a.id, label: a.label, state: "done", step: 4, progress: 1, failed, rows: laneRows,
        activity: failed
          ? `Checked ${n} ${n === 1 ? "requirement" : "requirements"} by our rules. Official sources were unavailable.`
          : `Checked ${n} ${n === 1 ? "requirement" : "requirements"} across ${sources} ${sources === 1 ? "source" : "sources"}`,
      };
    }
    if (e < starts[i]) {
      return { area: a.id, label: a.label, state: "wait", step: 0, progress: 0, failed, rows: [], activity: "Waiting for the coordinator" };
    }
    const t = e - starts[i];
    const step = Math.min(4, 1 + Math.floor(t / STEP));
    // Agents queue for report calls, so live runs can take a minute; keep the bar moving that long.
    const progress = 0.06 + 0.86 * ease(t, 20000);
    return { area: a.id, label: a.label, state: "work", step, progress, failed, rows: [], activity: steps[step - 1] };
  });

  const ready = e >= readyAt;
  const checkStarted = e >= checkStart;
  const percent =
    5 * Math.min(1, e / COORD) +
    lanes.reduce((n, l) => n + (l.state === "done" ? 30 : 30 * 0.92 * l.progress), 0) +
    (ready ? 5 : checkStarted ? 5 * Math.min(1, (e - checkStart) / SOURCE) : 0);
  const stage: Stage = ready ? 3 : checkStarted ? 2 : e >= COORD ? 1 : 0;
  return { stage, ready, lanes, percent: Math.min(100, percent), checkStarted };
}

const STAGES = ["Starting", "Agents working", "Checking sources", "Ready"];
const FAN_DONE = "var(--color-brand)";
const LINE = "var(--color-line)";
const LINE_ON = "#b9c8ae";

function factPills(p: BusinessProfile): string[] {
  const v = (k: string) => p.facts[k]?.confirmed ? p.facts[k].value : undefined;
  const sells = ({ goods: "Sells goods", services: "Sells services", both: "Goods & services" } as Record<string, string>)[
    String(v("sells"))
  ];
  return [
    sells,
    v("operates_in_vancouver") === true ? "Vancouver" : undefined,
    v("has_employees") === false ? "Owner only" : v("has_employees") === true ? "Has staff" : undefined,
    v("home_based") === true ? "Home-based" : undefined,
  ]
    .filter((x): x is string => !!x)
    .slice(0, 3);
}

type Found = { row: Row; label: string; className: string };

function foundOf(row: Row, kind: ReturnType<typeof kindOf>): Found | null {
  if (kind === "input") return { row, label: "Needs your input", className: "pill pill-dash" };
  if (row.bucket === "now") return { row, label: "May apply", className: "pill" };
  return null;
}

export function CheckProgress({ run, onDone }: { run: CheckRun; onDone: () => void }) {
  const { profile, marks, rows } = useBusiness();
  const { stage, ready, lanes, percent, checkStarted } = run;
  const name = profile?.trading_name || profile?.legal_name || "your business";
  const facts = profile ? confirmedFactCount(profile) : 0;

  const done = lanes.filter((l) => l.state === "done");
  const found: Found[] = [];
  let hidden = 0;
  for (const l of done)
    for (const r of l.rows) {
      const f = foundOf(r, kindOf(r, marks));
      if (f) found.push(f);
      else hidden += 1;
    }
  const may = found.filter((f) => f.label === "May apply").length;
  const ask = found.length - may;
  const checked = done.reduce((n, l) => n + l.rows.length, 0);
  const total = rows.length;
  const cited = rows.filter((r) => r.sources.length > 0).length;
  const failed = lanes.filter((l) => l.failed).length;

  const coordDone = stage > 0;
  const anyStarted = lanes.some((l) => l.state !== "wait");
  const fanLine = coordDone ? FAN_DONE : LINE;
  const mergeLine = checkStarted ? FAN_DONE : anyStarted ? LINE_ON : LINE;

  const progLabel =
    stage === 3
      ? `${total} of ${total} requirements checked`
      : stage === 2
        ? `${total} of ${total} checked, confirming sources`
        : done.length
          ? `${checked} of ${total} requirements checked`
          : stage === 1
            ? `${lanes.filter((l) => l.state === "work").length} of 3 agents working`
            : "Splitting your check into 3 areas";

  const subtitle = ready
    ? `All three areas are checked${
        failed ? `, though ${failed} ${failed === 1 ? "agent" : "agents"} couldn't reach official sources` : cited === total ? " and every finding has an official source" : ""
      }. Here is what may apply to ${name}.`
    : "Three agents check your facts against official sources, one for each area. You can watch what they find as they finish.";

  return (
    <main className="inner flex max-w-[1120px] flex-col gap-7">
      <div>
        <p className="pre">
          {name}, {facts} confirmed facts
        </p>
        <h1 className="hxl">{ready ? "Your check is ready." : "Checking your business."}</h1>
        <p className="muted mt-3.5 mb-0 max-w-[680px] text-[17px]">{subtitle}</p>
      </div>

      <section aria-label="Overall progress" className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <span className="inline-flex items-center gap-2.5" aria-live="polite">
            {ready ? (
              <span className="ck-pop inline-flex text-brand">
                <CheckIcon size={14} />
              </span>
            ) : (
              <span className="ck-spin" aria-hidden="true" />
            )}
            <span className="font-medium">{STAGES[stage]}</span>
          </span>
          <span className="muted text-sm">{progLabel}</span>
        </div>
        <div
          className="ck-bar h-1.5 rounded-[3px]"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(percent)}
          aria-label="Check progress"
        >
          <div style={{ width: `${percent}%`, transitionDuration: ready ? undefined : `${TICK}ms`, transitionTimingFunction: ready ? undefined : "linear" }} />
        </div>
      </section>

      <section className="box flex flex-col gap-4 px-[22px] pt-5 pb-[22px]" aria-labelledby="how-h">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1.5">
          <h2 id="how-h" className="m-0 text-[17px] font-medium">
            How your check runs
          </h2>
          <span className="muted text-[13px]">Each area has its own agent. They work at the same time.</span>
        </div>

        <div className="ck-flow">
          <span className="ck-lbl" style={o(1)}>
            <b>1</b>Your facts
          </span>
          <span className="ck-gap" />
          <span className="ck-lbl" style={o(3)}>
            <b>2</b>Coordinator
          </span>
          <span className="ck-gap" />
          <span className="ck-lbl pl-2.5" style={o(5)}>
            <b>3</b>Area agents
          </span>
          <span className="ck-gap" />
          <span className="ck-lbl" style={o(7)}>
            <b>4</b>Source check
          </span>

          <div className="ck-node done" style={o(2)}>
            <span className="text-sm leading-[1.3] font-medium">{facts} confirmed</span>
            {profile && (
              <div className="flex flex-wrap gap-1">
                {factPills(profile).map((f) => (
                  <span key={f} className="pill pill-mute h-[22px] text-xs font-normal">
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="ck-conn done" aria-hidden="true" />
          <div className={`ck-node ${coordDone ? "done" : "work"}`} style={o(4)}>
            <span
              aria-hidden="true"
              className="inline-flex size-8 items-center justify-center rounded-full bg-brand text-white"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M12 1v22M1 12h22M4.2 4.2l15.6 15.6M19.8 4.2 4.2 19.8" />
              </svg>
            </span>
            <span className="text-[13px] leading-[1.3]">
              {coordDone ? "Sent your facts to 3 agents" : "Splitting your check into 3 areas"}
            </span>
          </div>
          <div className={`ck-conn ${coordDone ? "done" : "on"}`} aria-hidden="true" />

          <div className="ck-lanes" style={{ ...o(6), "--fan": fanLine, "--merge": mergeLine } as CSSProperties}>
            <div aria-hidden="true" className="ck-rail left-[-1px]" style={{ background: fanLine }} />
            <div aria-hidden="true" className="ck-rail right-[-1px]" style={{ background: mergeLine }} />
            {lanes.map((l) => (
              <LaneCard key={l.area} lane={l} />
            ))}
          </div>

          <div className={`ck-conn ${ready ? "done" : checkStarted ? "on" : ""}`} aria-hidden="true" />
          <div className={`ck-node ${ready ? "done" : checkStarted ? "work" : "wait"}`} style={o(8)}>
            <span className="inline-flex items-center gap-1.5 text-sm leading-[1.3] font-medium">
              {ready ? (
                <span className="ck-pop inline-flex text-brand">
                  <CheckIcon size={14} />
                </span>
              ) : (
                checkStarted && <span className="ck-spin" aria-hidden="true" />
              )}
              {ready ? `${cited} of ${total} cited` : checkStarted ? "Checking citations" : "Waits for all agents"}
            </span>
            <span className="muted text-[13px] leading-[1.35]">Every finding needs an official passage before you see it.</span>
          </div>
        </div>
      </section>

      <section className="box overflow-hidden" aria-labelledby="found-h">
        <div className="flex flex-wrap items-center justify-between gap-2 bg-panel px-5 py-4">
          <h2 id="found-h" className="m-0 text-[17px] font-medium">
            {ready ? "What we found" : "Found so far"}
          </h2>
          <span className="muted text-sm" aria-live="polite">
            {done.length === 0
              ? "Nothing yet"
              : `${may} may apply, ${ask} ${ask === 1 ? "needs" : "need"} your input`}
          </span>
        </div>
        {found.map((f, i) => (
          <div key={f.row.requirement_id} className="ck-find" style={{ animationDelay: `${(i % 6) * 60}ms` }}>
            <div className="min-w-0 flex-[1_1_260px]">
              <div className="font-medium">{f.row.title}</div>
              <div className="muted text-[13px]">
                {AREAS.find((a) => a.id === f.row.area)?.label}, source:{" "}
                {f.row.sources[0]?.title ?? "no official source yet"}
              </div>
            </div>
            <span className={f.className}>{f.label}</span>
          </div>
        ))}
        {done.length === 0 && (
          <div className="flex flex-col gap-2.5 border-t border-line-soft p-5">
            <div className="ck-sk w-[70%]" />
            <div className="ck-sk w-[52%]" />
            <span className="muted text-[13px]">Findings show up here as each agent finishes.</span>
          </div>
        )}
        {hidden > 0 && (
          <div className="muted ck-find-fade border-t border-line-soft px-5 py-3 text-sm">
            {hidden} {hidden === 1 ? "requirement switches" : "requirements switch"} on later based on your facts. You can
            review them in your results.
          </div>
        )}
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
        <span className="muted max-w-[520px] text-sm">
          {ready
            ? "Results are saved to Overview. We re-check whenever your facts change."
            : "This can take up to a minute. Keep this tab open while your check runs."}
        </span>
        <div className="flex flex-wrap gap-2.5">
          <Link href="/" className="btn btn-soft">
            Start a new check
          </Link>
          {ready ? (
            <button type="button" className="btn btn-p ck-cta" onClick={onDone}>
              See my results
            </button>
          ) : (
            <span className="btn ck-cta ck-off" aria-disabled="true">
              See my results
            </span>
          )}
        </div>
      </div>
    </main>
  );
}

/** Reading order once the flow stacks on narrow screens. */
const o = (n: number) => ({ "--o": n }) as CSSProperties;

function LaneCard({ lane: l }: { lane: Lane }) {
  return (
    <div className={`ck-node ck-lane ${l.state}`}>
      <span className="ck-ic" aria-hidden="true">
        {l.state === "done" ? <CheckIcon size={16} /> : <AreaIcon area={l.area} size={16} strokeWidth={1.6} />}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <span className="text-sm leading-[1.3] font-medium">{l.label} agent</span>
        <span key={l.activity} className="muted ck-swap text-[13px] leading-[1.35]">
          {l.activity}
        </span>
        <div className={`ck-bar ck-lane-bar mt-1 ${l.state === "work" ? "" : "ck-hide"}`}>
          <div style={{ width: `${l.state === "done" ? 100 : l.progress * 100}%`, transitionDuration: `${TICK}ms`, transitionTimingFunction: "linear" }} />
        </div>
      </div>
      <span className="justify-self-end">
        {l.state === "done" ? (
          <span className={`ck-st ck-pop ${l.failed ? "" : "ck-st-done"}`}>
            {l.failed ? "Partial" : (
              <>
                <CheckIcon size={14} />
                Done
              </>
            )}
          </span>
        ) : l.state === "work" ? (
          <span className="ck-st">
            <span className="ck-spin ck-spin-sm" aria-hidden="true" />
            Step {l.step} of 4
          </span>
        ) : (
          <span className="ck-st ck-st-wait">Up next</span>
        )}
      </span>
    </div>
  );
}

/** Sidebar status for one category while the check screen is open. */
export function LaneStatus({ lane }: { lane: Lane }) {
  return lane.state === "done" ? (
    <span className="count ck-pop inline-flex text-brand" role="img" aria-label="Checked">
      <CheckIcon size={14} />
    </span>
  ) : (
    <span className="count inline-flex" role="img" aria-label="Checking">
      <span className="ck-spin ck-spin-sm" />
    </span>
  );
}
