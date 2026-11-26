import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, CheckCircle2, Clock, Loader2, Play, RefreshCw, Square, XCircle } from "lucide-react";
import clsx from "clsx";
import { TopBar } from "../components/TopBar";
import { BarList, ColumnChart, LatencyChart } from "../components/Charts";
import { ErrorState } from "../components/States";
import { STATIC, REPO_URL, api, displayDomain } from "../lib/api";
import { fmtBytes, fmtInt, fmtMs, fmtPct, timeAgo } from "../lib/format";

function Panel({ title, subtitle, action, children, className }) {
  return (
    <section className={clsx("rounded-lg border border-line bg-surface p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-[24px] leading-tight">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StatTile({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-5">
      <div className="smallcaps text-[13px] font-medium text-ink-3">{label}</div>
      <div className="mt-2 font-display text-[46px] leading-none tabular-nums text-ink">{value}</div>
      <div className="mt-2.5 text-xs text-ink-3">{sub}</div>
    </div>
  );
}

const STATUS_STYLE = {
  completed: { icon: CheckCircle2, color: "var(--status-good)", label: "Completed" },
  running: { icon: Loader2, color: "var(--series-1)", label: "Running", spin: true },
  queued: { icon: Clock, color: "var(--chart-axis)", label: "Queued" },
  failed: { icon: XCircle, color: "var(--status-critical)", label: "Failed" },
  cancelled: { icon: AlertCircle, color: "var(--status-warning)", label: "Cancelled" },
};

function StatusPill({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.queued;
  const Icon = s.icon;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-xs font-medium text-ink-2">
      <Icon size={13} style={{ color: s.color }} className={s.spin ? "animate-spin" : ""} /> {s.label}
    </span>
  );
}

const ERROR_LABELS = {
  robots: "Blocked by robots.txt", duplicate: "Duplicate content", http_error: "HTTP 4xx/5xx", timeout: "Timeout",
  dns: "DNS failure", connection: "Connection refused", tls: "TLS / certificate", too_large: "Too large",
  not_html: "Not HTML", redirect: "Redirect loop", protocol: "Protocol error", internal: "Internal error",
};

function CrawlPanel({ onFinished }) {
  const [seed, setSeed] = useState("");
  const [depth, setDepth] = useState(2);
  const [maxPages, setMaxPages] = useState(60);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const wasRunning = useRef(false);

  const poll = useCallback(() => {
    api.crawlStatus().then((s) => {
      setStatus(s);
      if (wasRunning.current && !s.running) onFinished?.();
      wasRunning.current = s.running;
    }).catch(() => {});
  }, [onFinished]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, status?.running ? 1000 : 5000);
    return () => clearInterval(id);
  }, [poll, status?.running]);

  const start = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.startCrawl({ seeds: seed.trim() ? [seed.trim()] : [], max_depth: Number(depth), max_pages: Number(maxPages) });
      wasRunning.current = true;
      poll();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const job = status?.job;
  const live = status?.live;
  const running = status?.running;
  const fetched = live ? live.fetched + live.failed : job?.pages_fetched ?? 0;
  const progress = job ? Math.min(1, fetched / job.max_pages) : 0;

  return (
    <Panel title="Crawler" subtitle="Breadth-first crawl · robots.txt · per-host rate limit"
      action={job && <StatusPill status={running ? "running" : job.status} />}>
      {STATIC ? (
        <p className="rounded-md border border-dashed border-line px-4 py-3 text-sm text-ink-2">
          Crawling runs in the Python backend, which this hosted demo does not include. The numbers on this page are a
          snapshot from the real crawler. <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="font-medium text-brand underline underline-offset-2">Run it locally</a> to crawl new sites.
        </p>
      ) : (
      <form onSubmit={start} className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto]">
        <label className="sr-only" htmlFor="seed">Seed URL</label>
        <input id="seed" value={seed} onChange={(e) => setSeed(e.target.value)} disabled={running}
          placeholder="Seed URL (empty = bundled QuirkPedia corpus)"
          className="focus-ring h-10 min-w-0 rounded-md border border-line bg-bg px-3 text-sm placeholder:text-ink-3 disabled:opacity-60" />
        <label className="flex h-10 items-center gap-2 rounded-md border border-line bg-bg px-3 text-xs text-ink-3">
          Depth
          <select value={depth} onChange={(e) => setDepth(e.target.value)} disabled={running} className="bg-transparent text-sm text-ink focus:outline-none">
            {[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="flex h-10 items-center gap-2 rounded-md border border-line bg-bg px-3 text-xs text-ink-3">
          Pages
          <input type="number" min={1} max={1000} value={maxPages} onChange={(e) => setMaxPages(e.target.value)} disabled={running}
            className="w-14 bg-transparent text-sm text-ink focus:outline-none" />
        </label>
        {running ? (
          <button type="button" onClick={() => api.cancelCrawl().then(poll)} className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md border border-line px-4 text-sm font-semibold transition hover:bg-surface-2">
            <Square size={14} /> Stop
          </button>
        ) : (
          <button type="submit" disabled={busy} className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-full bg-brand px-5 text-sm font-medium text-on-brand transition hover:opacity-90 disabled:opacity-60">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />} Crawl
          </button>
        )}
      </form>
      )}
      {error && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {job && (
        <div className="mt-5">
          <div className="flex items-center justify-between text-xs text-ink-3">
            <span className="truncate">Job #{job.id} · {job.seeds?.[0]}</span>
            <span className="tabular-nums">{fmtInt(fetched)} / {fmtInt(job.max_pages)} fetch budget</span>
          </div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-brand transition-[width] duration-500" style={{ width: `${(running ? progress : 1) * 100}%` }} />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
            {[
              ["Discovered", live?.discovered ?? job.pages_discovered],
              ["Fetched", live?.fetched ?? job.pages_fetched],
              ["Indexed", live?.stored ?? job.pages_stored],
              ["Failed", live?.failed ?? job.pages_failed],
            ].map(([k, v]) => (
              <div key={k} className="rounded-md bg-surface-2/70 py-2.5">
                <dd className="font-display text-[28px] leading-none tabular-nums">{fmtInt(v)}</dd>
                <dt className="text-xs text-ink-3">{k}</dt>
              </div>
            ))}
          </dl>
          {status.recent_errors?.length > 0 && (
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer text-xs font-medium text-ink-2 hover:text-ink">Recent crawl issues ({status.recent_errors.length})</summary>
              <ul className="mt-2 max-h-44 space-y-1 overflow-auto pr-1">
                {status.recent_errors.map((e) => (
                  <li key={e.id} className="flex gap-2 text-xs">
                    <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-ink-2">{e.error_type}{e.status_code ? ` ${e.status_code}` : ""}</span>
                    <span className="truncate text-ink-3" title={`${e.url} — ${e.message}`}>{e.url}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </Panel>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-[132px] rounded-lg" />)}</div>
      <div className="grid gap-4 lg:grid-cols-2">{[1, 2].map((i) => <div key={i} className="skeleton h-72 rounded-lg" />)}</div>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [docs, setDocs] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(() => {
    setRefreshing(true);
    Promise.all([api.stats(), api.documents(1, 6)])
      .then(([s, d]) => { setStats(s); setDocs(d); setError(null); })
      .catch(setError)
      .finally(() => setRefreshing(false));
  }, []);

  useEffect(() => {
    document.title = "Dashboard – QuirkSearch";
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [load]);

  const s = stats;
  const outcomes = s ? [{ label: "Indexed successfully", value: s.documents },
    ...Object.entries(s.errors_by_type).map(([k, v]) => ({ label: ERROR_LABELS[k] || k, value: v }))] : [];

  return (
    <div className="min-h-screen">
      <TopBar />
      <main className="mx-auto max-w-[1180px] px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-[48px] leading-none">Index analytics</h1>
            <p className="mt-2 font-read text-[16px] italic text-ink-2">Live numbers from the crawler, the inverted index and the query log.</p>
          </div>
          <button onClick={load} className="focus-ring inline-flex items-center gap-2 rounded-full border border-line bg-surface px-4 py-2 text-sm transition hover:border-ink-3">
            <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="mt-6">
          {error && !s ? <ErrorState error={error} onRetry={load} /> : !s ? <DashboardSkeleton /> : (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile label="Indexed pages" value={fmtInt(s.documents)} sub={`${fmtInt(s.domains)} domains · avg ${Math.round(s.avg_doc_length)} tokens`} />
                <StatTile label="Unique terms" value={fmtInt(s.terms)} sub={`${fmtInt(s.postings)} postings in the inverted index`} />
                <StatTile label="Avg query time" value={fmtMs(s.avg_latency_ms)} sub={`p95 ${fmtMs(s.p95_latency_ms)} · ${fmtInt(s.searches)} searches`} />
                <StatTile label="Crawl success rate" value={fmtPct(s.crawl_success_rate, 1)} sub={`${fmtInt(s.pages_fetched)} fetched · ${fmtInt(s.failed_requests)} failed requests`} />
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Link edges", fmtInt(s.links)],
                  ["Crawl jobs", fmtInt(s.crawl_jobs)],
                  ["Vocabulary words", fmtInt(s.vocabulary)],
                  ["Database size", fmtBytes(s.db_size_bytes)],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-baseline gap-3 border-b border-line px-1 py-2.5">
                    <span className="text-sm text-ink-2">{k}</span>
                    <span className="ml-auto font-mono text-sm tabular-nums text-ink">{v}</span>
                  </div>
                ))}
              </div>

              <CrawlPanel onFinished={load} />

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Query latency" subtitle="Engine time per search, milliseconds (last 60 searches)">
                  {s.recent_latencies.length ? <LatencyChart data={s.recent_latencies} format={fmtMs} /> : <p className="py-16 text-center text-sm text-ink-3">Run a search to see latency here.</p>}
                </Panel>
                <Panel title="Indexing activity" subtitle="Documents indexed per minute (UTC)">
                  <ColumnChart data={s.indexing_timeline} x="bucket" y="documents"
                    labelFormat={(b) => (b ? b.slice(11, 16) : "")} valueFormat={(v) => `${v} documents`} />
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Panel title="Crawl outcomes" subtitle="Every URL the crawler considered">
                  <BarList items={outcomes} valueFormat={fmtInt} />
                </Panel>
                <Panel title="Top domains" subtitle="Indexed pages per domain">
                  <BarList items={s.top_domains.map((d) => ({ label: displayDomain(d.domain), value: d.documents }))} valueFormat={fmtInt} />
                </Panel>
                <Panel title="Most widespread terms" subtitle="Document frequency (df)">
                  <BarList items={s.top_terms.slice(0, 8).map((t) => ({ label: t.term, value: t.df }))} valueFormat={(v) => `${v} docs`} />
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Recent searches">
                  {s.recent_searches.length ? (
                    <div className="-mx-2 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="text-left text-xs text-ink-3"><th className="px-2 pb-2 font-medium">Query</th><th className="px-2 pb-2 text-right font-medium">Results</th><th className="px-2 pb-2 text-right font-medium">Time</th><th className="px-2 pb-2 text-right font-medium">When</th></tr></thead>
                        <tbody>
                          {s.recent_searches.map((r, i) => (
                            <tr key={i} className="border-t border-line/70">
                              <td className="max-w-[12rem] truncate px-2 py-2">
                                <button onClick={() => navigate(`/search?q=${encodeURIComponent(r.query)}`)} className="focus-ring truncate rounded text-ink hover:text-brand">{r.query}</button>
                              </td>
                              <td className="px-2 py-2 text-right tabular-nums text-ink-2">{fmtInt(r.result_count)}</td>
                              <td className="px-2 py-2 text-right font-mono text-xs tabular-nums text-ink-2">{fmtMs(r.latency_ms)}</td>
                              <td className="whitespace-nowrap px-2 py-2 text-right text-xs text-ink-3">{timeAgo(r.created_at)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p className="py-8 text-center text-sm text-ink-3">No searches yet.</p>}
                </Panel>

                <Panel title="Indexing status">
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    {[
                      ["In-memory documents", fmtInt(s.index.documents)],
                      ["In-memory terms", fmtInt(s.index.terms)],
                      ["Index loaded", timeAgo(s.index.loaded_at)],
                      ["Last reload", s.index.last_reload_ms != null ? fmtMs(s.index.last_reload_ms) : "at startup"],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-md bg-surface-2/70 px-3 py-2.5">
                        <dt className="text-xs text-ink-3">{k}</dt>
                        <dd className="mt-0.5 font-semibold tabular-nums">{v}</dd>
                      </div>
                    ))}
                  </dl>
                  <h3 className="smallcaps mt-5 text-[13px] font-medium text-ink-3">Recent crawl jobs</h3>
                  <ul className="mt-2 divide-y divide-line/70">
                    {s.recent_jobs.map((j) => (
                      <li key={j.id} className="flex items-center gap-3 py-2 text-sm">
                        <span className="font-mono text-xs text-ink-3">#{j.id}</span>
                        <StatusPill status={j.status} />
                        <span className="text-ink-2">{fmtInt(j.pages_stored)} indexed</span>
                        <span className="ml-auto text-xs text-ink-3">{timeAgo(j.finished_at || j.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              </div>

              <Panel title="Recently indexed documents" subtitle={docs ? `${fmtInt(docs.total)} documents in the index` : ""}>
                <ul className="divide-y divide-line/70">
                  {docs?.documents.map((d) => (
                    <li key={d.id} className="flex flex-col gap-0.5 py-2.5 sm:flex-row sm:items-center sm:gap-4">
                      <a href={d.url} target="_blank" rel="noopener noreferrer" className="focus-ring truncate rounded font-medium text-ink hover:text-brand">{d.title}</a>
                      <span className="truncate text-xs text-ink-3 sm:ml-auto">{displayDomain(d.domain)} · depth {d.depth} · {fmtInt(d.doc_length)} tokens</span>
                    </li>
                  ))}
                </ul>
              </Panel>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
