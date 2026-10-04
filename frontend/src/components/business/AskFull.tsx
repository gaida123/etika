"use client";

// Wireframe 04b, Ask etika full view.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { LogoMark } from "@/components/ui";
import { isRealUrl, kindOf, priorityPill, statusText } from "@/lib/assessment";
import { useBusiness } from "./BusinessProvider";
import { ChatThread, Composer, SUGGESTIONS_GENERAL, SUGGESTIONS_TOPIC, Suggestions, conversationSources } from "./Chat";

export function AskFull({ topic }: { topic: string | null }) {
  const { businessId, rows, turns, marks } = useBusiness();
  const router = useRouter();
  const base = `/b/${businessId}`;
  const topicRow = topic ? rows.find((r) => r.requirement_id === topic) : undefined;
  const sources = conversationSources(turns);
  const related = topicRow
    ? rows.filter((r) => r.area === topicRow.area)
    : rows.filter((r) => kindOf(r, marks) === "action").slice(0, 4);

  // Keep the newest message in view while the reader is at the bottom. Answers fade in and grow
  // after the turn updates, so follow the content's size, not just the turn list. Scrolling up to
  // reread stops the follow; asking a new question resumes it.
  const threadRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  useEffect(() => {
    const el = threadRef.current;
    const content = contentRef.current;
    if (!el || !content) return;
    const onScroll = () => {
      follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    };
    const observer = new ResizeObserver(() => {
      if (follow.current) el.scrollTop = el.scrollHeight;
    });
    el.addEventListener("scroll", onScroll, { passive: true });
    observer.observe(content);
    return () => {
      el.removeEventListener("scroll", onScroll);
      observer.disconnect();
    };
  }, []);
  useEffect(() => {
    follow.current = true;
  }, [turns.length]);

  // On wide screens the page is a window-height frame: the conversation scrolls inside it and the
  // composer stays pinned at the bottom. Narrow screens scroll normally with a sticky composer.
  return (
    <div className="flex min-h-screen flex-col lg:min-h-0 lg:flex-1 lg:overflow-hidden">
      <header className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-3 border-b border-line-soft px-8 py-5 max-[720px]:px-4">
        <div className="min-w-0 flex-[1_1_320px]">
          <h1 className="m-0 text-[28px] leading-[1.15] font-medium tracking-[-0.03em]">Ask etika</h1>
          <p className="muted mt-1 mb-0 text-sm">Answers use only the official sources we hold. Not legal advice.</p>
        </div>
        {topicRow && (
          <>
            <span className="inline-flex min-h-9 items-center gap-2 rounded-[3px] bg-brand-tint py-0 pr-1.5 pl-3 text-sm text-brand">
              About: {topicRow.title}
              <button
                type="button"
                aria-label="Clear topic and ask about anything"
                className="inline-flex size-7 cursor-pointer items-center justify-center rounded-[3px] border-0 bg-transparent text-inherit"
                onClick={() => router.replace(`${base}/ask`)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </span>
            <Link href={`${base}/r/${topicRow.requirement_id}`} className="btn btn-s btn-soft">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
                <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
              </svg>
              Back to requirement
            </Link>
          </>
        )}
      </header>

      <div className="flex flex-1 flex-wrap items-stretch lg:min-h-0 lg:flex-nowrap">
        <main className="flex min-w-0 flex-[999_1_520px] flex-col lg:min-h-0">
          <div ref={threadRef} className="flex-1 lg:min-h-0 lg:overflow-y-auto">
            <div ref={contentRef} className="mx-auto flex w-full max-w-[780px] flex-col gap-6 px-8 pt-8 pb-6 max-[720px]:px-4">
              {turns.length === 0 && (
                <div className="flex items-start gap-3">
                  <LogoMark size={20} className="mt-[3px]" />
                  <p className="m-0">
                    Ask about registering, tax or hiring for your business. Every answer cites the official source it
                    came from, and if we can&apos;t find one we&apos;ll say so.
                  </p>
                </div>
              )}
              <ChatThread turns={turns} variant="full" />
            </div>
          </div>

          <div className="sticky bottom-0 shrink-0 border-t border-line-soft bg-white lg:static">
            <div className="mx-auto flex w-full max-w-[780px] flex-col gap-3 px-8 pt-4 pb-6 max-[720px]:px-4">
              <Suggestions items={topicRow ? SUGGESTIONS_TOPIC : SUGGESTIONS_GENERAL} topic={topicRow ? topic : null} />
              <Composer
                topic={topicRow ? topic : null}
                variant="full"
                placeholder={
                  topicRow
                    ? "Ask about this requirement, or clear the topic to ask about anything…"
                    : "Ask about your business…"
                }
              />
            </div>
          </div>
        </main>

        <aside
          aria-labelledby="src-h"
          className="flex min-w-0 flex-[1_1_280px] flex-col gap-6 border-l border-line-soft bg-panel px-6 pb-7 lg:max-w-[380px] lg:overflow-y-auto"
        >
          <section className="flex flex-col gap-2.5">
            <h2 id="src-h" className="sticky top-0 z-10 m-0 flex items-baseline justify-between bg-panel pt-7 pb-1 text-base font-medium">
              Sources in this conversation
              {sources.length > 0 && <span className="muted text-[13px] font-normal">{sources.length}</span>}
            </h2>
            {sources.length === 0 ? (
              <p className="muted m-0 text-[13px]">Sources cited in answers show up here.</p>
            ) : (
              sources.map((s) => (
                <div key={s.n} id={`s${s.n}`} className="box src scroll-mt-6">
                  <span className="muted text-xs">Source {s.n}</span>
                  <span className="text-sm font-medium">{s.title}</span>
                  {isRealUrl(s.url) ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-[13px] underline-offset-[3px]">
                      Open official source ↗
                    </a>
                  ) : (
                    <span className="muted text-[13px]">Official link not added yet</span>
                  )}
                </div>
              ))
            )}
          </section>
          {related.length > 0 && (
            <section className="flex flex-col gap-2.5">
              <h2 className="sticky top-0 z-10 m-0 bg-panel pt-3 pb-1 text-base font-medium">
                {topicRow ? "Related requirements" : "Your open requirements"}
              </h2>
              {related.map((r) => {
                const kind = kindOf(r, marks);
                const pri = priorityPill(r, kind);
                return (
                  <Link key={r.requirement_id} href={`${base}/r/${r.requirement_id}`} className="box src">
                    <span className="text-sm font-medium">{r.title}</span>
                    <span className="muted text-[13px]">
                      {pri ? `${pri.label}, ${statusText(r, kind, marks).toLowerCase()}` : statusText(r, kind, marks)}
                    </span>
                  </Link>
                );
              })}
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
