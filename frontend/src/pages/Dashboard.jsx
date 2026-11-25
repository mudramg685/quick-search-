import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity, AlertCircle, CheckCircle2, Clock, Database, FileText, Gauge, Globe2, HardDrive, Hash,
  Link2, Loader2, Play, RefreshCw, Search, Square, Timer, Waypoints, XCircle,
} from "lucide-react";
import clsx from "clsx";
import { TopBar } from "../components/TopBar";
import { BarList, ColumnChart, LatencyChart } from "../components/Charts";
import { ErrorState } from "../components/States";
import { api } from "../lib/api";
import { fmtBytes, fmtInt, fmtMs, fmtPct, timeAgo } from "../lib/format";

function Panel({ title, subtitle, icon: Icon, action, children, className }) {
  return (
    <section className={clsx("rounded-2xl border border-line bg-surface p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-display text-[15px] font-semibold">
            {Icon && <Icon size={16} className="text-ink-3" />} {title}
          </h2>
          {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function StatTile({ label, value, sub, icon: Icon, accent, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="relative overflow-hidden rounded-2xl border border-line bg-surface p-5"
    >
      {accent && <div className="absolute -right-10 -top-10 h-28 w-28 rounded-full bg-gradient-to-br from-brand/20 to-brand-2/20 blur-2xl" />}
      <div className="relative flex items-center justify-between text-sm text-ink-2">
        {label}
        <span className="grid h-8 w-8 place-items-center rounded-xl bg-surface-2 text-ink-2"><Icon size={16} /></span>
      </div>
      <div className="relative mt-3 font-display text-[32px] font-bold leading-none tracking-tight tabular-nums">{value}</div>
      <div className="relative mt-2 text-xs text-ink-3">{sub}</div>
    </motion.div>
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
    <Panel title="Crawler" subtitle="Breadth-first crawl · robots.txt · per-host rate limit" icon={Waypoints}
      action={job && <StatusPill status={running ? "running" : job.status} />}>
      <form onSubmit={start} className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto]">
        <label className="sr-only" htmlFor="seed">Seed URL</label>
        <input id="seed" value={seed} onChange={(e) => setSeed(e.target.value)} disabled={running}
          placeholder="Seed URL (empty = bundled QuirkPedia corpus)"
          className="focus-ring h-10 min-w-0 rounded-xl border border-line bg-bg px-3 text-sm placeholder:text-ink-3 disabled:opacity-60" />
        <label className="flex h-10 items-center gap-2 rounded-xl border border-line bg-bg px-3 text-xs text-ink-3">
          Depth
          <select value={depth} onChange={(e) => setDepth(e.target.value)} disabled={running} className="bg-transparent text-sm text-ink focus:outline-none">
            {[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        <label className="flex h-10 items-center gap-2 rounded-xl border border-line bg-bg px-3 text-xs text-ink-3">
          Pages
          <input type="number" min={1} max={1000} value={maxPages} onChange={(e) => setMaxPages(e.target.value)} disabled={running}
            className="w-14 bg-transparent text-sm text-ink focus:outline-none" />
        </label>
        {running ? (
          <button type="button" onClick={() => api.cancelCrawl().then(poll)} className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-line px-4 text-sm font-semibold transition hover:bg-surface-2">
            <Square size={14} /> Stop
          </button>
        ) : (
          <button type="submit" disabled={busy} className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand to-brand-2 px-4 text-sm font-semibold text-white transition hover:brightness-110 disabled:opacity-60">
            {busy ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />} Crawl
          </button>
        )}
      </form>
      {error && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {job && (
        <div className="mt-5">
          <div className="flex items-center justify-between text-xs text-ink-3">
            <span className="truncate">Job #{job.id} · {job.seeds?.[0]}</span>
            <span className="tabular-nums">{fmtInt(fetched)} / {fmtInt(job.max_pages)} fetch budget</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2">
            <motion.div className="h-full rounded-full bg-gradient-to-r from-brand to-brand-2" animate={{ width: `${(running ? progress : 1) * 100}%` }} transition={{ duration: 0.5 }} />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
            {[
              ["Discovered", live?.discovered ?? job.pages_discovered],
              ["Fetched", live?.fetched ?? job.pages_fetched],
              ["Indexed", live?.stored ?? job.pages_stored],
              ["Failed", live?.failed ?? job.pages_failed],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-surface-2/70 py-2.5">
                <dd className="font-display text-xl font-bold tabular-nums">{fmtInt(v)}</dd>
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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-[132px] rounded-2xl" />)}</div>
      <div className="grid gap-4 lg:grid-cols-2">{[1, 2].map((i) => <div key={i} className="skeleton h-72 rounded-2xl" />)}</div>
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
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl font-bold tracking-tight">Index analytics</h1>
            <p className="mt-1 text-sm text-ink-2">Live numbers from the crawler, the inverted index and the query log.</p>
          </div>
          <button onClick={load} className="focus-ring inline-flex items-center gap-2 rounded-xl border border-line bg-surface px-3.5 py-2 text-sm font-medium transition hover:bg-surface-2">
            <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} /> Refresh
          </button>
        </div>

        <div className="mt-6">
          {error && !s ? <ErrorState error={error} onRetry={load} /> : !s ? <DashboardSkeleton /> : (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile label="Indexed pages" value={fmtInt(s.documents)} sub={`${fmtInt(s.domains)} domains · avg ${Math.round(s.avg_doc_length)} tokens`} icon={FileText} accent delay={0} />
                <StatTile label="Unique terms" value={fmtInt(s.terms)} sub={`${fmtInt(s.postings)} postings in the inverted index`} icon={Hash} delay={0.05} />
                <StatTile label="Avg query time" value={fmtMs(s.avg_latency_ms)} sub={`p95 ${fmtMs(s.p95_latency_ms)} · ${fmtInt(s.searches)} searches`} icon={Timer} delay={0.1} />
                <StatTile label="Crawl success rate" value={fmtPct(s.crawl_success_rate, 1)} sub={`${fmtInt(s.pages_fetched)} fetched · ${fmtInt(s.failed_requests)} failed requests`} icon={Gauge} delay={0.15} />
              </div>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  [Link2, "Link edges", fmtInt(s.links)],
                  [Activity, "Crawl jobs", fmtInt(s.crawl_jobs)],
                  [Database, "Vocabulary words", fmtInt(s.vocabulary)],
                  [HardDrive, "Database size", fmtBytes(s.db_size_bytes)],
                ].map(([Icon, k, v]) => (
                  <div key={k} className="flex items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3">
                    <Icon size={16} className="text-ink-3" />
                    <span className="text-sm text-ink-2">{k}</span>
                    <span className="ml-auto font-display font-semibold tabular-nums">{v}</span>
                  </div>
                ))}
              </div>

              <CrawlPanel onFinished={load} />

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Query latency" subtitle="Engine time per search, milliseconds (last 60 searches)" icon={Timer}>
                  {s.recent_latencies.length ? <LatencyChart data={s.recent_latencies} format={fmtMs} /> : <p className="py-16 text-center text-sm text-ink-3">Run a search to see latency here.</p>}
                </Panel>
                <Panel title="Indexing activity" subtitle="Documents indexed per minute (UTC)" icon={Activity}>
                  <ColumnChart data={s.indexing_timeline} x="bucket" y="documents"
                    labelFormat={(b) => (b ? b.slice(11, 16) : "")} valueFormat={(v) => `${v} documents`} />
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Panel title="Crawl outcomes" subtitle="Every URL the crawler considered" icon={Waypoints}>
                  <BarList items={outcomes} valueFormat={fmtInt} />
                </Panel>
                <Panel title="Top domains" subtitle="Indexed pages per domain" icon={Globe2}>
                  <BarList items={s.top_domains.map((d) => ({ label: d.domain, value: d.documents }))} valueFormat={fmtInt} />
                </Panel>
                <Panel title="Most widespread terms" subtitle="Document frequency (df)" icon={Hash}>
                  <BarList items={s.top_terms.slice(0, 8).map((t) => ({ label: t.term, value: t.df }))} valueFormat={(v) => `${v} docs`} />
                </Panel>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title="Recent searches" icon={Search}>
                  {s.recent_searches.length ? (
                    <div className="-mx-2 overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead><tr className="text-left text-xs text-ink-3"><th className="px-2 pb-2 font-medium">Query</th><th className="px-2 pb-2 text-right font-medium">Results</th><th className="px-2 pb-2 text-right font-medium">Time</th><th className="px-2 pb-2 text-right font-medium">When</th></tr></thead>
                        <tbody>
                          {s.recent_searches.map((r, i) => (
                            <tr key={i} className="border-t border-line/70">
                              <td className="max-w-[12rem] truncate px-2 py-2">
                                <button onClick={() => navigate(`/search?q=${encodeURIComponent(r.query)}`)} className="focus-ring truncate rounded text-ink hover:text-brand-ink">{r.query}</button>
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

                <Panel title="Indexing status" icon={Database}>
                  <dl className="grid grid-cols-2 gap-3 text-sm">
                    {[
                      ["In-memory documents", fmtInt(s.index.documents)],
                      ["In-memory terms", fmtInt(s.index.terms)],
                      ["Index loaded", timeAgo(s.index.loaded_at)],
                      ["Last reload", s.index.last_reload_ms != null ? fmtMs(s.index.last_reload_ms) : "at startup"],
                    ].map(([k, v]) => (
                      <div key={k} className="rounded-xl bg-surface-2/70 px-3 py-2.5">
                        <dt className="text-xs text-ink-3">{k}</dt>
                        <dd className="mt-0.5 font-semibold tabular-nums">{v}</dd>
                      </div>
                    ))}
                  </dl>
                  <h3 className="mt-5 text-xs font-semibold uppercase tracking-[0.12em] text-ink-3">Recent crawl jobs</h3>
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

              <Panel title="Recently indexed documents" subtitle={docs ? `${fmtInt(docs.total)} documents in the index` : ""} icon={FileText}>
                <ul className="divide-y divide-line/70">
                  {docs?.documents.map((d) => (
                    <li key={d.id} className="flex flex-col gap-0.5 py-2.5 sm:flex-row sm:items-center sm:gap-4">
                      <a href={d.url} target="_blank" rel="noopener noreferrer" className="focus-ring truncate rounded font-medium text-ink hover:text-brand-ink">{d.title}</a>
                      <span className="truncate text-xs text-ink-3 sm:ml-auto">{d.domain} · depth {d.depth} · {fmtInt(d.doc_length)} tokens</span>
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
