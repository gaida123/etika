"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { CheckIcon, Logo, LogoMark } from "@/components/ui";
import { AREAS, confirmedFactCount, kindOf } from "@/lib/assessment";
import { useBusiness } from "./BusinessProvider";

export function AppShell({ children }: { children: ReactNode }) {
  const { phase, assessment, isDemo } = useBusiness();
  return (
    <div className="shell">
      <AppSidebar />
      <div className="content">
        {isDemo && (
          <div className="border-b border-line bg-brand-tint px-5 py-2.5 text-sm text-brand" role="note">
            Sample data for previewing the design. Nothing here comes from the backend or official sources.
          </div>
        )}
        {assessment ? children : phase === "error" ? <ErrorState /> : <LoadingState />}
      </div>
    </div>
  );
}

function AppSidebar() {
  const { businessId, profile, rows, marks, questions } = useBusiness();
  const path = usePathname();
  const base = `/b/${businessId}`;
  const name = profile?.trading_name || profile?.legal_name || "Your business";

  return (
    <aside className="side gap-[26px]" aria-label="Sidebar">
      <Logo href={base} />

      <nav aria-label="Your check">
        <div className="navh">Your check</div>
        <NavLink href={base} current={path === base} icon={<GridIcon />}>
          Overview
        </NavLink>
        <NavLink href={`${base}#input`} icon={<QuestionIcon />} count={questions.length || undefined}>
          Needs your input
        </NavLink>
        <NavLink href={`${base}/ask`} current={path === `${base}/ask`} icon={<LogoMark size={18} />}>
          Ask etika
        </NavLink>
      </nav>

      {rows.length > 0 && (
        <nav aria-label="Categories">
          <div className="navh">Categories</div>
          {AREAS.map((a) => {
            const areaRows = rows.filter((r) => r.area === a.id);
            const applicable = areaRows.filter((r) => r.bucket === "now");
            const done = areaRows.filter((r) => kindOf(r, marks) === "done").length;
            return (
              <NavLink
                key={a.id}
                href={`${base}#area-${a.id}`}
                icon={AREA_ICONS[a.id]}
                count={applicable.length ? `${done}/${applicable.length}` : undefined}
              >
                {a.label}
              </NavLink>
            );
          })}
        </nav>
      )}

      <nav aria-label="Business">
        <div className="navh">Business</div>
        <NavLink href={`${base}#coverage`} icon={<CoverageIcon />}>
          What we cover
        </NavLink>
        <NavLink href="/" icon={<PlusIcon />}>
          Start a new check
        </NavLink>
      </nav>

      <div className="mt-auto flex flex-col gap-4">
        <p className="muted m-0 px-2.5 text-[13px]">etika shows requirements that may apply. It isn&apos;t legal advice.</p>
        <div className="border-t border-opt pt-3">
          <div className="flex min-h-12 items-center gap-2.5 px-2.5 py-1.5">
            <span className="inline-flex size-8 flex-none items-center justify-center rounded-full bg-brand font-medium text-white">
              {name.trim().charAt(0).toUpperCase()}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{name}</span>
              {profile && (
                <span className="muted block text-xs">
                  Version {profile.profile_version}, {confirmedFactCount(profile)} confirmed facts
                </span>
              )}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
}

function NavLink({
  href,
  current,
  icon,
  count,
  children,
}: {
  href: string;
  current?: boolean;
  icon: ReactNode;
  count?: string | number;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={`nav ${current ? "nav-on" : ""}`} aria-current={current ? "page" : undefined}>
      <span className="flex-none">{icon}</span>
      {children}
      {count !== undefined && <span className="count">{count}</span>}
    </Link>
  );
}

function LoadingState() {
  const { profile, phase } = useBusiness();
  const name = profile?.trading_name || "your business";
  return (
    <div className="inner">
      <section className="box flex max-w-[520px] flex-col gap-3.5 p-6" aria-busy="true" aria-labelledby="l-h">
        <div className="tag">Loading</div>
        <h1 id="l-h" className="m-0 text-xl leading-tight font-medium tracking-[-0.015em]">
          Checking {name}…
        </h1>
        <Step state={profile ? "done" : "active"}>
          {profile ? `Reading your ${confirmedFactCount(profile)} confirmed facts` : "Reading your business profile"}
        </Step>
        <Step state={phase === "assessing" ? "active" : "todo"}>Matching against requirements</Step>
        <Step state={phase === "assessing" ? "active" : "todo"}>Pulling official sources</Step>
        <div className="mt-2 flex flex-col gap-2">
          <div className="sk w-[90%]" />
          <div className="sk w-[70%]" />
          <div className="sk w-[80%]" />
        </div>
        <span className="muted text-[13px]">Usually under 20 seconds.</span>
      </section>
    </div>
  );
}

function Step({ state, children }: { state: "done" | "active" | "todo"; children: ReactNode }) {
  if (state === "done")
    return (
      <div className="flex items-center gap-2.5 text-sm text-brand">
        <CheckIcon size={18} />
        {children}
      </div>
    );
  return (
    <div className={`flex items-center gap-2.5 text-sm ${state === "active" ? "font-medium" : "muted"}`}>
      {state === "active" ? (
        <span className="spin" />
      ) : (
        <span className="mx-0.5 inline-block size-3.5 rounded-full border-2 border-opt" />
      )}
      {children}
    </div>
  );
}

function ErrorState() {
  const { error, retry } = useBusiness();
  return (
    <div className="inner">
      <section className="box flex max-w-[520px] flex-col gap-3.5 p-6" aria-labelledby="e-h" role="alert">
        <div className="tag">Error</div>
        <h1 id="e-h" className="m-0 text-xl leading-tight font-medium tracking-[-0.015em]">
          We couldn&apos;t finish your check
        </h1>
        <p className="m-0 text-sm">{error} Your answers are saved and nothing was lost.</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn btn-p" onClick={retry}>
            Try again
          </button>
          <Link href="/" className="btn border-step-off">
            Start a new check
          </Link>
        </div>
      </section>
    </div>
  );
}

const icon = (d: ReactNode, extra?: object) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true" {...extra}>
    {d}
  </svg>
);
const GridIcon = () => icon(<path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" />);
const QuestionIcon = () =>
  icon(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.7M12 17h.01" />
    </>,
  );
const CoverageIcon = () => icon(<circle cx="12" cy="12" r="9" />, { strokeDasharray: "3 3" });
const PlusIcon = () => icon(<path d="M12 5v14M5 12h14" />);
const AREA_ICONS = {
  registration: icon(<path d="M6 3h9l4 4v14H6zM14 3v5h5" />),
  tax: icon(<path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2zM9 8h6M9 12h6M9 16h3" />),
  employer: icon(
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3 3-5 6-5s6 2 6 5M16 5a3 3 0 0 1 0 6M18 15c2 .6 3 2.3 3 5" />
    </>,
  ),
};
