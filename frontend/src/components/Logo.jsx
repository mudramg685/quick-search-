import { Link } from "react-router-dom";
import clsx from "clsx";

// Custom mark: a lens with a four-point "spark of curiosity" inside, on a violet→pink tile.
export function LogoMark({ size = 32, className }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="qs-logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="rgb(var(--brand))" />
          <stop offset="1" stopColor="rgb(var(--brand-2))" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="17" fill="url(#qs-logo-g)" />
      <circle cx="29" cy="29" r="13" fill="none" stroke="#fff" strokeWidth="5" />
      <path d="M38.5 38.5 L48 48" stroke="#fff" strokeWidth="5.5" strokeLinecap="round" />
      <path d="M29 22.5 L30.6 27.4 L35.5 29 L30.6 30.6 L29 35.5 L27.4 30.6 L22.5 29 L27.4 27.4 Z" fill="#fff" />
    </svg>
  );
}

export function Logo({ size = "md", to = "/", className, compact = false }) {
  const big = size === "lg";
  return (
    <Link to={to} className={clsx("group inline-flex items-center gap-2.5 focus-ring rounded-xl", className)} aria-label="QuirkSearch home">
      <LogoMark size={big ? 44 : 30} className="transition-transform duration-300 group-hover:rotate-[-8deg] group-hover:scale-105" />
      <span className={clsx("font-display font-extrabold tracking-tight", big ? "text-3xl" : "text-lg", compact && "hidden md:inline")}>
        Quirk<span className="text-gradient">Search</span>
      </span>
    </Link>
  );
}
