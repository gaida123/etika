// Turns an assessment response into what the dashboard and finding screens show (wireframes 03, 04a).
//
// Bucket comes from the backend (now / next / later). Owner progress (to do, in progress, done)
// is not tracked by the backend yet, so it is kept per browser in ./stored.ts and layered on top.

import type { Area, Assessment, AssessmentItem, BusinessProfile } from "./api";

export const AREAS: { id: Area; label: string }[] = [
  { id: "registration", label: "Registration & licensing" },
  { id: "tax", label: "Tax registration" },
  { id: "employer", label: "Employer" },
];

export const areaLabel = (area: Area) => AREAS.find((a) => a.id === area)?.label ?? area;

export type Bucket = "now" | "next" | "later";
export type Row = AssessmentItem & { bucket: Bucket };
export type Progress = "todo" | "in_progress" | "done";
export type Marks = Record<string, Progress>;
/** What the owner needs to do about a row: act, answer a question, nothing yet, or nothing (done). */
export type Kind = "action" | "input" | "upcoming" | "done";

export function rowsOf(a: Assessment): Row[] {
  return [
    ...a.now.map((i) => ({ ...i, bucket: "now" as const })),
    ...a.next.map((i) => ({ ...i, bucket: "next" as const })),
    ...a.later.map((i) => ({ ...i, bucket: "later" as const })),
  ];
}

export function progressOf(row: Row, marks: Marks): Progress {
  if (marks[row.requirement_id]) return marks[row.requirement_id];
  if (row.status === "done") return "done";
  if (row.status === "in_progress") return "in_progress";
  return "todo";
}

export function kindOf(row: Row, marks: Marks): Kind {
  if (row.missing_facts.length > 0 || row.applicability === "undetermined") return "input";
  if (row.bucket !== "now") return "upcoming";
  return progressOf(row, marks) === "done" ? "done" : "action";
}

export function appliesPill(row: Row, kind: Kind): { label: string; className: string } {
  if (kind === "input") return { label: "Needs your input", className: "pill pill-dash" };
  if (row.bucket === "now") return { label: "Applies now", className: "pill" };
  if (row.trigger === "first_hire") return { label: "When you hire", className: "pill pill-mute" };
  return { label: "Coming up", className: "pill pill-mute" };
}

export function priorityPill(row: Row, kind: Kind): { label: string; className: string } | null {
  if (kind !== "action") return null;
  return row.priority === "high"
    ? { label: "Do first", className: "pill pill-fill" }
    : { label: "Soon", className: "pill pill-mute" };
}

export function statusText(row: Row, kind: Kind, marks: Marks): string {
  if (kind === "done") return "Done";
  if (kind === "input") return "Waiting on you";
  if (kind === "upcoming") return "Not yet";
  return progressOf(row, marks) === "in_progress" ? "In progress" : "To do";
}

const money = (n: number) => `$${Math.round(n).toLocaleString("en-CA")}`;

export function monthText(yyyyMm: string): string {
  const [y, m] = yyyyMm.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-CA", { month: "short", year: "numeric" });
}

/** One-line context under a row: threshold progress or what switches it on. */
export function detailLine(row: Row): string | undefined {
  if (row.progress) {
    const { current, threshold, estimated_crossing } = row.progress;
    const est = estimated_crossing ? `, estimated to cross around ${monthText(estimated_crossing)}` : "";
    return `${money(current)} of the ${money(threshold)} line${est}`;
  }
  if (row.trigger === "first_hire") return "Switches on when you hire";
  return undefined;
}

export type Summary = {
  applicableNow: number;
  done: number;
  action: number;
  doFirst: number;
  input: number;
  upcoming: number;
};

export function summarize(rows: Row[], marks: Marks): Summary {
  const kinds = rows.map((r) => kindOf(r, marks));
  const nowRows = rows.filter((r) => r.bucket === "now");
  return {
    applicableNow: nowRows.length,
    done: kinds.filter((k) => k === "done").length,
    action: kinds.filter((k) => k === "action").length,
    doFirst: rows.filter((r, i) => kinds[i] === "action" && r.priority === "high").length,
    input: kinds.filter((k) => k === "input").length,
    upcoming: kinds.filter((k) => k === "upcoming").length,
  };
}

/** The first open `now` item. The backend already orders `now` by dependencies, then priority. */
export function nextStep(rows: Row[], marks: Marks): Row | undefined {
  return rows.find((r) => kindOf(r, marks) === "action" && progressOf(r, marks) !== "in_progress")
    ?? rows.find((r) => kindOf(r, marks) === "action");
}

export function confirmedFactCount(p: BusinessProfile): number {
  return Object.values(p.facts).filter((f) => f.confirmed && f.value !== null && f.value !== undefined).length;
}

/** Official links come only from the registry; stub rows still hold placeholders like "TODO-official-url". */
export const isRealUrl = (url: string | null | undefined): url is string => !!url && /^https?:\/\//.test(url);

export function shortDate(iso: string | null | undefined): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" });
}
