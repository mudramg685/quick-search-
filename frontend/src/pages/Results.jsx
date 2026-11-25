import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Globe2, Info, Loader2, Microscope, SlidersHorizontal, Sparkles, X, Zap } from "lucide-react";
import clsx from "clsx";
import { TopBar } from "../components/TopBar";
import { SearchBox } from "../components/SearchBox";
import { ResultCard } from "../components/ResultCard";
import { EmptyState, ErrorState, ResultSkeleton } from "../components/States";
import { api } from "../lib/api";
import { fmtInt, fmtMs } from "../lib/format";

const PAGE_SIZE = 10;
const RELEVANCE_LEVELS = [
  { label: "All", value: 0 },
  { label: "≥ 25%", value: 0.25 },
  { label: "≥ 50%", value: 0.5 },
  { label: "≥ 75%", value: 0.75 },
];

function Card({ title, icon: Icon, children }) {
  return (
    <section className="rounded-2xl border border-line bg-surface p-4">
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-3">
        <Icon size={14} /> {title}
      </h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export default function Results() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") || "";
  const domain = params.get("domain") || "";

  const [data, setData] = useState(null); // first page response (summary, facets…)
  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [minRel, setMinRel] = useState(0);
  const [related, setRelated] = useState([]);
  const reqId = useRef(0);

  const runSearch = useCallback(() => {
    if (!q.trim()) {
      navigate("/");
      return;
    }
    const id = ++reqId.current; // ignore responses from superseded searches
    setLoading(true);
    setError(null);
    setPage(1);
    api
      .search(q, { page: 1, pageSize: PAGE_SIZE, domain: domain || undefined })
      .then((d) => {
        if (id !== reqId.current) return;
        setData(d);
        setResults(d.results);
      })
      .catch((e) => id === reqId.current && setError(e))
      .finally(() => id === reqId.current && setLoading(false));
    api.suggestions(q.split(" ").slice(0, 2).join(" ")).then((d) => setRelated(d.suggestions.filter((s) => s !== q.toLowerCase()).slice(0, 5))).catch(() => setRelated([]));
  }, [q, domain, navigate]);

  useEffect(() => {
    runSearch();
    document.title = q ? `${q} – QuirkSearch` : "QuirkSearch";
    window.scrollTo({ top: 0 });
  }, [runSearch, q]);

  const loadMore = () => {
    const next = page + 1;
    setLoadingMore(true);
    api
      .search(q, { page: next, pageSize: PAGE_SIZE, domain: domain || undefined })
      .then((d) => {
        setResults((r) => [...r, ...d.results]);
        setPage(next);
      })
      .catch(setError)
      .finally(() => setLoadingMore(false));
  };

  const go = (query) => setParams({ q: query });
  const setDomain = (d) => setParams(d ? { q, domain: d } : { q });

  const visible = useMemo(() => results.filter((r) => r.relevance >= minRel), [results, minRel]);
  const hidden = results.length - visible.length;
  const hasMore = data && results.length < data.total;

  return (
    <div className="min-h-screen">
      <TopBar>
        <div className="max-w-2xl">
          <SearchBox initial={q} onSearch={go} />
        </div>
      </TopBar>

      <main className="mx-auto grid max-w-6xl gap-8 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_290px]">
        <div className="min-w-0">
          {/* summary + filters */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-sm text-ink-2" aria-live="polite">
              {loading ? (
                <span className="skeleton inline-block h-4 w-56" />
              ) : data ? (
                <>
                  <span className="font-semibold text-ink">{fmtInt(data.total)}</span> {data.total === 1 ? "result" : "results"}
                  <span className="mx-1.5 text-line">•</span>
                  <span className="inline-flex items-center gap-1"><Zap size={13} className="text-brand" />{fmtMs(data.took_ms)}</span>
                  <span className="mx-1.5 text-line">•</span>
                  searched {fmtInt(data.index_size)} pages
                </>
              ) : null}
            </div>
            <div className="flex items-center gap-1 rounded-xl border border-line bg-surface p-1" role="group" aria-label="Minimum relevance">
              <SlidersHorizontal size={14} className="mx-1.5 text-ink-3" />
              {RELEVANCE_LEVELS.map((l) => (
                <button
                  key={l.value}
                  onClick={() => setMinRel(l.value)}
                  aria-pressed={minRel === l.value}
                  className={clsx(
                    "focus-ring rounded-lg px-2.5 py-1 text-xs font-medium transition",
                    minRel === l.value ? "bg-ink text-bg" : "text-ink-2 hover:bg-surface-2",
                  )}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {domain && (
            <div className="mt-3">
              <button onClick={() => setDomain("")} className="focus-ring inline-flex items-center gap-1.5 rounded-full bg-brand/10 px-3 py-1 text-sm font-medium text-brand-ink transition hover:bg-brand/15">
                <Globe2 size={14} /> {domain} <X size={14} />
              </button>
            </div>
          )}

          {data?.did_you_mean && data.total > 0 && (
            <p className="mt-3 text-sm text-ink-2">
              Did you mean <button onClick={() => go(data.did_you_mean)} className="font-semibold text-brand-ink underline underline-offset-4">{data.did_you_mean}</button>?
            </p>
          )}

          <div className="mt-5 space-y-3">
            {loading ? (
              Array.from({ length: 4 }, (_, i) => <ResultSkeleton key={i} />)
            ) : error ? (
              <ErrorState error={error} onRetry={runSearch} />
            ) : data && data.total === 0 ? (
              <EmptyState query={q} didYouMean={data.did_you_mean} onSearch={go} suggestions={["bm25", "inverted index", "tcp", "sqlite"]} />
            ) : (
              <>
                <AnimatePresence initial={false}>
                  {visible.map((r, i) => (
                    <ResultCard key={r.doc_id} result={r} index={i % PAGE_SIZE} />
                  ))}
                </AnimatePresence>
                {hidden > 0 && (
                  <p className="rounded-xl border border-dashed border-line px-4 py-3 text-center text-sm text-ink-3">
                    {hidden} loaded {hidden === 1 ? "result is" : "results are"} below the {Math.round(minRel * 100)}% relevance threshold.{" "}
                    <button onClick={() => setMinRel(0)} className="font-medium text-brand-ink underline underline-offset-4">Show all</button>
                  </p>
                )}
                {hasMore && (
                  <div className="pt-3 text-center">
                    <button
                      onClick={loadMore}
                      disabled={loadingMore}
                      className="focus-ring inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-5 py-2.5 text-sm font-semibold shadow-soft transition hover:-translate-y-0.5 hover:border-brand/40 disabled:opacity-60"
                    >
                      {loadingMore ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} className="text-brand" />}
                      {loadingMore ? "Loading…" : `Load more (${fmtInt(data.total - results.length)} left)`}
                    </button>
                  </div>
                )}
                {!hasMore && results.length > 0 && (
                  <p className="pt-4 text-center text-xs text-ink-3">That's every matching page in the index.</p>
                )}
              </>
            )}
          </div>
        </div>

        {/* sidebar */}
        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <Card title="Domains" icon={Globe2}>
            {loading ? (
              <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="skeleton h-7" />)}</div>
            ) : data?.facets?.length ? (
              <ul className="space-y-1">
                {data.facets.map((f) => {
                  const active = f.domain === (data.domain || "");
                  const max = data.facets[0].count;
                  return (
                    <li key={f.domain}>
                      <button
                        onClick={() => setDomain(active ? "" : f.domain)}
                        aria-pressed={active}
                        className={clsx(
                          "focus-ring relative flex w-full items-center justify-between overflow-hidden rounded-lg px-2.5 py-1.5 text-left text-sm transition",
                          active ? "bg-brand/10 font-semibold text-brand-ink" : "text-ink-2 hover:bg-surface-2",
                        )}
                      >
                        <span className="absolute inset-y-0 left-0 bg-surface-2" style={{ width: `${(f.count / max) * 100}%`, opacity: active ? 0 : 0.6 }} aria-hidden="true" />
                        <span className="relative truncate">{f.domain}</span>
                        <span className="relative ml-2 font-mono text-xs tabular-nums">{f.count}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="text-sm text-ink-3">No domains to filter.</p>
            )}
          </Card>

          <Card title="Query analysis" icon={Microscope}>
            {data ? (
              <>
                <p className="text-xs text-ink-3">After tokenizing, removing stop words and Porter stemming:</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {data.terms.length ? data.terms.map((t) => (
                    <code key={t} className="rounded-md bg-surface-2 px-2 py-0.5 font-mono text-xs text-ink">{t}</code>
                  )) : <span className="text-sm text-ink-3">only stop words</span>}
                  {data.excluded.map((t) => (
                    <code key={t} className="rounded-md bg-red-500/10 px-2 py-0.5 font-mono text-xs text-red-600 line-through dark:text-red-400">{t}</code>
                  ))}
                </div>
                <p className="mt-3 text-xs leading-relaxed text-ink-3">
                  Tip: use <code className="font-mono text-ink-2">+term</code> to require, <code className="font-mono text-ink-2">-term</code> to exclude,
                  <code className="font-mono text-ink-2"> site:domain</code> to restrict.
                </p>
              </>
            ) : <div className="skeleton h-12" />}
          </Card>

          {related.length > 0 && (
            <Card title="Related searches" icon={Sparkles}>
              <div className="flex flex-wrap gap-1.5">
                {related.map((s) => (
                  <button key={s} onClick={() => go(s)} className="focus-ring rounded-full border border-line px-3 py-1 text-sm text-ink-2 transition hover:border-brand/40 hover:text-ink">
                    {s}
                  </button>
                ))}
              </div>
            </Card>
          )}

          <Card title="How ranking works" icon={Info}>
            <p className="text-[13px] leading-relaxed text-ink-2">
              Each page is scored with <strong className="text-ink">BM25</strong>: rare terms weigh more (IDF), repeated
              terms help with diminishing returns, and long pages are length-normalized. The top {PAGE_SIZE} are picked with a min-heap.
            </p>
            <div className="mt-3 overflow-x-auto rounded-lg bg-surface-2 px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-2">
              Σ IDF(t) · tf·(k₁+1) / (tf + k₁·(1−b+b·|d|/avgdl))
            </div>
          </Card>
        </aside>
      </main>
    </div>
  );
}
