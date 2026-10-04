"use client";

// Wireframe 04a, Finding, action and grounded chat.

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckIcon, LogoMark } from "@/components/ui";
import { ApiError, type RequirementDetail } from "@/lib/api";
import {
  type Progress,
  appliesPill,
  areaLabel,
  detailLine,
  isRealUrl,
  kindOf,
  priorityPill,
  progressOf,
  shortDate,
} from "@/lib/assessment";
import { factField, factText } from "@/lib/facts";
import { useStored } from "@/lib/stored";
import { useBusiness } from "./BusinessProvider";
import { ChatThread, Composer, SUGGESTIONS_TOPIC, Suggestions } from "./Chat";

const PROGRESS: { value: Progress; label: string }[] = [
  { value: "todo", label: "To do" },
  { value: "in_progress", label: "In progress" },
  { value: "done", label: "Done" },
];

export function FindingView({ requirementId }: { requirementId: string }) {
  const { backend, businessId, rows, marks, setMark, profile, assessment } = useBusiness();
  const [detail, setDetail] = useState<RequirementDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [ticked, setTicked] = useStored<string[]>(`etika:prep:${businessId}:${requirementId}`, []);
  const base = `/b/${businessId}`;
  const row = rows.find((r) => r.requirement_id === requirementId);

  useEffect(() => {
    let cancelled = false;
    backend.getRequirement(requirementId).then(
      (d) => !cancelled && setDetail(d),
      (e) => !cancelled && setDetailError(e instanceof ApiError ? e.message : "Couldn't load the official source."),
    );
    return () => {
      cancelled = true;
    };
  }, [backend, requirementId]);

  if (!row || !profile || !assessment)
    return (
      <main className="inner flex flex-col gap-4">
        <h1 className="hxl">We couldn&apos;t find that requirement.</h1>
        <Link href={base} className="btn btn-soft self-start">
          Back to overview
        </Link>
      </main>
    );

  const kind = kindOf(row, marks);
  const applies = appliesPill(row, kind);
  const priority = priorityPill(row, kind);
  const finding = assessment.findings.find((f) => f.requirement_id === requirementId);
  const flags = finding?.flags ?? [];
  const req = detail?.requirement;
  const factKeys = req?.required_fact_keys ?? [];
  const revenueMonths = profile.monthly_revenue?.length ?? 0;
  const factValue = (k: string) => (k === "monthly_revenue" ? revenueMonths : profile.facts[k]?.value);
  const known = factKeys.filter((k) =>
    k === "monthly_revenue" ? revenueMonths > 0 : profile.facts[k]?.confirmed && profile.facts[k]?.value != null,
  );
  const missing = [...new Set([...row.missing_facts, ...factKeys.filter((k) => !known.includes(k))])];
  const prep = req?.preparation_items ?? [];
  const verified = shortDate(req?.last_verified_at);
  const actionUrl = row.action_url ?? req?.action_url;
  const chunks = detail?.evidence.status === "supported" ? detail.evidence.chunks.slice(0, 2) : [];
  const detailText = detailLine(row);

  return (
    <div className="max-w-[1160px] px-12 pt-10 pb-20 max-[720px]:px-4">
      <nav aria-label="Breadcrumb" className="mb-5 text-sm">
        <Link href={base} className="text-ink underline-offset-[3px]">
          Overview
        </Link>{" "}
        <span className="muted">/ {areaLabel(row.area)} /</span> {row.title}
      </nav>

      <div className="flex flex-wrap items-start gap-8">
        <main className="flex min-w-0 flex-[999_1_520px] flex-col gap-8">
          <div className="flex flex-col gap-3.5">
            <h1 className="m-0 text-[44px] leading-[1.08] font-medium tracking-[-0.035em] max-[720px]:text-[32px]">
              {row.title}.
            </h1>
            <div className="flex flex-wrap gap-2">
              <span className={applies.className}>{applies.label}</span>
              {priority && <span className={priority.className}>{priority.label}</span>}
              <span className="pill pill-mute">{areaLabel(row.area)}</span>
            </div>
            {row.explanation && <p className="m-0 max-w-[640px] text-[17px]">{row.explanation}</p>}
          </div>

          {row.bucket === "now" ? (
            <fieldset className="box flex flex-wrap items-center gap-x-5 gap-y-3 px-5 py-4">
              <legend className="float-left flex-[1_1_140px] font-medium">Your progress</legend>
              <div className="inline-flex overflow-hidden rounded-[3px] border border-ink">
                {PROGRESS.map((p) => (
                  <label key={p.value} className="seg">
                    <input
                      type="radio"
                      name="progress"
                      className="sr-only"
                      checked={progressOf(row, marks) === p.value}
                      onChange={() => setMark(requirementId, p.value)}
                    />
                    {p.label}
                  </label>
                ))}
              </div>
              <span className="muted basis-full text-[13px]">
                Marking Done is your call. etika doesn&apos;t verify it with the authority. Saved in this browser.
              </span>
            </fieldset>
          ) : (
            <div className="box flex flex-col gap-2 px-5 py-4">
              <span className="font-medium">Not required yet</span>
              {detailText && <span className="muted text-sm">{detailText}.</span>}
              {row.progress && (
                <div
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={row.progress.threshold}
                  aria-valuenow={row.progress.current}
                  aria-label="Sales toward the threshold"
                  className="h-1.5 overflow-hidden rounded-[3px] bg-line-soft"
                >
                  <div
                    className="h-full bg-brand"
                    style={{ width: `${Math.min(100, (100 * row.progress.current) / row.progress.threshold)}%` }}
                  />
                </div>
              )}
              {row.progress?.estimated_crossing && (
                <span className="muted text-[13px]">The crossing month is an estimate from your recent sales.</span>
              )}
            </div>
          )}

          <section aria-labelledby="why-h">
            <h2 id="why-h" className="h2-f">
              Why this showed up
            </h2>
            {!detail && !detailError ? (
              <div className="sk w-1/2" />
            ) : (
              <>
                <p className="muted mt-0 mb-2.5 text-sm">
                  {known.length === factKeys.length
                    ? factKeys.length === 1
                      ? "The condition is met by a fact you confirmed:"
                      : `All ${factKeys.length} conditions are checked against facts you confirmed:`
                    : `Based on ${known.length} of ${factKeys.length} facts it needs:`}
                </p>
                <div className="flex flex-wrap gap-2">
                  {known.map((k) => (
                    <span key={k} className="fact">
                      <CheckIcon size={14} />
                      {factText(k, factValue(k))}
                    </span>
                  ))}
                  {factKeys
                    .filter((k) => !known.includes(k))
                    .map((k) => (
                      <a key={k} href={`${base}#input`} className="pill pill-dash h-8 px-3 font-normal text-ink no-underline">
                        Needs your input: {factField(k)}
                      </a>
                    ))}
                </div>
              </>
            )}
          </section>

          <section aria-labelledby="src-h">
            <h2 id="src-h" className="h2-f">
              What the official source says
            </h2>
            {detailError ? (
              <p className="muted m-0 text-sm">{detailError}</p>
            ) : !detail ? (
              <div className="box flex flex-col gap-2 bg-panel p-5">
                <div className="sk w-[96%]" />
                <div className="sk w-[88%]" />
                <div className="sk w-[62%]" />
              </div>
            ) : chunks.length === 0 ? (
              <div className="box bg-panel p-5 text-sm">
                We couldn&apos;t find an official source for this. Check with the authority or a professional before
                relying on it.
              </div>
            ) : (
              chunks.map((c) => (
                <figure key={c.chunk_id} className="box m-0 mb-3 flex flex-col gap-3.5 bg-panel p-5">
                  <blockquote className="m-0 border-l-2 border-brand pl-4">{c.text}</blockquote>
                  <figcaption className="flex flex-wrap justify-between gap-2 text-sm">
                    <span>
                      <strong className="font-medium">{c.title}</strong>
                      {c.section_path && `, ${c.section_path}`}
                    </span>
                    <span className="muted">
                      {verified ? `Last verified ${verified}` : "Not yet verified"}
                      {isRealUrl(c.url) && (
                        <>
                          {"   "}
                          <a href={c.url} target="_blank" rel="noreferrer" className="underline-offset-[3px]">
                            Open official source ↗
                          </a>
                        </>
                      )}
                    </span>
                  </figcaption>
                </figure>
              ))
            )}
          </section>

          <section aria-labelledby="step-h" className="box callout flex flex-col gap-3.5 p-6">
            <span className="text-sm font-medium text-brand">Your next step</span>
            <h2 id="step-h" className="m-0 text-2xl font-medium tracking-[-0.02em]">
              {row.bucket === "now" ? "Start on the official site" : "Get ready before it applies"}
            </h2>
            <div className="flex flex-wrap gap-2.5">
              {isRealUrl(actionUrl) ? (
                <a href={actionUrl} target="_blank" rel="noreferrer" className="btn btn-p">
                  Open official page ↗
                </a>
              ) : (
                <button type="button" className="btn btn-p" disabled>
                  Official link coming soon
                </button>
              )}
              <a href="#chat" className="btn border-step-off">
                Ask about this
              </a>
            </div>
            <span className="muted text-[13px]">
              {verified ? `Link verified ${verified}. ` : ""}Opens the official site. etika doesn&apos;t submit anything
              for you.
            </span>
          </section>

          {prep.length > 0 && (
            <section aria-labelledby="cl-h">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="cl-h" className="h2-f">
                  Get ready to apply
                </h2>
                <span className="muted text-sm">
                  {ticked.filter((t) => prep.includes(t)).length} of {prep.length} ready
                </span>
              </div>
              <div>
                {prep.map((item) => (
                  <label key={item} className="check">
                    <input
                      type="checkbox"
                      className="mt-0.5 size-[18px]"
                      checked={ticked.includes(item)}
                      onChange={(e) => setTicked(e.target.checked ? [...ticked, item] : ticked.filter((t) => t !== item))}
                    />
                    <span className="font-medium">{item}</span>
                  </label>
                ))}
              </div>
            </section>
          )}

          <section aria-labelledby="lim-h" className="box bg-side px-5 py-[18px]">
            <h2 id="lim-h" className="mt-0 mb-1 text-[15px] font-medium">
              Limits of this finding
            </h2>
            <p className="m-0 text-sm">
              Covers whether this may be required of you. It doesn&apos;t review fees, processing times or your
              paperwork. Missing information:{" "}
              {missing.length ? missing.map(factField).join(", ") : "none for this requirement"}.
            </p>
            {(flags.length > 0 || (req?.review_flags.length ?? 0) > 0) && (
              <p className="mt-2 mb-0 text-sm">
                Flagged for review: {[...flags, ...(req?.review_flags ?? [])].map((f) => f.replace(/\.$/, "")).join("; ")}.
                These are gray areas, so
                check with the authority or a professional.
              </p>
            )}
          </section>
        </main>

        <ChatPanel requirementId={requirementId} />
      </div>
    </div>
  );
}

function ChatPanel({ requirementId }: { requirementId: string }) {
  const { businessId, turns } = useBusiness();
  const mine = turns.filter((t) => t.topic === requirementId);

  return (
    <aside
      id="chat"
      aria-labelledby="chat-h"
      className="box sticky top-6 flex max-h-[calc(100vh-48px)] min-w-0 flex-[1_1_340px] flex-col overflow-hidden"
    >
      <div className="flex items-start gap-2.5 border-b border-line-soft px-5 py-4">
        <LogoMark className="mt-[3px]" />
        <div className="min-w-0 flex-1">
          <h2 id="chat-h" className="m-0 text-base font-medium">
            Ask about this requirement
          </h2>
          <p className="muted mt-0.5 mb-0 text-[13px]">Answers use only the official sources we hold. Not legal advice.</p>
        </div>
        <Link
          href={`/b/${businessId}/ask?topic=${requirementId}`}
          aria-label="Open full view"
          title="Open full view"
          className="btn btn-s btn-soft w-9 flex-none p-0"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" />
          </svg>
        </Link>
      </div>
      <div className="flex flex-col gap-4 overflow-y-auto p-5">
        {mine.length === 0 && (
          <p className="muted m-0 text-sm">Ask anything about this requirement. Answers cite the official source.</p>
        )}
        <ChatThread turns={mine} variant="panel" />
        <Suggestions items={SUGGESTIONS_TOPIC} topic={requirementId} />
      </div>
      <Composer topic={requirementId} placeholder="Ask about this requirement…" variant="panel" />
    </aside>
  );
}
