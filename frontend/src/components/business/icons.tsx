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
