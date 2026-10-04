"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from "react";
import "./landing.css";

// Ported from "etika Landing Page.html". The desktop, tablet and phone frames of that design share
// one DOM here; landing.css switches between them at 1000px and 600px.

const CHECK_HREF = "/check";
const MARK = "M12 1v22M1 12h22M4.2 4.2l15.6 15.6M19.8 4.2 4.2 19.8";
const TICK = "M3 8.5 6.5 12 13 4";
const TABS = ["assess", "act", "ask"] as const;
type Tab = (typeof TABS)[number];
type Sales = "yes" | "no" | "unsure";
type LaneState = "wait" | "work" | "done";

const FLOW_LANES = [
  { key: "lic", area: "Licensing & permits", icon: "M6 3h9l4 4v14H6zM14 3v5h5", step: 4, states: ["wait", "done", "done", "done"] },
  {
    key: "food",
    area: "Food safety",
    icon: "M7 3v8a2 2 0 0 0 2 2v8M5 3v5M9 3v5M16 21V3c2 1 3 3 3 6s-1 4-3 4",
    step: 2,
    states: ["wait", "work", "done", "done"],
  },
  {
    key: "emp",
    area: "Employer & tax",
    icon: "M6 8a3 3 0 1 0 6 0a3 3 0 1 0-6 0M3 20c0-3 3-5 6-5s6 2 6 5M16 5a3 3 0 0 1 0 6M18 15c2 .6 3 2.3 3 5",
    step: 1,
    states: ["wait", "work", "done", "done"],
  },
] as const;

function Mark({ size, width = 2.4, stroke = "currentColor" }: { size: number; width?: number; stroke?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={width} aria-hidden="true">
      <path d={MARK} />
    </svg>
  );
}

function Tick({ size = 14, width = 2.2, stroke = "#2C4A21" }: { size?: number; width?: number; stroke?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={stroke} strokeWidth={width} aria-hidden="true">
      <path d={TICK} />
    </svg>
  );
}

function Noise({ id, frequency, className }: { id: string; frequency: number; className: string }) {
  return (
    <svg aria-hidden="true" className={className}>
      <filter id={id}>
        <feTurbulence type="fractalNoise" baseFrequency={frequency} numOctaves={3} stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter={`url(#${id})`} />
    </svg>
  );
}

function Dots({ color }: { color: string }) {
  return (
    <span aria-hidden="true" className="l-dots">
      <span style={{ background: color }} />
      <span style={{ background: color }} />
      <span style={{ background: color }} />
    </span>
  );
}

function CheckRow({ n, children }: { n: 1 | 2 | 3; children: React.ReactNode }) {
  return (
    <div className={`l-xr l-xr${n}`}>
      <span className="l-xi" aria-hidden="true">
        <span className="l-xsp" />
        <svg className="l-xc" width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#2C4A21" strokeWidth="1.8">
          <path d={TICK} />
        </svg>
      </span>
      {children}
    </div>
  );
}

function Seg({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className={`l-seg${on ? " on" : ""}`} aria-pressed={on} onClick={onClick}>
      {children}
    </button>
  );
}

/** The 3D etika asterisk: four extruded bars that float and follow the pointer. */
function MarkScene({ onTurn, spins }: { onTurn: () => void; spins: number }) {
  const [tilt, setTilt] = useState({ rx: -6, ry: 14 });
  function onMove(e: MouseEvent<HTMLButtonElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    setTilt({ rx: Math.round(-y * 34), ry: Math.round(x * 46) });
  }
  return (
    <div className="l-markbox">
      <button
        type="button"
        className="l-mark"
        aria-label="Tilt and turn the etika mark"
        onClick={onTurn}
        onMouseMove={onMove}
        onMouseLeave={() => setTilt({ rx: -6, ry: 14 })}
      >
        <div aria-hidden="true" className="l-markglow" />
        <div
          aria-hidden="true"
          className="l-scene"
          style={{ transform: `rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg) rotateZ(${spins * 45}deg)` }}
        >
          <div className="l-float">
            {[0, 45, 90, 135].map((a) => (
              <div key={a} className="l-bar" style={{ transform: `rotateZ(${a}deg)` }}>
                <div className="l-face" style={{ left: 0, top: 0, width: 320, height: 60, background: "linear-gradient(180deg,#FBFBF8,#E7E7E1)", transform: "translateZ(36px)" }} />
                <div className="l-face" style={{ left: 0, top: 0, width: 320, height: 60, background: "#D8D9D1", transform: "rotateY(180deg) translateZ(36px)" }} />
                <div className="l-face" style={{ left: 0, top: -6, width: 320, height: 72, background: "#FFFFFF", transform: "rotateX(90deg) translateZ(30px)" }} />
                <div className="l-face" style={{ left: 0, top: -6, width: 320, height: 72, background: "#B5B7AC", transform: "rotateX(-90deg) translateZ(30px)" }} />
                <div className="l-face" style={{ left: 124, top: 0, width: 72, height: 60, background: "#CBCDC4", transform: "rotateY(90deg) translateZ(160px)" }} />
                <div className="l-face" style={{ left: 124, top: 0, width: 72, height: 60, background: "#C1C3B9", transform: "rotateY(-90deg) translateZ(160px)" }} />
              </div>
            ))}
          </div>
        </div>
      </button>
    </div>
  );
}

/** On wide screens the green stage pins and grows to full bleed as you scroll, ticking off the card's rows. */
function useStageScroll() {
  useEffect(() => {
    const root = document.documentElement;
    let raf = 0;
    const tick = () => {
      raf = 0;
      const track = document.querySelector(".l-xtrack");
      if (!track) return;
      const vh = Math.min(window.innerHeight, window.screen?.availHeight || window.innerHeight);
      const live = window.innerHeight < 2200 && window.innerWidth >= 1000;
      root.classList.toggle("x-live", live);
      if (!live) {
        root.style.removeProperty("--xp");
        root.style.removeProperty("--xvh");
        root.classList.remove("x-s1", "x-s2", "x-s3");
        return;
      }
      root.style.setProperty("--xvh", vh + "px");
      const r = track.getBoundingClientRect();
      const start = vh * 0.45;
      const span = start + (vh * 0.25 + 560) * 0.75;
      let p = Math.max(0, Math.min(1, (start - r.top) / span));
      p = p * p * (3 - 2 * p);
      root.style.setProperty("--xp", p.toFixed(4));
      root.classList.toggle("x-s1", p >= 0.12);
      root.classList.toggle("x-s2", p >= 0.45);
      root.classList.toggle("x-s3", p >= 0.8);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(tick);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    tick();
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
      root.classList.remove("x-live", "x-s1", "x-s2", "x-s3");
      root.style.removeProperty("--xp");
      root.style.removeProperty("--xvh");
    };
  }, []);
}

function Preview({ food, staff, sales }: { food: boolean; staff: boolean; sales: Sales }) {
  const [tab, setTab] = useState<Tab>("assess");
  const dragEnd = useRef(0);

  const reqs = [{ name: "City business licence", src: "City of Vancouver", st: "May apply", cls: "may" }];
  if (food) {
    reqs.push({ name: "Health permit to operate a food premises", src: "Vancouver Coastal Health", st: "May apply", cls: "may" });
    reqs.push({ name: "Food safety and sanitation plans", src: "Vancouver Coastal Health", st: "May apply", cls: "may" });
    reqs.push({ name: "FOODSAFE Level 1 certification", src: "BC food premises rules", st: "May apply", cls: "may" });
  }
  if (staff) {
    reqs.push({ name: "WorkSafeBC employer registration", src: "WorkSafeBC", st: "May apply", cls: "may" });
    reqs.push({ name: "CRA payroll program account", src: "Canada Revenue Agency", st: "May apply", cls: "may" });
    reqs.push({ name: "Employment Standards payroll records", src: "BC Employment Standards", st: "May apply", cls: "may" });
  }
  if (sales === "yes") reqs.push({ name: "GST/HST registration", src: "Canada Revenue Agency", st: "May apply", cls: "may" });
  else if (sales === "unsure") reqs.push({ name: "GST/HST registration", src: "Canada Revenue Agency", st: "Needs your input", cls: "ask" });
  const may = reqs.filter((r) => r.cls === "may").length;
  const ask = reqs.length - may;
  const nextSteps = food
    ? ["Floor plan of the food preparation area", "Menu", "Food safety plan", "Sanitation plan"]
    : ["Business name and address", "Description of your business", "Zoning confirmation for the location"];

  function show(t: Tab) {
    if (Date.now() - dragEnd.current < 350) return;
    setTab(t);
  }

  // Drag the white indicator between tabs; it squashes slightly with speed and snaps on release.
  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (e.button !== 0) return;
    const list = e.currentTarget;
    const ind = list.querySelector<HTMLElement>(".l-tabind");
    if (!ind) return;
    const cur = TABS.indexOf(tab);
    const r = list.getBoundingClientRect();
    const w = (r.width - 8) / 3;
    const startX = e.clientX;
    const rel = startX - (r.left + 4 + cur * w);
    if (rel < 0 || rel > w) return;
    let moved = false;
    let last = startX;
    let vel = 0;
    const pos = (cx: number) => Math.max(0, Math.min(2 * w, cur * w + (cx - startX)));
    const mv = (ev: globalThis.PointerEvent) => {
      if (!moved && Math.abs(ev.clientX - startX) < 4) return;
      moved = true;
      vel = ev.clientX - last;
      last = ev.clientX;
      const st = Math.min(0.03, Math.abs(vel) / 400);
      ind.classList.add("drag");
      ind.style.transition = "transform .12s ease-out, box-shadow .25s ease";
      const sx = 1 + st;
      const m = (w * (sx - 1)) / 2;
      const px = Math.max(m, Math.min(2 * w - m, pos(ev.clientX)));
      ind.style.transform = `translateX(${px}px) scale(${sx},${0.94 - st})`;
    };
    const up = (ev: globalThis.PointerEvent) => {
      window.removeEventListener("pointermove", mv);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      if (!moved) return;
      const x = pos(ev.clientX === undefined ? last : ev.clientX) + vel * 4;
      const idx = Math.max(0, Math.min(2, Math.round(x / w)));
      ind.classList.remove("drag");
      ind.style.transition = "";
      ind.style.transform = `translateX(${idx * 100}%)`;
      dragEnd.current = Date.now();
      setTab(TABS[idx]);
    };
    window.addEventListener("pointermove", mv);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  }

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    const i = TABS.indexOf(tab);
    if (e.key === "ArrowRight") {
      e.preventDefault();
      setTab(TABS[Math.min(2, i + 1)]);
    }
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      setTab(TABS[Math.max(0, i - 1)]);
    }
  }

  const tabX = TABS.indexOf(tab) * 100;

  return (
    <div className="l-prev">
      <div className="l-prevhead">
        <Dots color="#DAD8CF" />
        <span className="l-prevlogo">
          etika
          <Mark size={11} width={2.6} />
        </span>
        <span className="l-prevname">Larch Lane Café, Vancouver</span>
      </div>
      <div className="l-prevbody">
        <div role="tablist" aria-label="Preview" className="l-tablist" onPointerDown={onPointerDown} onKeyDown={onKeyDown}>
          <span className="l-tabind" aria-hidden="true" style={{ transform: `translateX(${tabX}%)` }} />
          <button type="button" role="tab" className={`l-tab${tab === "assess" ? " on" : ""}`} aria-selected={tab === "assess"} onClick={() => show("assess")}>
            Assessment
          </button>
          <button type="button" role="tab" className={`l-tab${tab === "act" ? " on" : ""}`} aria-selected={tab === "act"} onClick={() => show("act")}>
            Next step
          </button>
          <button type="button" role="tab" className={`l-tab${tab === "ask" ? " on" : ""}`} aria-selected={tab === "ask"} onClick={() => show("ask")}>
            Ask etika
          </button>
        </div>

        {tab === "assess" && (
          <div role="tabpanel" className="l-pane" style={{ gap: 16 }}>
            <div className="l-tally">
              <span className="l-maylabel">{may} may apply</span>
              <span className="l-asklabel">
                {ask === 0 ? "Nothing waiting on you" : ask === 1 ? "1 needs your input" : `${ask} need your input`}
              </span>
            </div>
            <div className="l-meter">
              <div style={{ width: `${Math.round((may / 12) * 100)}%` }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column" }}>
              {reqs.map((r) => (
                <div key={r.name} className="l-req l-rowin">
                  <div className="l-reqtext">
                    <div style={{ fontWeight: 500 }}>{r.name}</div>
                    <div className="l-small">Source: {r.src}</div>
                  </div>
                  <span className={`l-pill ${r.cls}`}>{r.st}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "act" && (
          <div role="tabpanel" className="l-pane" style={{ gap: 16 }}>
            <div className="l-nextcard">
              <div className="l-nextmain">
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 14, fontWeight: 500, color: "#2C4A21" }}>Do this next</span>
                  <span className="l-pill" style={{ borderRadius: 6, background: "#2C4A21", color: "#fff" }}>
                    Do first before you open
                  </span>
                </div>
                <div className="l-nexttitle">
                  {food ? "Apply for a health permit to operate a food premises" : "Apply for your City business licence"}
                </div>
                <div style={{ fontSize: 15 }}>
                  {food
                    ? "Because you prepare and serve food on site in Vancouver."
                    : "Because every business operating in Vancouver needs one."}
                </div>
                <div className="l-small">
                  Source:{" "}
                  {food ? "[Vancouver Coastal Health source title], [section]" : "[City of Vancouver source title], [section]"}, verified [date]
                </div>
              </div>
              <Link href={CHECK_HREF} className="l-btn l-btn-g l-nextbtn">
                Start this step
              </Link>
            </div>
            <div style={{ fontWeight: 500 }}>Get ready to apply</div>
            {nextSteps.map((label) => (
              <div key={label} className="l-todo">
                <span aria-hidden="true" className="l-box" />
                <span>{label}</span>
              </div>
            ))}
          </div>
        )}

        {tab === "ask" && (
          <div role="tabpanel" className="l-pane" style={{ gap: 14 }}>
            <div className="l-bubble">What do I need to submit with my application?</div>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2C4A21" strokeWidth="2.4" style={{ flex: "none", marginTop: 4 }} aria-hidden="true">
                <path d={MARK} />
              </svg>
              <div style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
                <p style={{ margin: 0 }}>
                  The health authority lists a floor plan, your menu, and food safety and sanitation plans as part of the
                  application. They are already on your checklist.
                </p>
                <div className="l-source">
                  <span className="l-mono" style={{ fontSize: 11, color: "#4A6B36" }}>
                    Source
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 500 }}>[Source title], [Section]</span>
                  <span className="l-small">&quot;[Short supporting excerpt from the official page]&quot;</span>
                </div>
                <p className="l-small" style={{ margin: 0 }}>
                  Not covered: fees and processing times weren&apos;t in the sources we checked.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** "Under the hood": a looping run of the coordinator, three area agents and the source check. */
function AgentFlow() {
  const [fp, setFp] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setFp((p) => (p + 1) % 4), 2600);
    return () => clearInterval(id);
  }, []);

  const lanes = FLOW_LANES.map((m) => {
    const st: LaneState = m.states[fp];
    const n = st === "done" ? 4 : st === "work" ? m.step : 0;
    return { ...m, st, n };
  });
  const checked = lanes.reduce((sum, l) => sum + l.n, 0);
  const ready = fp === 3;
  const fan = fp === 0 ? "#E2E0D8" : "#2C4A21";
  const merge = fp >= 2 ? "#2C4A21" : fp === 1 ? "#B9C8AE" : "#E2E0D8";

  return (
    <div className="l-under">
      <div className="l-underhead">
        <div style={{ maxWidth: 640 }}>
          <div className="l-mono l-eyebrow">Under the hood</div>
          <h3 className="l-underh3">Three agents, one cited plan.</h3>
          <p className="l-underp">
            When you run a check, a coordinator splits your facts by area. Specialist agents work at the same time, and
            nothing reaches you until it&apos;s matched to an official source.
          </p>
        </div>
        <div aria-live="polite" className="l-fstatus">
          {ready ? <Tick /> : <span className="l-fspin" aria-hidden="true" />}
          <span style={{ fontWeight: 500 }}>{["Starting", "Agents working", "Checking sources", "Plan ready"][fp]}</span>
          <span style={{ color: "#5F5E57" }}>{ready ? "12 of 12 cited" : `${checked} of 12 checked`}</span>
        </div>
      </div>

      <div className="l-flowbox">
        <div
          className="l-flow"
          role="img"
          aria-label="Your facts go to a coordinator, which sends them to three area agents working in parallel. Their findings pass a source check before you see your plan."
        >
          <div className="l-fcol">
            <span className="l-flab" style={{ gridColumn: 1 }}>
              01 Your facts
            </span>
            <div className="l-fnode done" style={{ gridColumn: 1 }}>
              <span style={{ fontWeight: 500 }}>8 confirmed facts</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {["Café", "Vancouver", "Owner only"].map((t) => (
                  <span key={t} className="l-pill" style={{ background: "#F1F0EB", color: "#4A4943" }}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="l-fc done" style={{ gridColumn: 2 }} aria-hidden="true" />
          <div className="l-fcol">
            <span className="l-flab" style={{ gridColumn: 3 }}>
              02 Coordinator
            </span>
            <div className={`l-fnode l-coord ${fp === 0 ? "work" : "done"}`} style={{ gridColumn: 3 }}>
              <span aria-hidden="true" className="l-coordmark">
                <Mark size={17} width={2.2} />
              </span>
              <span style={{ fontSize: 14, lineHeight: 1.35 }}>
                {fp === 0 ? "Splitting your check into 3 areas" : "Sent your facts to 3 agents"}
              </span>
            </div>
          </div>
          <div className={`l-fc ${fp === 0 ? "on" : "done"}`} style={{ gridColumn: 4 }} aria-hidden="true" />
          <div className="l-fcol">
            <span className="l-flab l-flab-lanes" style={{ gridColumn: 5 }}>
              03 Area agents
            </span>
            <div className="l-lanes" style={{ gridColumn: 5, ["--fan" as string]: fan, ["--merge" as string]: merge }}>
              {lanes.map((l) => (
                <div key={l.key} className={`l-fnode l-lane ${l.st}`}>
                  <span className="l-lic" aria-hidden="true">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                      <path d={l.icon} />
                    </svg>
                  </span>
                  <span style={{ fontWeight: 500, fontSize: 14, lineHeight: 1.3, minWidth: 0 }}>{l.area}</span>
                  <span className={`l-lst ${l.st}`}>
                    {l.st === "done" && <Tick size={13} stroke="currentColor" />}
                    {l.st === "work" && <span className="l-fspin" aria-hidden="true" />}
                    {l.st === "done" ? "Done" : l.st === "work" ? `${l.n} of 4` : "Up next"}
                  </span>
                  <div className="l-fbar" aria-hidden="true">
                    <div style={{ width: `${Math.round((l.n / 4) * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className={`l-fc ${ready ? "done" : fp === 2 ? "on" : ""}`} style={{ gridColumn: 6 }} aria-hidden="true" />
          <div className="l-fcol">
            <span className="l-flab" style={{ gridColumn: 7 }}>
              04 Source check
            </span>
            <div className={`l-fnode ${ready ? "done" : fp === 2 ? "work" : "wait"}`} style={{ gridColumn: 7 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontWeight: 500 }}>
                {fp === 2 && <span className="l-fspin" aria-hidden="true" />}
                {ready && <Tick />}
                {ready ? "12 of 12 cited" : fp === 2 ? "Checking citations" : "Waits for all agents"}
              </span>
              <span style={{ fontSize: 14, lineHeight: 1.4, color: "#5F5E57" }}>
                Every finding needs an official passage before you see it.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Landing() {
  const [spins, setSpins] = useState(0);
  const [food, setFood] = useState(true);
  const [staff, setStaff] = useState(false);
  const [sales, setSales] = useState<Sales>("unsure");
  const [menu, setMenu] = useState(false);
  const turn = () => setSpins((s) => s + 1);
  useStageScroll();

  return (
    <div className="lp">
      <section className="l-hero">
        <Noise id="n1" frequency={0.85} className="l-noise-hero" />

        <header className="l-wrap l-header">
          <a href="#" aria-label="etika home" className="l-logo">
            etika
            <Mark size={18} />
          </a>
          <nav aria-label="Main" className="l-nav">
            <a className="l-navlink" href="#how">
              How it works
            </a>
            <a className="l-navlink" href="#try">
              Try it
            </a>
          </nav>
          <button
            type="button"
            className="l-menu-btn"
            aria-label={menu ? "Close menu" : "Open menu"}
            aria-expanded={menu}
            onClick={() => setMenu((m) => !m)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d={menu ? "M6 6l12 12M18 6 6 18" : "M4 7h16M4 12h16M4 17h16"} />
            </svg>
          </button>
          {menu && (
            <nav aria-label="Main menu" className="l-mnav l-rowin">
              <a className="l-mlink" href="#how" onClick={() => setMenu(false)}>
                How it works
              </a>
              <a className="l-mlink" href="#try" onClick={() => setMenu(false)}>
                Try it
              </a>
              <Link className="l-btn l-btn-g" href={CHECK_HREF} style={{ borderRadius: 10, marginTop: 8 }}>
                <Mark size={16} />
                Start my check
              </Link>
            </nav>
          )}
        </header>

        <div className="l-wrap l-herobody">
          <div className="l-word l-rise" aria-hidden="true">
            etika
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
              <path d={MARK} />
            </svg>
          </div>
          <h1 className="l-h1 l-rise2">Know which rules apply to your small business.</h1>
          <p className="l-sub l-rise3">
            etika reads official sources and turns them into a clear, cited plan, so you know what to do next and why.
          </p>
          <div className="l-ctas l-rise3">
            <a className="l-btn l-btn-line l-cta" href="#how">
              Learn more
            </a>
            <Link className="l-btn l-btn-g l-cta-glow l-cta" href={CHECK_HREF}>
              <Mark size={17} />
              Start my check
            </Link>
          </div>
        </div>

        <div className="l-xtrack">
          <div className="l-xpin">
            <div className="l-xstage">
              <div aria-hidden="true" className="l-shade" />
              <div aria-hidden="true" className="l-lines" />
              <div aria-hidden="true" className="l-ring l-ring1" />
              <div aria-hidden="true" className="l-ring l-ring2" />
              <div aria-hidden="true" className="l-ring l-ring3" />
              <div aria-hidden="true" className="l-ring l-ring4" />
              <Noise id="n5" frequency={0.85} className="l-noise-stage" />

              <MarkScene onTurn={turn} spins={spins} />

              <div className="l-card">
                <div className="l-cardhead">
                  <Dots color="#D3D0C6" />
                  <Mark size={14} width={2.6} stroke="#2C4A21" />
                  <span style={{ fontSize: 14, fontWeight: 500 }}>Larch Lane Café check</span>
                </div>
                <div className="l-cardrows">
                  <CheckRow n={1}>
                    <div>
                      <div style={{ fontWeight: 500 }}>Read your 8 confirmed facts</div>
                      <div className="l-small14">Café, Vancouver, owner only, opening soon</div>
                    </div>
                  </CheckRow>
                  <CheckRow n={2}>
                    <div>
                      <div style={{ fontWeight: 500 }}>Matched 12 requirements</div>
                      <div className="l-small14">5 may apply, 3 need your input</div>
                      <a href="#try" className="l-viewsrc">
                        View sources
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                          <path d="m9 6 6 6-6 6" />
                        </svg>
                      </a>
                    </div>
                  </CheckRow>
                  <CheckRow n={3}>
                    <div style={{ fontWeight: 500 }}>Next step ready. Apply for a health permit before you open.</div>
                  </CheckRow>
                </div>
                <div className="l-askwrap">
                  <div className="l-askbox">
                    <span className="l-wide">Ask about your requirements</span>
                    <span className="l-narrow">Ask a question</span>
                    <span aria-hidden="true" className="l-caret" />
                  </div>
                </div>
              </div>

              <button type="button" aria-label="Turn the etika mark" className="l-turn" onClick={turn}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                  <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
                  <path d="M3 3v5h5" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>

      <section id="try" className="l-try">
        <Noise id="n2" frequency={0.9} className="l-noise-try" />
        <div className="l-wrap l-trywrap">
          <div className="l-qcol">
            <div>
              <div className="l-mono l-eyebrow">Try it</div>
              <h2 className="l-h2">See what may apply, before you sign up.</h2>
              <p className="l-tryp">
                Answer three questions about a café in Vancouver. The plan <span className="l-wide">on the right</span>
                <span className="l-narrow">below</span> updates as you go.
              </p>
            </div>

            <div className="l-qs">
              <div role="group" aria-labelledby="q1" className="l-q">
                <div id="q1" className="l-qlabel">
                  Do you prepare food on site?
                </div>
                <div className="l-segs">
                  <Seg on={food} onClick={() => setFood(true)}>
                    Yes
                  </Seg>
                  <Seg on={!food} onClick={() => setFood(false)}>
                    No
                  </Seg>
                </div>
              </div>
              <div role="group" aria-labelledby="q2" className="l-q">
                <div id="q2" className="l-qlabel">
                  Does anyone else work for you?
                </div>
                <div className="l-segs">
                  <Seg on={!staff} onClick={() => setStaff(false)}>
                    Just me
                  </Seg>
                  <Seg on={staff} onClick={() => setStaff(true)}>
                    I have staff
                  </Seg>
                </div>
              </div>
              <div role="group" aria-labelledby="q3" className="l-q">
                <div id="q3" className="l-qlabel">
                  Expect $30,000 or more in sales this year?
                </div>
                <div className="l-segs">
                  <Seg on={sales === "yes"} onClick={() => setSales("yes")}>
                    Yes
                  </Seg>
                  <Seg on={sales === "no"} onClick={() => setSales("no")}>
                    No
                  </Seg>
                  <Seg on={sales === "unsure"} onClick={() => setSales("unsure")}>
                    Not sure
                  </Seg>
                </div>
              </div>
            </div>
            <p className="l-small" style={{ margin: 0 }}>
              A preview with sample requirements. Your real check uses every fact you confirm.
            </p>
          </div>

          <Preview food={food} staff={staff} sales={sales} />
        </div>
      </section>

      <section id="how" className="l-how">
        <div className="l-wrap">
          <div className="l-howhead">
            <div className="l-mono l-eyebrow">How it works</div>
            <h2 className="l-h2">From a few questions to a plan you can act on.</h2>
            <p className="l-howp">
              No legal jargon and no guessing. etika matches what you tell it against a registry of real requirements.
            </p>
          </div>
          <div className="l-cells">
            <div className="l-cell">
              <span className="l-mono l-num">01</span>
              <h3 className="l-cellh3">Tell us about your business</h3>
              <p className="l-cellp">
                What you do, where you are and who works with you. Add your website or a document to save time.
              </p>
              <div style={{ marginTop: "auto", paddingTop: 16, display: "flex", flexWrap: "wrap", gap: 8 }}>
                <span className="l-pill l-chip" style={{ background: "#E3EBDD", color: "#22391A" }}>
                  Café
                </span>
                <span className="l-pill l-chip" style={{ background: "#E3EBDD", color: "#22391A" }}>
                  Vancouver
                </span>
                <span className="l-pill l-chip" style={{ background: "#F1F0EB", color: "#4A4943" }}>
                  Opening soon
                </span>
              </div>
            </div>
            <div className="l-cell">
              <span className="l-mono l-num">02</span>
              <h3 className="l-cellh3">See what may apply, with sources</h3>
              <p className="l-cellp">Each requirement explains why it showed up and quotes the official passage behind it.</p>
              <div className="l-why">
                <span style={{ fontSize: 14, fontWeight: 500 }}>Health permit</span>
                <span className="l-small">Because you prepare food on site</span>
              </div>
            </div>
            <div className="l-cell l-cell3">
              <span className="l-mono l-num">03</span>
              <h3 className="l-cellh3">Take one clear next step</h3>
              <p className="l-cellp">
                Verified links, a checklist of what to prepare, and a drafted inquiry when a question needs a human answer.
              </p>
              <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
                <div className="l-checkline">
                  <span aria-hidden="true" className="l-checked">
                    <svg width="11" height="11" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M2 6.5 5 9l5-6" />
                    </svg>
                  </span>
                  FOODSAFE certificate
                </div>
                <div className="l-checkline">
                  <span aria-hidden="true" className="l-unchecked" />
                  Floor plan
                </div>
              </div>
            </div>
          </div>

          <AgentFlow />
        </div>
      </section>

      <footer className="l-footer">
        <div className="l-wrap l-footrow">
          <div style={{ flex: "1 1 320px", minWidth: 0 }}>
            <a href="#" aria-label="etika home" className="l-footlogo">
              etika
              <Mark size={15} />
            </a>
            <p className="l-disclaimer">
              etika gives compliance guidance based on official sources. It is not a law firm and does not give legal advice.
            </p>
          </div>
          <nav aria-label="Footer" className="l-footnav">
            <a href="#how">How it works</a>
            <a href="#">Privacy</a>
            <a href="#">Contact</a>
          </nav>
        </div>
        <div className="l-wrap">
          <p className="l-copy">© 2026 etika</p>
        </div>
      </footer>
    </div>
  );
}
