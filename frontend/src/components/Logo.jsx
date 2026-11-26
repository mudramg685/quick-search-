import { Link } from "react-router-dom";
import clsx from "clsx";

// The mark: an asterisk – the footnote sign, "there's more to this" – with one arm
// that wandered off and became a dot. That's the quirk.
export function LogoMark({ size = 22, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden="true">
      <g stroke="currentColor" strokeWidth="3" strokeLinecap="round" fill="none">
        <path d="M16 16V6M16 16l8.66-5M16 16l8.66 5M16 16v10M16 16l-8.66 5" />
      </g>
      <circle cx="7.6" cy="10.4" r="2.1" fill="currentColor" />
    </svg>
  );
}

export function Wordmark({ className }) {
  return (
    <span className={clsx("font-display leading-none tracking-[-0.01em] text-ink", className)}>
      <span className="italic">Quirk</span>Search
    </span>
  );
}

export function Logo({ to = "/", className, compact = false }) {
  return (
    <Link to={to} className={clsx("focus-ring group inline-flex items-center gap-1.5 rounded-md", className)} aria-label="QuirkSearch home">
      <LogoMark size={20} className="text-brand transition-transform duration-500 group-hover:rotate-[30deg]" />
      <Wordmark className={clsx("text-[26px]", compact && "hidden sm:inline")} />
    </Link>
  );
}
