import Link from "next/link";
import type { ReactNode, SelectHTMLAttributes } from "react";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link
      href={href}
      aria-label="etika home"
      className="inline-flex items-center gap-1.5 px-2.5 text-[28px] leading-none font-normal tracking-[-0.035em] text-brand no-underline"
    >
      etika
      <LogoMark />
    </Link>
  );
}

/** The etika asterisk, always in brand green. */
export function LogoMark({ size = 18, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--color-brand)"
      strokeWidth="2.2"
      aria-hidden="true"
      className={`flex-none ${className}`}
    >
      <path d="M12 1v22M1 12h22M4.2 4.2l15.6 15.6M19.8 4.2 4.2 19.8" />
    </svg>
  );
}

export function CheckIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 8.5 6.5 12 13 4" />
    </svg>
  );
}

export function UploadIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  );
}

/** Native select styled as `.inp` with the wireframe's chevron. */
export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span className="relative block">
      <select className={`inp ${className}`} {...props} />
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-3.5 -mt-[7px]"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </span>
  );
}

/** Radio-button group rendered as the wireframe's bordered `.opt` chips. */
export function ChoiceGroup<T extends string>({
  name,
  options,
  value,
  onChange,
  className = "flex flex-wrap gap-2.5",
  children,
}: {
  name: string;
  options: readonly { value: T; label: string }[];
  value: T | null;
  onChange: (value: T) => void;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <div className={className}>
      {options.map((o) => (
        <label key={o.value} className="opt">
          <input type="radio" name={name} checked={value === o.value} onChange={() => onChange(o.value)} />
          {o.label}
        </label>
      ))}
      {children}
    </div>
  );
}
