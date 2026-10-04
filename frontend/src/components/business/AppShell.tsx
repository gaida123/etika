"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Logo, LogoMark } from "@/components/ui";
import { AREAS, confirmedFactCount, kindOf } from "@/lib/assessment";
import { useBusiness } from "./BusinessProvider";
import { type CheckRun, CheckProgress, LaneStatus, useCheckRun } from "./CheckProgress";
import { AreaIcon } from "./icons";

export function AppShell({ children }: { children: ReactNode }) {
  const { businessId, phase, assessment, isDemo, closeCheck } = useBusiness();
  const run = useCheckRun();
  const router = useRouter();
  const path = usePathname();
  // Once the check is ready, any navigation leaves the check screen for the page asked for.
  const leaveCheck = run?.ready ? closeCheck : undefined;

  return (
    <div className="shell">
      <AppSidebar run={run} onNavigate={leaveCheck} />
      <div className="content">
        {isDemo && (
          <div className="border-b border-line bg-brand-tint px-5 py-2.5 text-sm text-brand" role="note">
            Sample data for previewing the design. Nothing here comes from the backend or official sources.
          </div>
        )}
        {run ? (
          <CheckProgress
            run={run}
            onDone={() => {
              closeCheck();
              window.scrollTo({ top: 0 });
              if (path !== `/b/${businessId}`) router.push(`/b/${businessId}`);
            }}
          />
        ) : assessment ? (
          children
        ) : phase === "error" ? (
          <ErrorState />
        ) : (
          <LoadingState />
        )}
      </div>
    </div>
  );
}

function AppSidebar({ run, onNavigate }: { run: CheckRun | null; onNavigate?: () => void }) {
  const { businessId, profile, rows, marks, questions } = useBusiness();
  const path = usePathname();
  const base = `/b/${businessId}`;
  const showCount = !run || run.ready;
  const name = profile?.trading_name || profile?.legal_name || "Your business";

  return (
    <aside className="side gap-[26px]" aria-label="Sidebar">
      <Logo href={base} />

      <nav aria-label="Your check">
        <div className="navh">Your check</div>
        <NavLink href={base} current={run ? true : path === base} icon={<GridIcon />} onClick={onNavigate}>
          Overview
        </NavLink>
        <NavLink
          href={`${base}#input`}
          icon={<QuestionIcon />}
          count={(showCount && questions.length) || undefined}
          onClick={onNavigate}
        >
          Needs your input
        </NavLink>
        <NavLink
          href={`${base}/ask`}
          current={!run && path === `${base}/ask`}
          icon={<LogoMark size={18} />}
          onClick={onNavigate}
        >
          Ask etika
        </NavLink>
      </nav>

      {run ? (
        <nav aria-label="Categories">
          <div className="navh">Categories</div>
          {run.lanes.map((l) => (
            <NavLink
              key={l.area}
              href={`${base}#area-${l.area}`}
              icon={<AreaIcon area={l.area} />}
              status={<LaneStatus lane={l} />}
              onClick={onNavigate}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      ) : rows.length > 0 && (
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
                icon={<AreaIcon area={a.id} />}
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
        <NavLink href={`${base}#coverage`} icon={<CoverageIcon />} onClick={onNavigate}>
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
  status,
  onClick,
  children,
}: {
  href: string;
  current?: boolean;
  icon: ReactNode;
  count?: string | number;
  status?: ReactNode;
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <Link
      href={href}
      className={`nav ${current ? "nav-on" : ""}`}
      aria-current={current ? "page" : undefined}
      onClick={onClick}
    >
      <span className="flex-none">{icon}</span>
      {children}
      {status ?? (count !== undefined && <span className="count">{count}</span>)}
    </Link>
  );
}

function LoadingState() {
  return (
    <div className="inner">
      <div className="muted flex items-center gap-2.5 text-sm" role="status" aria-busy="true">
        <span className="ck-spin" aria-hidden="true" />
        Loading your business…
      </div>
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
