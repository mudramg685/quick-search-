import { NavLink } from "react-router-dom";
import { BarChart3, Moon, Search, Sun } from "lucide-react";
import clsx from "clsx";
import { Logo } from "./Logo";
import { useTheme } from "../lib/theme";

export function ThemeToggle() {
  const [dark, toggle] = useTheme();
  return (
    <button
      onClick={toggle}
      className="focus-ring grid h-9 w-9 place-items-center rounded-xl text-ink-2 transition hover:bg-surface-2 hover:text-ink"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      title={dark ? "Light theme" : "Dark theme"}
    >
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}

function NavItem({ to, icon: Icon, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        clsx(
          "focus-ring inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium transition",
          isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
        )
      }
    >
      <Icon size={16} />
      <span className="hidden sm:inline">{children}</span>
    </NavLink>
  );
}

export function TopBar({ children, showLogo = true }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 glass">
      <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3 sm:gap-5 sm:px-6">
        {showLogo && <Logo className="shrink-0" compact />}
        <div className="min-w-0 flex-1">{children}</div>
        <nav className="flex shrink-0 items-center gap-1">
          <span className="hidden sm:block"><NavItem to="/" icon={Search}>Search</NavItem></span>
          <NavItem to="/dashboard" icon={BarChart3}>Dashboard</NavItem>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
