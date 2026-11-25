import { useEffect, useState } from "react";

// Theme toggle: the class on <html> drives the CSS variables in index.css.
export function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("qs-theme", dark ? "dark" : "light");
    } catch {
      /* private mode – theme still works for this visit */
    }
  }, [dark]);
  return [dark, () => setDark((d) => !d)];
}
