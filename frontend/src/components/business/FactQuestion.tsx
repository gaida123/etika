"use client";

// One follow-up question (GET /profile/{id}/questions). Used as a row on the dashboard's
// "Needs your input" list (wireframe 03) and as the chat's missing-fact card (wireframe 05, state B).
// "Not sure" saves nothing: the fact stays unknown, which is never treated as false.

import { useState } from "react";
import { Select } from "@/components/ui";
import type { FollowUpQuestion } from "@/lib/api";
import { monthText } from "@/lib/assessment";
import { upcomingMonths } from "@/lib/intake";
import { useBusiness } from "./BusinessProvider";

type Choice = { label: string; value: unknown };

function choicesFor(q: FollowUpQuestion): Choice[] | null {
  if (q.answer_type === "bool")
    return [
      { label: "Yes", value: true },
      { label: "No", value: false },
    ];
  if (q.answer_type === "enum") return q.options.map((o) => ({ label: o[0].toUpperCase() + o.slice(1), value: o }));
  return null;
}

function pastMonths(count = 12, from = new Date()): string[] {
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(from.getFullYear(), from.getMonth() - count + i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
}



export function FactQuestion({ question, variant }: { question: FollowUpQuestion; variant: "row" | "card" }) {
  const { answer, rechecking, rows } = useBusiness();
  const [state, setState] = useState<{ kind: "idle" | "saving" | "unsure" } | { kind: "error"; message: string }>({
    kind: "idle",
  });
  const [text, setText] = useState("");
  const [revenue, setRevenue] = useState<Record<string, string>>({});
  // The choice the owner clicked, held highlighted until the save and re-check finish.
  const [picked, setPicked] = useState<string | null>(null);
  const busy = state.kind === "saving" || rechecking;

  const unlocks = question.needed_for
    .map((id) => rows.find((r) => r.requirement_id === id)?.title ?? id)
    .join(", ");

  async function save(body: Parameters<typeof answer>[0]) {
    setState({ kind: "saving" });
    try {
      await answer(body);
      setState({ kind: "idle" });
    } catch (e) {
      setState({ kind: "error", message: e instanceof Error ? e.message : "Couldn't save. Try again." });
    } finally {
      setPicked(null);
    }
  }

  const choices = choicesFor(question);
  const btn = variant === "card" ? "btn btn-s" : "opt opt-s cursor-pointer";

  const controls = (
    <div className="flex flex-wrap items-center gap-2">
      {choices?.map((c) => (
        <button
          key={c.label}
          type="button"
          className={`${btn} ${picked === c.label ? "pick-on" : ""}`}
          aria-pressed={picked === c.label}
          disabled={busy}
          onClick={() => {
            setPicked(c.label);
            save({ facts: { [question.fact_key]: c.value } });
          }}
        >
          {c.label}
        </button>
      ))}

      {question.answer_type === "month" && (
        <>
          <span className="min-w-[180px]">
            <Select aria-label="Month" value={text} onChange={(e) => setText(e.target.value)} disabled={busy}>
              <option value="">Month</option>
              {upcomingMonths().map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </span>
          <button
            type="button"
            className="btn btn-s btn-p"
            disabled={busy || !text}
            onClick={() => save({ facts: { [question.fact_key]: text } })}
          >
            Save
          </button>
        </>
      )}

      {question.answer_type === "text" && (
        <>
          <input
            className="inp max-w-[260px]"
            aria-label={question.question}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
          />
          <button
            type="button"
            className="btn btn-s btn-p"
            disabled={busy || !text.trim()}
            onClick={() => save({ facts: { [question.fact_key]: text.trim() } })}
          >
            Save
          </button>
        </>
      )}

      {question.answer_type !== "monthly_revenue" && (
        <button
          type="button"
          className={`${variant === "card" ? "btn btn-s btn-soft" : "opt opt-s cursor-pointer"} ${state.kind === "unsure" ? "pick-on" : ""}`}
          aria-pressed={state.kind === "unsure"}
          disabled={busy}
          onClick={() => setState({ kind: "unsure" })}
        >
          Not sure
        </button>
      )}
    </div>
  );

  const revenueForm = question.answer_type === "monthly_revenue" && (
    <form
      className="flex w-full flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        const entries = Object.entries(revenue)
          .filter(([, v]) => v.trim() !== "")
          .map(([month, v]) => ({ month, amount: Number(v) }));
        if (entries.length) save({ monthly_revenue: entries });
      }}
    >
      <div className="grid grid-cols-[repeat(auto-fill,minmax(120px,1fr))] gap-2">
        {pastMonths().map((m) => (
          <label key={m} className="flex flex-col gap-1 text-[13px]">
            <span className="muted">{monthText(m)}</span>
            <input
              className="inp min-h-9"
              inputMode="decimal"
              type="number"
              min={0}
              step="any"
              placeholder="$0"
              value={revenue[m] ?? ""}
              onChange={(e) => setRevenue({ ...revenue, [m]: e.target.value })}
              disabled={busy}
            />
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className="btn btn-s btn-p" disabled={busy || !Object.values(revenue).some((v) => v)}>
          Save sales
        </button>
        <span className="muted text-[13px]">Estimates are fine. Leave a month blank if you don&apos;t know.</span>
      </div>
    </form>
  );

  const status =
    state.kind === "saving" ? (
      <span className="muted text-[13px]">Saving and re-checking…</span>
    ) : state.kind === "unsure" ? (
      <span className="muted text-[13px]">Kept as unknown. We won&apos;t guess, so this stays open.</span>
    ) : state.kind === "error" ? (
      <span className="text-[13px] text-[#a3341f]" role="alert">
        {state.message}
      </span>
    ) : null;

  if (variant === "card") {
    return (
      <fieldset className="m-0 flex min-w-0 flex-col gap-2.5 rounded-[2px] border border-line p-3.5">
        <legend className="px-1.5 text-sm font-medium">{question.question}</legend>
        {revenueForm || controls}
        {status ?? (
          <span className="muted text-[13px]">Your answer updates your profile and re-checks {unlocks}.</span>
        )}
      </fieldset>
    );
  }

  return (
    <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2.5 border-t border-line-soft px-5 py-4 first:border-t-0">
      <legend className="float-left min-w-0 flex-[1_1_360px]">
        <span className="font-medium">{question.question}</span>
        <br />
        <span className="muted text-[13px]">Unlocks: {unlocks}</span>
      </legend>
      {revenueForm || controls}
      {status && <div className="basis-full">{status}</div>}
    </fieldset>
  );
}
