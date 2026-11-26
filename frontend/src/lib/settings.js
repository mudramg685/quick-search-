// Per-browser preferences (theme, accent, fonts, search behaviour) and search history.
// Stored in localStorage as a convenience only – everything works when storage is blocked.
import { useSyncExternalStore } from "react";

const KEY = "qs-settings";
const HISTORY_KEY = "qs-history";

export const DEFAULTS = {
  theme: "system", // light | dark | system
  accent: "vermilion",
  font: "serif", // reading font for titles & snippets: serif | sans
  size: "m", // s | m | l
  pageSize: 10,
  newTab: false,
  suggest: true,
  autocorrect: true,
  details: true, // show the BM25 "why this result" line
  history: true,
};

// Swatches shown in Settings; the real values live in index.css per theme.
export const ACCENTS = [
  { id: "vermilion", label: "Vermilion", light: "#a8401f", dark: "#e8875f" },
  { id: "ink", label: "Ink blue", light: "#2b4c7e", dark: "#93b4e6" },
  { id: "moss", label: "Moss", light: "#476b2e", dark: "#a9c57f" },
  { id: "plum", label: "Plum", light: "#7d3a68", dark: "#d9a0c8" },
  { id: "ochre", label: "Ochre", light: "#8a5a08", dark: "#e0b25a" },
  { id: "graphite", label: "Graphite", light: "#2a2723", dark: "#e9e4da" },
];

const load = (key, fallback) => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
};
const save = (key, value) => {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode – the choice still applies for this visit */
  }
};

function createStore(initial) {
  let state = initial;
  const subs = new Set();
  return {
    get: () => state,
    set: (next) => { state = next; subs.forEach((f) => f()); },
    subscribe: (f) => { subs.add(f); return () => subs.delete(f); },
  };
}

const settingsStore = createStore({ ...DEFAULTS, ...load(KEY, {}) });
const historyStore = createStore(Array.isArray(load(HISTORY_KEY, [])) ? load(HISTORY_KEY, []) : []);

const media = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;

export function applySettings(s = settingsStore.get()) {
  const el = document.documentElement;
  const dark = s.theme === "dark" || (s.theme === "system" && media?.matches);
  el.classList.toggle("dark", !!dark);
  el.dataset.accent = s.accent;
  el.dataset.font = s.font;
  el.dataset.size = s.size;
}
media?.addEventListener?.("change", () => applySettings());

export function setSettings(patch) {
  const next = { ...settingsStore.get(), ...patch };
  save(KEY, next);
  applySettings(next);
  settingsStore.set(next);
  if (patch.history === false) clearHistory();
}

export function resetSettings() {
  save(KEY, null);
  applySettings(DEFAULTS);
  settingsStore.set({ ...DEFAULTS });
}

export const getSettings = settingsStore.get;
export const useSettings = () => useSyncExternalStore(settingsStore.subscribe, settingsStore.get);

// ---- search history ---------------------------------------------------------------
export const useHistory = () => useSyncExternalStore(historyStore.subscribe, historyStore.get);

export function addHistory(query) {
  const q = query.trim();
  if (!q || !settingsStore.get().history) return;
  const next = [q, ...historyStore.get().filter((h) => h.toLowerCase() !== q.toLowerCase())].slice(0, 25);
  save(HISTORY_KEY, next);
  historyStore.set(next);
}

export function removeHistory(query) {
  const next = historyStore.get().filter((h) => h !== query);
  save(HISTORY_KEY, next);
  historyStore.set(next);
}

export function clearHistory() {
  save(HISTORY_KEY, null);
  historyStore.set([]);
}
