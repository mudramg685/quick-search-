import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import clsx from "clsx";
import { TopBar } from "../components/TopBar";
import { SearchBox } from "../components/SearchBox";
import { ResultCard } from "../components/ResultCard";
import { EmptyState, ErrorState, ResultSkeleton } from "../components/States";
import { api, displayDomain } from "../lib/api";
import { fmtInt, fmtMs } from "../lib/format";
import { addHistory, useSettings } from "../lib/settings";

function SideBlock({ title, children }) {
  return (
    <section className="border-t border-line pt-4 first:border-t-0 first:pt-0">
      <h3 className="smallcaps text-[13px] font-medium text-ink-3">{title}</h3>
      <div className="mt-2.5">{children}</div>
    </section>
  );
}

function Pagination({ page, pages, onPage }) {
  if (pages <= 1) return null;
  const from = Math.max(1, Math.min(page - 4, pages - 9));
  const nums = Array.from({ length: Math.min(10, pages) }, (_, i) => from + i);
  const cell = "focus-ring grid h-10 min-w-10 place-items-center rounded-full px-2 text-[15px] transition";
  return (
    <nav aria-label="Result pages" className="mt-12 flex max-w-[640px] items-center justify-center gap-1 font-read">
      <button onClick={() => onPage(page - 1)} disabled={page === 1} className={clsx(cell, "gap-1 pr-3 text-ink-2 hover:text-ink disabled:invisible")} aria-label="Previous page">
        <span className="inline-flex items-center gap-1"><ChevronLeft size={16} /> Previous</span>
      </button>
      {nums.map((n) => (
        <button key={n} onClick={() => onPage(n)} aria-current={n === page ? "page" : undefined}
          className={clsx(cell, n === page ? "bg-ink text-bg" : "result-title hover:bg-surface-2")}>
          {n}
        </button>
      ))}
      <button onClick={() => onPage(page + 1)} disabled={page === pages} className={clsx(cell, "pl-3 text-ink-2 hover:text-ink disabled:invisible")} aria-label="Next page">
        <span className="inline-flex items-center gap-1">Next <ChevronRight size={16} /></span>
      </button>
    </nav>
  );
}

export default function Results() {
  const settings = useSettings();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") || "";
  const domain = params.get("domain") || "";
  const exact = params.get("exact") === "1";
  const page = Math.max(1, Number(params.get("p")) || 1);
  const pageSize = settings.pageSize;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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
    api
      .search(q, { page, pageSize, domain: domain || undefined, autocorrect: settings.autocorrect && !exact })
      .then((d) => id === reqId.current && setData(d))
      .catch((e) => id === reqId.current && setError(e))
      .finally(() => id === reqId.current && setLoading(false));
  }, [q, page, pageSize, domain, exact, settings.autocorrect, navigate]);

  useEffect(() => {
    runSearch();
    window.scrollTo({ top: 0 });
  }, [runSearch]);

  useEffect(() => {
    document.title = q ? `${q} – QuirkSearch` : "QuirkSearch";
    if (q) addHistory(q);
    const base = q.replace(/["+-]|site:\S+/g, " ").trim().split(/\s+/).slice(0, 2).join(" ");
    if (!base) return setRelated([]);
    api.suggestions(base).then((d) => setRelated(d.suggestions.filter((s) => s !== q.toLowerCase()).slice(0, 8))).catch(() => setRelated([]));
  }, [q]);

  const go = (query, extra = {}) => setParams({ q: query, ...extra });
  const setDomain = (d) => setParams({ q, ...(d ? { domain: d } : {}) });
  const setPage = (p) => setParams({ q, ...(domain ? { domain } : {}), ...(exact ? { exact: "1" } : {}), ...(p > 1 ? { p: String(p) } : {}) });

  const pages = data ? Math.min(100, Math.ceil(data.total / pageSize)) : 0;
  const shownQuery = data?.corrected_query || q;

  return (
    <div className="min-h-screen">
      <TopBar>
        <div className="max-w-[600px]">
          <SearchBox initial={q} onSearch={(v) => go(v)} />
        </div>
      </TopBar>

      {/* tools row */}
      <div className="border-b border-line">
        <div className="mx-auto flex max-w-[1180px] items-center gap-5 overflow-x-auto px-4 text-sm sm:px-6 sm:pl-[calc(1.5rem+178px)]">
          <span className="border-b-2 border-brand py-2.5 text-ink">All results</span>
          <label className="flex shrink-0 items-center gap-1.5 py-2.5 text-ink-2">
            <span className="text-ink-3">Site</span>
            <select value={domain} onChange={(e) => setDomain(e.target.value)} aria-label="Filter by site"
              className="focus-ring max-w-[12rem] rounded bg-transparent text-ink-2 hover:text-ink focus:outline-none">
              <option value="">Any site</option>
              {(data?.facets || []).map((f) => <option key={f.domain} value={f.domain}>{displayDomain(f.domain)} ({f.count})</option>)}
              {domain && !(data?.facets || []).some((f) => f.domain === domain) && <option value={domain}>{domain}</option>}
            </select>
          </label>
        </div>
      </div>

      <main className="mx-auto grid max-w-[1180px] gap-x-16 gap-y-10 px-4 pb-20 pt-4 sm:px-6 sm:pl-[calc(1.5rem+178px)] lg:grid-cols-[minmax(0,640px)_minmax(0,300px)]">
        <div className="min-w-0">
          <p className="h-5 text-[13px] text-ink-3" aria-live="polite">
            {loading ? <span className="skeleton inline-block h-3 w-52 align-middle" /> : data && data.total > 0 ? (
              <>
                {page > 1 ? <>Page {page} of about </> : <>About </>}{fmtInt(data.total)} {data.total === 1 ? "result" : "results"} ({fmtMs(data.took_ms)})
                {data.domain && <> on <span className="text-ink-2">{displayDomain(data.domain)}</span></>}
              </>
            ) : null}
          </p>

          {!loading && data?.corrected_query && (
            <div className="mt-3 font-read text-[17px] leading-relaxed">
              <p className="text-ink-2">
                Showing results for{" "}
                <button onClick={() => go(data.corrected_query)} className="result-title focus-ring rounded-sm font-semibold italic hover:underline">
                  {data.corrected_query}
                </button>
              </p>
              <p className="text-[14px] text-ink-3">
                Search instead for{" "}
                <button onClick={() => go(q, { exact: "1" })} className="result-title focus-ring rounded-sm hover:underline">{q}</button>
              </p>
            </div>
          )}

          {!loading && data?.did_you_mean && data.total > 0 && (
            <p className="mt-3 font-read text-[17px] text-ink-2">
              Did you mean:{" "}
              <button onClick={() => go(data.did_you_mean)} className="result-title focus-ring rounded-sm font-semibold italic hover:underline">
                {data.did_you_mean}
              </button>
            </p>
          )}

          <div className="mt-6 space-y-8">
            {loading ? (
              Array.from({ length: 4 }, (_, i) => <ResultSkeleton key={i} />)
            ) : error ? (
              <ErrorState error={error} onRetry={runSearch} />
            ) : data && data.total === 0 ? (
              <EmptyState query={q} didYouMean={data.did_you_mean} onSearch={go} suggestions={["bm25", "inverted index", "tcp", "sqlite"]} />
            ) : (
              data?.results.map((r) => <ResultCard key={r.doc_id} result={r} />)
            )}
          </div>

          {!loading && !error && data?.total > 0 && related.length > 0 && page === 1 && (
            <section className="mt-14 max-w-[640px]">
              <h2 className="font-display text-[26px] leading-none">Related searches</h2>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {related.map((s) => (
                  <button key={s} onClick={() => go(s)}
                    className="focus-ring flex items-center gap-3 rounded-full bg-surface-2/70 px-4 py-2.5 text-left text-[15px] text-ink transition hover:bg-surface-2">
                    <Search size={15} className="shrink-0 text-ink-3" />
                    <span className="truncate">{s}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {!loading && !error && <Pagination page={page} pages={pages} onPage={setPage} />}
        </div>

        {/* margin notes */}
        <aside className="hidden space-y-5 self-start pt-11 lg:sticky lg:top-24 lg:block">
          <SideBlock title="How we read your query">
            {data ? (
              <>
                <div className="flex flex-wrap gap-1.5">
                  {data.terms.length ? data.terms.map((t) => (
                    <code key={t} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-ink">{t}</code>
                  )) : <span className="text-sm text-ink-3">only stop words</span>}
                  {data.excluded.map((t) => (
                    <code key={t} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs text-ink-3 line-through">{t}</code>
                  ))}
                </div>
                {data.phrases?.length > 0 && (
                  <p className="mt-2 text-xs text-ink-3">Exact phrase: {data.phrases.map((p) => <span key={p} className="font-mono text-ink-2">"{p}" </span>)}</p>
                )}
                <p className="mt-3 font-read text-[14px] leading-relaxed text-ink-2">
                  Lower-cased, stop words removed, each word reduced to its stem by the Porter algorithm
                  {data.corrected_query ? <>; spelling corrected to <em>{shownQuery}</em></> : ""}.
                </p>
              </>
            ) : <div className="skeleton h-12" />}
          </SideBlock>

          <SideBlock title="Search like an editor">
            <dl className="space-y-1.5 text-[13px] text-ink-2">
              {[['"write ahead log"', "exact phrase"], ["+heap", "must contain"], ["-python", "leave out"], ["site:docs.python.org", "one site only"]].map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3">
                  <dt className="font-mono text-xs text-ink">{k}</dt>
                  <dd className="text-ink-3">{v}</dd>
                </div>
              ))}
            </dl>
          </SideBlock>

          <SideBlock title="How ranking works">
            <p className="font-read text-[14px] leading-relaxed text-ink-2">
              Each page is scored with <em>BM25</em>: rare words weigh more, repeats help with diminishing returns, long pages are
              length-normalised. The sum is multiplied by how much of your query the page covers.
            </p>
            <p className="mt-2 font-mono text-[11px] leading-relaxed text-ink-3">
              Σ IDF·tf(k₁+1) / (tf+k₁(1−b+b·|d|/avgdl))<br />× (1 + matched) / (1 + query words)
            </p>
          </SideBlock>
        </aside>
      </main>
    </div>
  );
}
