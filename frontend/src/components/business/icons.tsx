import type { ReactNode } from "react";
import type { Area } from "@/lib/api";

const AREA_PATHS: Record<Area, ReactNode> = {
  registration: <path d="M6 3h9l4 4v14H6zM14 3v5h5" />,
  tax: <path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2zM9 8h6M9 12h6M9 16h3" />,
  employer: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3 3-5 6-5s6 2 6 5M16 5a3 3 0 0 1 0 6M18 15c2 .6 3 2.3 3 5" />
    </>
  ),
};

export function AreaIcon({ area, size = 18, strokeWidth = 1.5 }: { area: Area; size?: number; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} aria-hidden="true">
      {AREA_PATHS[area]}
    </svg>
  );
}

// --- Persona chibis (Phase 7) -----------------------------------------------------------------
// One small original character per specialist agent: big head, two dots, one prop that says what
// they do. Flat shapes only, so they stay legible at 20px in a row header and at 48px on a card.

const SKIN = "#f1ddc8";
const INK = "#2a2a28";
const HAIR = "#3f3a33";
const CLOTH = "#2c4a21";
const BAND = "#4a6b3a";
const BRIM = "#38532b";
const BLUSH = "#e4a596";
const AMBER = "#dfa23e";
const AMBER_DEEP = "#b9802a";
const PAPER = "#f0ebe0";
const TIE = "#b2503c";

function Shoulders({ fill = CLOTH }: { fill?: string }) {
  return <path d="M8 48c0-8.1 7.2-13.6 16-13.6S40 39.9 40 48z" fill={fill} />;
}

function Head() {
  return (
    <>
      <circle cx="11.9" cy="22.4" r="2.3" fill={SKIN} />
      <circle cx="36.1" cy="22.4" r="2.3" fill={SKIN} />
      <circle cx="24" cy="21" r="12.6" fill={SKIN} />
    </>
  );
}

/** Two dots, two cheeks and a small smile. The only expression any of them needs. */
function Face({ eyeY }: { eyeY: number }) {
  return (
    <>
      <circle cx="19.7" cy={eyeY} r="1.75" fill={INK} />
      <circle cx="28.3" cy={eyeY} r="1.75" fill={INK} />
      <circle cx="15.5" cy={eyeY + 3.4} r="1.9" fill={BLUSH} opacity="0.7" />
      <circle cx="32.5" cy={eyeY + 3.4} r="1.9" fill={BLUSH} opacity="0.7" />
      <path
        d={`M21.5 ${eyeY + 4}q2.5 2.2 5 0`}
        fill="none"
        stroke={INK}
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </>
  );
}

const AVATARS: Record<string, ReactNode> = {
  // The Registrar: neat hairline, round spectacles, bow tie. A clerk who likes a tidy file.
  registrar: (
    <>
      <Shoulders />
      <Head />
      <path d="M11.5 20.6C11.5 13.6 17.1 8.4 24 8.4s12.5 5.2 12.5 12.2c-1.7-3.7-6.1-5.7-12.5-5.7s-10.8 2-12.5 5.7z" fill={HAIR} />
      <Face eyeY={22} />
      <g fill="none" stroke={HAIR} strokeWidth="1.3">
        <circle cx="19.7" cy="22" r="3.9" />
        <circle cx="28.3" cy="22" r="3.9" />
        <path d="M23.6 22h.8" />
      </g>
      <path d="M24 38.2l-5.1-2.7v5.4zM24 38.2l5.1-2.7v5.4z" fill={TIE} />
      <circle cx="24" cy="38.2" r="1.2" fill={TIE} />
    </>
  ),
  // The Counter: an accountant's eyeshade and a pressed collar. Calm about numbers.
  counter: (
    <>
      <Shoulders />
      <Head />
      <Face eyeY={23.2} />
      <path d="M13.3 16.4a10.9 10.9 0 0 1 21.4 0z" fill={BAND} />
      <rect x="8.3" y="15.4" width="31.4" height="3.4" rx="1.7" fill={BRIM} />
      <path d="M19.6 35.4L24 41.2l4.4-5.8z" fill={PAPER} />
    </>
  ),
  // The Foreman: hard hat and two hi-vis stripes. Walks you through your first hire.
  foreman: (
    <>
      <Shoulders />
      <g stroke={AMBER} strokeLinecap="round">
        <path d="M19.4 38v10" strokeWidth="2.4" />
        <path d="M28.6 38v10" strokeWidth="2.4" />
        <path d="M15 44h18" strokeWidth="2.2" />
      </g>
      <Head />
      <Face eyeY={23.2} />
      <path d="M13.1 16.4a10.9 10.9 0 0 1 21.8 0z" fill={AMBER} />
      <path d="M24 6.4v9.4" stroke={AMBER_DEEP} strokeWidth="1.5" strokeLinecap="round" />
      <rect x="7.8" y="15.4" width="32.4" height="3.4" rx="1.7" fill={AMBER_DEEP} />
    </>
  ),
};

/** One persona's chibi portrait. Falls back to a plain head if a new avatar key appears. */
export function PersonaAvatar({ avatar, size = 48 }: { avatar: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" className="shrink-0">
      {AVATARS[avatar] ?? (
        <>
          <Shoulders />
          <Head />
          <Face eyeY={22} />
        </>
      )}
    </svg>
  );
}
