import { useState } from "react";
import { NavLink } from "react-router-dom";
import { Settings2 } from "lucide-react";
import clsx from "clsx";
import { Logo } from "./Logo";
import { SettingsPanel } from "./SettingsPanel";

export function SettingsButton({ className }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={clsx("focus-ring grid h-10 w-10 place-items-center rounded-full text-ink-2 transition hover:bg-surface-2 hover:text-ink", className)}
        aria-label="Settings"
        title="Settings"
      >
        <Settings2 size={19} strokeWidth={1.75} />
      </button>
      <SettingsPanel open={open} onClose={() => setOpen(false)} />
    </>
  );
}

export function NavText({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        clsx(
          "focus-ring rounded px-1 text-sm underline-offset-[6px] transition",
          isActive ? "text-ink underline decoration-brand decoration-2" : "text-ink-2 hover:text-ink hover:underline decoration-line",
        )
      }
    >
      {children}
    </NavLink>
  );
}

export function TopBar({ children }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-[1180px] items-center gap-3 px-4 py-3 sm:gap-8 sm:px-6">
        <Logo className="shrink-0" compact />
        <div className="min-w-0 flex-1">{children}</div>
        <nav className="flex shrink-0 items-center gap-3">
          <span className="hidden sm:inline"><NavText to="/dashboard">Dashboard</NavText></span>
          <SettingsButton />
        </nav>
      </div>
    </header>
  );
}
