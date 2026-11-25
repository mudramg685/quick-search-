import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ExternalLink, Sigma } from "lucide-react";
import clsx from "clsx";
import { Highlight } from "./Highlight";
import { prettyUrl } from "../lib/format";

// Deterministic tint per domain (hash → hue) so a domain is recognizable across results.
function domainHue(domain) {
  let h = 0;
  for (const ch of domain) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

export function ResultCard({ result, index }) {
  const [open, setOpen] = useState(false);
  const { host, crumbs } = prettyUrl(result.url);
  const hue = domainHue(result.domain);
  const pct = Math.round(result.relevance * 100);
  const terms = Object.entries(result.term_scores).sort((a, b) => b[1] - a[1]);
  const maxTerm = Math.max(...terms.map(([, v]) => v), 0.0001);

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: Math.min(index, 8) * 0.035, ease: [0.2, 0.7, 0.2, 1] }}
      className="group rounded-2xl border border-line bg-surface p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-lift"
    >
      <div className="flex items-center gap-2.5 text-sm">
        <span
          className="grid h-7 w-7 shrink-0 place-items-center rounded-lg text-xs font-bold uppercase text-white"
          style={{ background: `hsl(${hue} 62% 52%)` }}
          aria-hidden="true"
        >
          {result.domain.replace(/^www\./, "")[0]}
        </span>
        <div className="min-w-0 leading-tight">
          <div className="truncate font-medium text-ink">{host}</div>
          <div className="truncate text-xs text-ink-3">
            {[host, ...crumbs].join(" › ")}
          </div>
        </div>
        <span className="ml-auto shrink-0 rounded-full bg-surface-2 px-2 py-0.5 font-mono text-[11px] text-ink-3">#{result.rank}</span>
      </div>

      <h2 className="mt-3 font-display text-[19px] font-semibold leading-snug tracking-tight">
        <a
          href={result.url}
          target="_blank"
          rel="noopener noreferrer"
          className="focus-ring rounded text-ink decoration-brand/50 underline-offset-4 transition hover:text-brand-ink hover:underline"
        >
          <Highlight segments={result.title_segments} fallback={result.title} />
          <ExternalLink size={14} className="ml-1.5 hidden -translate-y-0.5 opacity-0 transition group-hover:opacity-60 sm:inline" />
        </a>
      </h2>

      <p className="mt-2 text-[15px] leading-relaxed text-ink-2">
        <Highlight segments={result.snippet} fallback={result.description} />
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-3">
        <div className="flex items-center gap-2" title={`Relevance relative to the top result: ${pct}%`}>
          <span className="font-medium text-ink-2">Relevance</span>
          <span className="relative h-1.5 w-24 overflow-hidden rounded-full bg-surface-2">
            <motion.span
              className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-brand to-brand-2"
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.6, delay: 0.15 }}
            />
          </span>
          <span className="tabular-nums text-ink-2">{pct}%</span>
        </div>
        <span className="tabular-nums">
          BM25 <span className="font-mono text-ink-2">{result.score.toFixed(2)}</span>
        </span>
        <span>
          matched <span className="font-medium text-ink-2">{result.matched_terms}</span>/{result.query_terms} terms
        </span>
        <button
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="focus-ring ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 font-medium text-ink-2 transition hover:bg-surface-2 hover:text-ink"
        >
          <Sigma size={13} /> Why this result?
          <ChevronDown size={14} className={clsx("transition-transform", open && "rotate-180")} />
        </button>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="mt-4 rounded-xl border border-line bg-surface-2/60 p-4">
              <p className="text-xs text-ink-3">
                BM25 contribution of each stemmed query term (sums to the total score):
              </p>
              <ul className="mt-3 space-y-2">
                {terms.map(([term, v]) => (
                  <li key={term} className="grid grid-cols-[6.5rem_1fr_3.5rem] items-center gap-3 text-xs">
                    <code className="truncate font-mono text-ink">{term}</code>
                    <span className="h-1.5 overflow-hidden rounded-full bg-surface">
                      <span className="block h-full rounded-full" style={{ width: `${(v / maxTerm) * 100}%`, background: "var(--series-1)" }} />
                    </span>
                    <span className="text-right font-mono tabular-nums text-ink-2">{v.toFixed(3)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}
