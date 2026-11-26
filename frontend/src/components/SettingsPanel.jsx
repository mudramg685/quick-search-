import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Check, Monitor, Moon, Sun, X } from "lucide-react";
import clsx from "clsx";
import { ACCENTS, clearHistory, resetSettings, setSettings, useHistory, useSettings } from "../lib/settings";

function Section({ title, children }) {
  return (
    <section className="border-t border-line py-5 first:border-t-0 first:pt-0">
      <h3 className="smallcaps text-[13px] font-medium text-ink-3">{title}</h3>
      <div className="mt-3 space-y-4">{children}</div>
    </section>
  );
}

function Row({ label, hint, children }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="min-w-0">
        <div className="text-[15px] text-ink">{label}</div>
        {hint && <div className="text-xs leading-snug text-ink-3">{hint}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Segmented({ value, options, onChange, label }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={String(o.value)}
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          title={o.title || o.label}
          className={clsx(
            "focus-ring inline-flex h-8 items-center gap-1.5 rounded-full px-3 text-[13px] transition-colors",
            value === o.value ? "bg-ink text-bg" : "text-ink-2 hover:text-ink",
          )}
        >
          {o.icon && <o.icon size={14} aria-hidden="true" />}
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Toggle({ checked, onChange, label }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={clsx(
        "focus-ring relative h-6 w-11 rounded-full border transition-colors",
        checked ? "border-brand bg-brand" : "border-line bg-surface-2",
      )}
    >
      <span
        className={clsx(
          "absolute top-[3px] h-4 w-4 rounded-full shadow-sm transition-all",
          checked ? "left-[22px] bg-on-brand" : "left-[3px] bg-ink-3",
        )}
      />
    </button>
  );
}

export function SettingsPanel({ open, onClose }) {
  const s = useSettings();
  const history = useHistory();
  const closeRef = useRef(null);
  const dark = document.documentElement.classList.contains("dark");

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  // Portal to <body>: the sticky header's backdrop-filter would otherwise trap this fixed drawer.
  return createPortal(
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="settings-title">
      <div className="fade-in absolute inset-0 bg-ink/25" onClick={onClose} />
      <aside className="drawer-in absolute inset-y-0 right-0 flex w-full max-w-[400px] flex-col border-l border-line bg-bg shadow-lift">
        <header className="flex items-center justify-between border-b border-line px-6 py-4">
          <h2 id="settings-title" className="font-display text-[28px] leading-none">Settings</h2>
          <button ref={closeRef} onClick={onClose} aria-label="Close settings"
            className="focus-ring grid h-9 w-9 place-items-center rounded-full text-ink-2 hover:bg-surface-2 hover:text-ink">
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          <Section title="Appearance">
            <Row label="Theme">
              <Segmented label="Theme" value={s.theme} onChange={(theme) => setSettings({ theme })} options={[
                { value: "light", label: "Light", icon: Sun },
                { value: "dark", label: "Dark", icon: Moon },
                { value: "system", label: "Auto", icon: Monitor, title: "Follow your device" },
              ]} />
            </Row>
            <div>
              <div className="text-[15px] text-ink">Accent colour</div>
              <div className="mt-2.5 grid grid-cols-6 gap-2" role="radiogroup" aria-label="Accent colour">
                {ACCENTS.map((a) => {
                  const active = s.accent === a.id;
                  return (
                    <button key={a.id} role="radio" aria-checked={active} aria-label={a.label} title={a.label}
                      onClick={() => setSettings({ accent: a.id })}
                      className={clsx("focus-ring group flex flex-col items-center gap-1 rounded-lg py-1.5", active && "bg-surface-2")}>
                      <span className="grid h-8 w-8 place-items-center rounded-full ring-1 ring-ink/10"
                        style={{ background: dark ? a.dark : a.light }}>
                        {active && <Check size={15} className="text-on-brand" strokeWidth={2.5} />}
                      </span>
                      <span className="text-[11px] text-ink-3 group-hover:text-ink-2">{a.label.split(" ")[0]}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <Row label="Reading font" hint="Used for result titles and snippets">
              <Segmented label="Reading font" value={s.font} onChange={(font) => setSettings({ font })} options={[
                { value: "serif", label: "Serif" },
                { value: "sans", label: "Sans" },
              ]} />
            </Row>
            <Row label="Text size">
              <Segmented label="Text size" value={s.size} onChange={(size) => setSettings({ size })} options={[
                { value: "s", label: "S" }, { value: "m", label: "M" }, { value: "l", label: "L" },
              ]} />
            </Row>
          </Section>

          <Section title="Search">
            <Row label="Results per page">
              <Segmented label="Results per page" value={s.pageSize} onChange={(pageSize) => setSettings({ pageSize })} options={[
                { value: 10, label: "10" }, { value: 20, label: "20" }, { value: 30, label: "30" },
              ]} />
            </Row>
            <Row label="Open results in a new tab">
              <Toggle label="Open results in a new tab" checked={s.newTab} onChange={(newTab) => setSettings({ newTab })} />
            </Row>
            <Row label="Suggestions while typing">
              <Toggle label="Suggestions while typing" checked={s.suggest} onChange={(suggest) => setSettings({ suggest })} />
            </Row>
            <Row label="Fix spelling automatically" hint="When nothing matches, search the corrected words">
              <Toggle label="Fix spelling automatically" checked={s.autocorrect} onChange={(autocorrect) => setSettings({ autocorrect })} />
            </Row>
            <Row label="Show ranking details" hint="BM25 score and per-word breakdown on each result">
              <Toggle label="Show ranking details" checked={s.details} onChange={(details) => setSettings({ details })} />
            </Row>
          </Section>

          <Section title="Privacy">
            <Row label="Remember my searches" hint="Kept only in this browser">
              <Toggle label="Remember my searches" checked={s.history} onChange={(h) => setSettings({ history: h })} />
            </Row>
            <Row label="Search history" hint={history.length ? `${history.length} saved ${history.length === 1 ? "search" : "searches"}` : "Nothing saved"}>
              <button onClick={clearHistory} disabled={!history.length}
                className="focus-ring rounded-full border border-line px-3.5 py-1.5 text-[13px] text-ink-2 transition hover:border-ink-3 hover:text-ink disabled:opacity-40">
                Clear
              </button>
            </Row>
          </Section>

          <Section title="Keyboard">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              {[["/", "Focus the search box"], ["↑ ↓", "Move through suggestions"], ["Enter", "Search"], ["Esc", "Close menus and this panel"]].map(([k, v]) => (
                <div key={k} className="contents">
                  <dt><kbd className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-xs text-ink-2">{k}</kbd></dt>
                  <dd className="text-ink-2">{v}</dd>
                </div>
              ))}
            </dl>
          </Section>
        </div>

        <footer className="flex items-center justify-between border-t border-line px-6 py-3.5 text-[13px]">
          <button onClick={resetSettings} className="focus-ring rounded text-ink-3 underline-offset-4 hover:text-ink hover:underline">
            Restore defaults
          </button>
          <span className="text-ink-3">Saved automatically</span>
        </footer>
      </aside>
    </div>,
    document.body,
  );
}
