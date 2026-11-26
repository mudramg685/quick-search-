import { useEffect, useId, useRef, useState } from "react";
import { Clock, Search, X } from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";
import { removeHistory, useHistory, useSettings } from "../lib/settings";

/**
 * Search input with recent searches (when empty) and debounced autocomplete (trie-backed).
 * Keyboard: ↑/↓ move, Enter search, Esc close, "/" anywhere focuses it.
 * Implements the WAI-ARIA combobox pattern.
 */
export function SearchBox({ initial = "", onSearch, size = "md", autoFocus = false, inputRef: externalRef }) {
  const settings = useSettings();
  const history = useHistory();
  const [value, setValue] = useState(initial);
  const [remote, setRemote] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const ownRef = useRef(null);
  const inputRef = externalRef || ownRef;
  const listId = useId();
  const big = size === "lg";

  useEffect(() => setValue(initial), [initial]);

  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && !document.querySelector("[role=dialog]")) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [inputRef]);

  // Debounced suggestions; aborts stale requests so out-of-order responses can't win.
  useEffect(() => {
    const q = value.trim();
    if (!q || q === initial.trim() || !settings.suggest) {
      setRemote([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api.suggestions(q, ctrl.signal).then((d) => setRemote(d.suggestions)).catch(() => {});
    }, 110);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [value, initial, settings.suggest]);

  // Recent searches first (matching what's typed), then index suggestions.
  const typed = value.trim().toLowerCase();
  const recent = history.filter((h) => (typed ? h.toLowerCase().startsWith(typed) && h.toLowerCase() !== typed : true)).slice(0, typed ? 3 : 7);
  const items = [
    ...recent.map((text) => ({ text, recent: true })),
    ...(typed ? remote.filter((s) => !recent.some((r) => r.toLowerCase() === s)).map((text) => ({ text, recent: false })) : []),
  ].slice(0, 9);

  useEffect(() => setActive(-1), [value, remote.length]);

  const submit = (q) => {
    const query = (q ?? value).trim();
    if (!query) {
      inputRef.current?.focus();
      return;
    }
    setValue(query);
    setOpen(false);
    inputRef.current?.blur();
    onSearch(query);
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" && items.length) {
      e.preventDefault();
      setOpen(true);
      setActive((a) => (a + 1) % items.length);
    } else if (e.key === "ArrowUp" && items.length) {
      e.preventDefault();
      setActive((a) => (a <= 0 ? items.length - 1 : a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      submit(active >= 0 && open ? items[active].text : undefined);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  const showList = open && items.length > 0;

  return (
    <div className="relative w-full">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className={clsx(
          "relative flex items-center border bg-surface transition-[box-shadow,border-color,border-radius] duration-150",
          big ? "h-[54px] pl-5 pr-2" : "h-11 pl-4 pr-1.5",
          showList ? "rounded-t-[27px] border-line border-b-transparent shadow-lift" : "rounded-full border-line hover:shadow-soft focus-within:shadow-soft",
        )}
      >
        <Search className="shrink-0 text-ink-3" size={big ? 19 : 17} strokeWidth={1.75} aria-hidden="true" />
        <input
          ref={inputRef}
          value={value}
          autoFocus={autoFocus}
          onChange={(e) => {
            setValue(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          maxLength={256}
          placeholder={big ? "Search the index, or try \"write ahead log\"" : "Search"}
          aria-label="Search query"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          className={clsx("min-w-0 flex-1 bg-transparent px-3 text-ink placeholder:text-ink-3 focus:outline-none", big ? "text-[17px]" : "text-[15px]")}
        />
        {value ? (
          <button
            type="button"
            onClick={() => {
              setValue("");
              setOpen(true);
              inputRef.current?.focus();
            }}
            className="focus-ring grid h-8 w-8 place-items-center rounded-full text-ink-3 transition hover:text-ink"
            aria-label="Clear search"
          >
            <X size={17} strokeWidth={1.75} />
          </button>
        ) : (
          big && <kbd className="mr-3 hidden rounded border border-line px-1.5 py-0.5 font-mono text-[11px] text-ink-3 sm:block">/</kbd>
        )}
        {!big && (
          <button type="submit" aria-label="Search"
            className="focus-ring ml-1 grid h-8 w-8 place-items-center rounded-full text-brand transition hover:bg-surface-2">
            <Search size={17} strokeWidth={2} />
          </button>
        )}
      </form>

      {showList && (
        <ul
          id={listId}
          role="listbox"
          className={clsx(
            "absolute left-0 right-0 top-full z-40 overflow-hidden rounded-b-[27px] border border-t-0 border-line bg-surface pb-3 shadow-lift",
          )}
        >
          <li aria-hidden="true" className="mx-5 mb-2 border-t border-line" />
          {items.map((it, i) => (
            <li
              key={(it.recent ? "h:" : "s:") + it.text}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                submit(it.text);
              }}
              onMouseEnter={() => setActive(i)}
              className={clsx("group flex cursor-pointer items-center gap-3.5 px-5 py-[7px] text-[15px]", i === active ? "bg-surface-2" : "")}
            >
              {it.recent
                ? <Clock size={16} strokeWidth={1.75} className="shrink-0 text-ink-3" aria-hidden="true" />
                : <Search size={16} strokeWidth={1.75} className="shrink-0 text-ink-3" aria-hidden="true" />}
              <span className={clsx("flex-1 truncate", it.recent ? "text-[rgb(var(--visited))]" : "text-ink")}>
                <SuggestionText suggestion={it.text} typed={value} />
              </span>
              {it.recent && (
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    removeHistory(it.text);
                  }}
                  className="rounded px-1.5 text-xs text-ink-3 opacity-0 transition hover:text-ink hover:underline group-hover:opacity-100 group-aria-selected:opacity-100"
                  aria-label={`Remove "${it.text}" from history`}
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Typed prefix in regular weight, completion in bold – the conventional autocomplete look.
function SuggestionText({ suggestion, typed }) {
  const t = typed.trim().toLowerCase();
  if (t && suggestion.toLowerCase().startsWith(t)) {
    return (
      <>
        {suggestion.slice(0, t.length)}
        <strong className="font-semibold">{suggestion.slice(t.length)}</strong>
      </>
    );
  }
  return suggestion;
}
