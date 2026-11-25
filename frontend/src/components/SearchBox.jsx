import { useEffect, useId, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, CornerDownLeft, Search, Sparkles, X } from "lucide-react";
import clsx from "clsx";
import { api } from "../lib/api";

/**
 * Search input with debounced autocomplete (trie-backed /api/suggestions).
 * Keyboard: ↑/↓ to move, Enter to search, Esc to close, "/" anywhere to focus.
 * Implements the WAI-ARIA combobox pattern for screen readers.
 */
export function SearchBox({ initial = "", onSearch, size = "md", autoFocus = false }) {
  const [value, setValue] = useState(initial);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const inputRef = useRef(null);
  const listId = useId();
  const big = size === "lg";

  useEffect(() => setValue(initial), [initial]);

  // "/" focuses the search box from anywhere on the page
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Debounced suggestions; aborts stale requests so out-of-order responses can't win.
  useEffect(() => {
    const q = value.trim();
    if (!q || q === initial.trim()) {
      setItems([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      api
        .suggestions(q, ctrl.signal)
        .then((d) => {
          setItems(d.suggestions);
          setActive(-1);
        })
        .catch(() => {});
    }, 120);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [value, initial]);

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
      submit(active >= 0 && open ? items[active] : undefined);
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
          "group relative flex items-center rounded-2xl border bg-surface transition-all duration-300",
          big ? "h-16 pl-5 pr-2 shadow-lift sm:h-[68px]" : "h-11 pl-3.5 pr-1.5 shadow-soft",
          "border-line focus-within:border-brand/50 focus-within:shadow-glow",
        )}
      >
        <Search className={clsx("shrink-0 text-ink-3 transition group-focus-within:text-brand", big ? "h-5 w-5" : "h-4 w-4")} />
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
          placeholder={big ? "Ask the index anything — try “bm25 ranking”" : "Search the index…"}
          aria-label="Search query"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          className={clsx(
            "min-w-0 flex-1 bg-transparent px-3 text-ink placeholder:text-ink-3 focus:outline-none",
            big ? "text-lg" : "text-[15px]",
          )}
        />
        {value && (
          <button
            type="button"
            onClick={() => {
              setValue("");
              inputRef.current?.focus();
            }}
            className="focus-ring mr-1 grid h-8 w-8 place-items-center rounded-lg text-ink-3 transition hover:bg-surface-2 hover:text-ink"
            aria-label="Clear search"
          >
            <X size={16} />
          </button>
        )}
        {!value && big && (
          <kbd className="mr-2 hidden rounded-md border border-line px-1.5 py-0.5 font-mono text-xs text-ink-3 sm:block">/</kbd>
        )}
        <button
          type="submit"
          className={clsx(
            "focus-ring inline-flex shrink-0 items-center gap-2 rounded-xl bg-gradient-to-r from-brand to-brand-2 font-semibold text-white transition hover:brightness-110 active:scale-[0.97]",
            big ? "h-12 px-5 text-[15px]" : "h-8 px-3 text-sm",
          )}
        >
          <span className={clsx(!big && "hidden sm:inline")}>Search</span>
          <ArrowRight size={big ? 18 : 15} />
        </button>
      </form>

      <AnimatePresence>
        {showList && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.14 }}
            className="absolute left-0 right-0 top-full z-40 mt-2 overflow-hidden rounded-2xl border border-line bg-surface p-1.5 shadow-lift"
          >
            {items.map((s, i) => (
              <li
                key={s}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  submit(s);
                }}
                onMouseEnter={() => setActive(i)}
                className={clsx(
                  "flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition",
                  i === active ? "bg-surface-2 text-ink" : "text-ink-2",
                )}
              >
                <Sparkles size={15} className="shrink-0 text-brand" />
                <span className="flex-1 truncate">
                  <SuggestionText suggestion={s} typed={value} />
                </span>
                {i === active && <CornerDownLeft size={14} className="text-ink-3" />}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

// Typed prefix in regular weight, completion in bold – the conventional autocomplete look.
function SuggestionText({ suggestion, typed }) {
  const t = typed.trim().toLowerCase();
  if (t && suggestion.startsWith(t)) {
    return (
      <>
        {suggestion.slice(0, t.length)}
        <strong className="font-semibold text-ink">{suggestion.slice(t.length)}</strong>
      </>
    );
  }
  return suggestion;
}
