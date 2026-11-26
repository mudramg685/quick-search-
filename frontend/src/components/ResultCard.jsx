import { useState } from "react";
import clsx from "clsx";
import { Highlight } from "./Highlight";
import { prettyUrl } from "../lib/format";
import { useSettings } from "../lib/settings";

export function ResultCard({ result }) {
  const settings = useSettings();
  const [open, setOpen] = useState(false);
  const { host, crumbs } = prettyUrl(result.url);
  const pct = Math.round(result.relevance * 100);
  const terms = Object.entries(result.term_scores).sort((a, b) => b[1] - a[1]);
  const maxTerm = Math.max(...terms.map(([, v]) => v), 0.0001);
  const site = result.domain.replace(/^www\./, "");
  const linkProps = settings.newTab ? { target: "_blank", rel: "noopener noreferrer" } : {};
  const bm25 = terms.reduce((s, [, v]) => s + v, 0);

  return (
    <article className="group max-w-[640px]">
      <a href={result.url} {...linkProps} className="focus-ring -mx-1 block rounded px-1" tabIndex={-1} aria-hidden="true">
        <div className="flex items-center gap-3">
          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-line bg-surface font-display text-[15px] uppercase leading-none text-ink-2">
            {site[0]}
          </span>
          <div className="min-w-0 leading-tight">
            <div className="truncate text-sm text-ink">{site}</div>
            <div className="truncate text-xs text-ink-3">{[host, ...crumbs].join(" › ")}</div>
          </div>
        </div>
      </a>

      <h2 className="mt-1.5 font-read text-[21px] font-normal leading-snug">
        <a href={result.url} {...linkProps} className="result-title focus-ring rounded-sm underline-offset-[3px] hover:underline">
          <Highlight segments={result.title_segments} fallback={result.title} />
        </a>
      </h2>

      <p className="mt-1 font-read text-[15.5px] leading-[1.6] text-ink-2">
        <Highlight segments={result.snippet} fallback={result.description} />
      </p>

      {settings.details && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
          <span className="inline-flex items-center gap-1.5" title={`Score relative to the best match: ${pct}%`}>
            <span className="relative h-[3px] w-12 overflow-hidden rounded-full bg-line" aria-hidden="true">
              <span className="absolute inset-y-0 left-0 bg-brand" style={{ width: `${pct}%` }} />
            </span>
            <span className="tabular-nums">{pct}%</span>
          </span>
          <span aria-hidden="true">·</span>
          <span>{result.matched_terms} of {result.query_terms} {result.query_terms === 1 ? "word" : "words"}</span>
          <span aria-hidden="true">·</span>
          <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
            className="focus-ring rounded underline decoration-line underline-offset-4 transition hover:text-ink hover:decoration-ink-3">
            {open ? "Hide ranking" : "Why this result?"}
          </button>
        </div>
      )}

      {open && settings.details && (
        <div className="fade-in mt-3 border-l-2 border-brand/60 pl-4">
          <p className="font-read text-[14px] italic text-ink-2">
            BM25 {bm25.toFixed(2)} × coverage {result.coverage?.toFixed(2) ?? "1.00"} ={" "}
            <span className="not-italic text-ink tabular-nums">{result.score.toFixed(2)}</span>
          </p>
          <ul className="mt-2 space-y-1.5">
            {terms.map(([term, v]) => (
              <li key={term} className="grid grid-cols-[7rem_1fr_3.25rem] items-center gap-3 text-xs">
                <code className="truncate font-mono text-ink-2">{term}</code>
                <span className="h-[5px] overflow-hidden rounded-full bg-surface-2">
                  <span className="block h-full rounded-full bg-brand" style={{ width: `${(v / maxTerm) * 100}%` }} />
                </span>
                <span className="text-right font-mono tabular-nums text-ink-2">{v.toFixed(3)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs leading-relaxed text-ink-3">
            Each word adds its BM25 weight; coverage = (1 + words matched) / (1 + words in query), so pages that contain your whole
            query rise above ones that repeat a single word.
          </p>
        </div>
      )}
    </article>
  );
}
