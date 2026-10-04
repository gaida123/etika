"use client";

// Ask etika (wireframes 04a panel, 04b full view, 05 answer states).
// A: not enough evidence. B: answer depends on a missing fact. C: profile-change proposal.

import Link from "next/link";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { LogoMark, Select } from "@/components/ui";
import type { ProposedFact } from "@/lib/api";
import { isRealUrl } from "@/lib/assessment";
import { factField, factText } from "@/lib/facts";
import { type ChatTurn, useBusiness } from "./BusinessProvider";
import { FactQuestion } from "./FactQuestion";

export const SUGGESTIONS_GENERAL = [
  "Do I need a business licence?",
  "When do I have to register for PST?",
  "What changes when I hire someone?",
];

export const SUGGESTIONS_TOPIC = [
  "What do I need to prepare?",
  "What happens if I skip this?",
  "Does this depend on how much I sell?",
];

/** Sources cited across the conversation, in first-seen order, numbered from 1. */
export function conversationSources(turns: ChatTurn[]) {
  const seen = new Map<string, { n: number; title: string; url: string }>();
  for (const t of turns)
    for (const s of t.response?.sources ?? [])
      if (!seen.has(s.url + s.title)) seen.set(s.url + s.title, { n: seen.size + 1, ...s });
  return [...seen.values()];
}

export function ChatThread({ turns, variant }: { turns: ChatTurn[]; variant: "panel" | "full" }) {
  const sources = conversationSources(turns);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (turns.length) end.current?.scrollIntoView({ block: "nearest" });
  }, [turns.length]);

  return (
    <>
      {turns.map((t) => (
        <div key={t.id} className="flex flex-col gap-4">
          <div className={`q ${variant === "full" ? "max-w-[75%] px-4 py-3" : ""}`}>{t.question}</div>
          <Answer turn={t} sourceNumber={(title, url) => sources.find((s) => s.title === title && s.url === url)?.n} variant={variant} />
        </div>
      ))}
      <div ref={end} />
    </>
  );
}

function Answer({
  turn,
  sourceNumber,
  variant,
}: {
  turn: ChatTurn;
  sourceNumber: (title: string, url: string) => number | undefined;
  variant: "panel" | "full";
}) {
  const { questions, rows, businessId } = useBusiness();
  const r = turn.response;

  const body = (() => {
    if (turn.error)
      return (
        <p className="m-0 text-sm text-[#a3341f]" role="alert">
          {turn.error}
        </p>
      );
    if (!r)
      return (
        <p className="muted m-0 flex items-center gap-2 text-sm" aria-live="polite">
          <span className="spin" /> Checking official sources…
        </p>
      );

    if (r.insufficient_evidence)
      return (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 rounded-[2px] border border-dashed border-ink p-3.5">
            <div className="flex items-center gap-2 font-medium">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v5m0 3v.5" />
              </svg>
              We can&apos;t answer this confidently
            </div>
            <p className="m-0 text-sm">{r.answer}</p>
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">What you can do</span>
            <Link href={`/b/${businessId}#coverage`} className="btn btn-s btn-soft self-start">
              See what etika covers
            </Link>
          </div>
        </div>
      );

    // State B: questions whose answer could change requirements in the area this agent covers.
    const areaIds = new Set(rows.filter((row) => row.area === r.agent).map((row) => row.requirement_id));
    const missing = questions.filter((q) => q.needed_for.some((id) => areaIds.has(id))).slice(0, 1);

    return (
      <div className="flex flex-col gap-3">
        <p className="m-0 whitespace-pre-line">{r.answer}</p>
        {r.sources.map((s) => (
          <SourceCard key={s.url + s.title} n={sourceNumber(s.title, s.url)} title={s.title} url={s.url} full={variant === "full"} />
        ))}
        {missing.length > 0 && !turn.proposal && (
          <>
            <p className="m-0">This could change with a fact we don&apos;t have yet:</p>
            {missing.map((q) => (
              <FactQuestion key={q.fact_key} question={q} variant="card" />
            ))}
          </>
        )}
      </div>
    );
  })();

  return (
    <div className="flex flex-col gap-4">
      {variant === "full" ? (
        <div className="flex items-start gap-3">
          <LogoMark size={20} className="mt-[3px]" />
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            {body}
            {r && turn.proposal && <ProposalCard turn={turn} />}
          </div>
        </div>
      ) : (
        <>
          {body}
          {r && turn.proposal && <ProposalCard turn={turn} />}
        </>
      )}
    </div>
  );
}

function SourceCard({ n, title, url, full }: { n?: number; title: string; url: string; full: boolean }) {
  const inner = (
    <>
      <span className="muted text-xs">{n ? `Source ${n}` : "Source"}</span>
      <span className="text-sm font-medium">{title}</span>
      {isRealUrl(url) ? (
        full ? null : (
          <span className="text-[13px] text-brand underline underline-offset-[3px]">Open official source ↗</span>
        )
      ) : (
        <span className="muted text-[13px]">Official link not added yet</span>
      )}
    </>
  );
  if (full && n) {
    return (
      <a href={`#s${n}`} className="box src max-w-[520px]">
        {inner}
      </a>
    );
  }
  return isRealUrl(url) ? (
    <a href={url} target="_blank" rel="noreferrer" className="box src">
      {inner}
    </a>
  ) : (
    <div className="box src">{inner}</div>
  );
}

function ProposalCard({ turn }: { turn: ChatTurn }) {
  const { profile, confirmTurn, dismissTurn } = useBusiness();
  const [editing, setEditing] = useState(false);
  const [edits, setEdits] = useState<Record<string, unknown>>({});
  const facts = turn.response?.proposed_facts ?? [];

  if (turn.proposal === "dismissed")
    return <p className="muted m-0 text-[13px]">Not changed. Your profile stays as it was.</p>;
  if (turn.proposal === "confirmed")
    return (
      <p className="m-0 text-sm font-medium text-brand" role="status">
        Profile updated and re-checked.
      </p>
    );

  const saving = turn.proposal === "saving";
  const valueOf = (f: ProposedFact) => (f.key in edits ? edits[f.key] : f.value);

  return (
    <div className="flex flex-col gap-3">
      <p className="m-0">That changes your business profile, which can change what applies. Want to update it?</p>
      <div className="box callout flex flex-col gap-3 p-4">
        <div className="tag">Proposed change</div>
        {facts.map((f) => {
          const was = profile?.facts[f.key];
          return (
            <div key={f.key} className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              <span className="muted">Field</span>
              <span className="font-medium">{factField(f.key)}</span>
              <span className="muted">Was</span>
              <span className={was?.confirmed ? "line-through" : "muted"}>
                {was?.confirmed ? factText(f.key, was.value) : "Unknown"}
              </span>
              <span className="muted">Now</span>
              {editing ? (
                <EditValue fact={f} value={valueOf(f)} onChange={(v) => setEdits({ ...edits, [f.key]: v })} />
              ) : (
                <span className="font-medium">{factText(f.key, valueOf(f))}</span>
              )}
            </div>
          );
        })}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-s btn-p" disabled={saving} onClick={() => confirmTurn(turn.id, edits)}>
            {saving ? "Re-checking…" : "Confirm and re-check"}
          </button>
          <button type="button" className="btn btn-s border-step-off" disabled={saving} onClick={() => setEditing(!editing)}>
            {editing ? "Done editing" : "Edit"}
          </button>
          <button type="button" className="btn btn-s border-transparent" disabled={saving} onClick={() => dismissTurn(turn.id)}>
            Not now
          </button>
        </div>
        {turn.proposalError && (
          <span className="text-[13px] text-[#a3341f]" role="alert">
            {turn.proposalError}
          </span>
        )}
      </div>
      <p className="muted m-0 text-[13px]">etika never changes your profile without your OK.</p>
    </div>
  );
}

function EditValue({ fact, value, onChange }: { fact: ProposedFact; value: unknown; onChange: (v: unknown) => void }) {
  if (typeof fact.value === "boolean")
    return (
      <Select aria-label={factField(fact.key)} className="min-h-9" value={String(value)} onChange={(e) => onChange(e.target.value === "true")}>
        <option value="true">{factText(fact.key, true)}</option>
        <option value="false">{factText(fact.key, false)}</option>
      </Select>
    );
  return (
    <input
      aria-label={factField(fact.key)}
      className="inp min-h-9"
      value={String(value ?? "")}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function Composer({
  topic,
  placeholder,
  variant,
}: {
  topic: string | null;
  placeholder: string;
  variant: "panel" | "full";
}) {
  const { ask, turns } = useBusiness();
  const [text, setText] = useState("");
  const pending = turns.some((t) => !t.response && !t.error);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const q = text.trim();
    if (!q || pending) return;
    ask(q, topic);
    setText("");
  }

  if (variant === "panel")
    return (
      <form onSubmit={submit} className="mt-auto flex gap-2 border-t border-line-soft px-5 py-4">
        <label htmlFor="ask" className="sr-only">
          Your question
        </label>
        <input id="ask" className="inp flex-1" placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="btn btn-p" disabled={pending || !text.trim()}>
          Ask
        </button>
      </form>
    );

  return (
    <form onSubmit={submit} className="box flex items-end gap-2 border-field p-2.5">
      <label htmlFor="ask" className="sr-only">
        Your question
      </label>
      <textarea
        id="ask"
        rows={2}
        placeholder={placeholder}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e: KeyboardEvent) => {
          if (e.key === "Enter" && !e.shiftKey) submit(e as unknown as FormEvent);
        }}
        className="min-w-0 flex-1 resize-none border-0 p-1.5 outline-none"
      />
      <button type="submit" className="btn btn-p" disabled={pending || !text.trim()}>
        Ask
      </button>
    </form>
  );
}

export function Suggestions({ items, topic }: { items: string[]; topic: string | null }) {
  const { ask, turns } = useBusiness();
  const pending = turns.some((t) => !t.response && !t.error);
  const asked = new Set(turns.map((t) => t.question));
  const left = items.filter((i) => !asked.has(i));
  if (!left.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {left.map((s) => (
        <button key={s} type="button" className="btn btn-s btn-soft" disabled={pending} onClick={() => ask(s, topic)}>
          {s}
        </button>
      ))}
    </div>
  );
}
