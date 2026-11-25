import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowUpRight, Boxes, Database, Network, Orbit, Sparkles, Telescope, Timer } from "lucide-react";
import { Background } from "../components/Background";
import { LogoMark } from "../components/Logo";
import { SearchBox } from "../components/SearchBox";
import { ThemeToggle } from "../components/TopBar";
import { api } from "../lib/api";
import { fmtInt, fmtMs } from "../lib/format";

const SUGGESTED = ["bm25 ranking", "tcp handshake", "inverted index", "write ahead log", "python list comprehension", "octopus"];

const TOPICS = [
  { title: "Computer Networks", icon: Network, query: "http tcp dns protocol", blurb: "HTTP, TCP, DNS, TLS and the art of polite crawling." },
  { title: "Databases", icon: Database, query: "database transactions index", blurb: "Normalization, B-trees, ACID and query planners." },
  { title: "Algorithms", icon: Boxes, query: "heap trie hash table graph", blurb: "Hash maps, tries, heaps and graph traversal." },
  { title: "Search Engines", icon: Telescope, query: "inverted index ranking", blurb: "Crawlers, inverted indexes, TF-IDF and BM25." },
  { title: "Curiosities", icon: Orbit, query: "octopus black holes sourdough", blurb: "Octopus brains, black holes and wild yeast." },
];

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay, ease: [0.2, 0.7, 0.2, 1] },
});

function LiveStats() {
  const [stats, setStats] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    const load = () => api.stats(ctrl.signal).then((s) => { setStats(s); setFailed(false); }).catch((e) => e.name !== "AbortError" && setFailed(true));
    load();
    const id = setInterval(load, 10000);
    return () => { ctrl.abort(); clearInterval(id); };
  }, []);

  const items = [
    { label: "pages indexed", value: stats && fmtInt(stats.documents) },
    { label: "unique terms", value: stats && fmtInt(stats.terms) },
    { label: "domains", value: stats && fmtInt(stats.domains) },
    { label: "avg query time", value: stats && fmtMs(stats.avg_latency_ms) },
  ];
  return (
    <div className="mx-auto mt-10 flex max-w-3xl flex-col items-center gap-3 text-sm sm:flex-row sm:flex-wrap sm:justify-center sm:gap-0">
      <span className="inline-flex shrink-0 sm:mr-3 items-center gap-1.5 rounded-full border border-line bg-surface/70 px-2.5 py-1 text-xs font-medium text-ink-2 glass">
        <span className="relative flex h-2 w-2">
          {!failed && <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: "var(--status-good)" }} />}
          <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: failed ? "var(--status-critical)" : "var(--status-good)" }} />
        </span>
        {failed ? "Backend offline" : "Live index"}
      </span>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:flex sm:gap-0 sm:divide-x sm:divide-line">
        {items.map((it) => (
          <span key={it.label} className="inline-flex items-baseline gap-1.5 whitespace-nowrap py-1 text-ink-3 sm:px-4">
            {stats ? <span className="font-display text-base font-semibold tabular-nums text-ink">{it.value}</span> : <span className="skeleton inline-block h-4 w-10" />}
            {it.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const navigate = useNavigate();
  const go = (q) => navigate(`/search?q=${encodeURIComponent(q)}`);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <Background />
      <header className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <div className="flex items-center gap-2 font-display text-base font-bold tracking-tight">
          <LogoMark size={28} /> QuirkSearch
        </div>
        <nav className="flex items-center gap-1">
          <button onClick={() => navigate("/dashboard")} className="focus-ring inline-flex items-center gap-1 rounded-xl px-3 py-2 text-sm font-medium text-ink-2 transition hover:bg-surface-2 hover:text-ink">
            Dashboard <ArrowUpRight size={15} />
          </button>
          <ThemeToggle />
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-4 pb-24 pt-10 text-center sm:px-6 sm:pt-20">
        <motion.div {...fade(0)} className="inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3.5 py-1.5 text-xs font-medium text-ink-2 glass">
          <Sparkles size={13} className="text-brand" />
          Own crawler · inverted index · BM25 ranking — no borrowed search APIs
        </motion.div>

        <motion.h1 {...fade(0.08)} className="mt-7 font-display text-[44px] font-extrabold leading-[1.02] tracking-[-0.035em] sm:text-7xl md:text-[84px]">
          Curiosity deserves
          <br />
          <span className="font-serif text-[1.08em] font-normal italic tracking-[-0.01em] text-gradient">better results.</span>
        </motion.h1>

        <motion.p {...fade(0.16)} className="mx-auto mt-6 max-w-xl text-lg text-ink-2">
          QuirkSearch crawls the web itself, builds its own index and ranks every answer with
          maths you can inspect.
        </motion.p>

        <motion.div {...fade(0.24)} className="mx-auto mt-10 max-w-2xl text-left">
          <SearchBox size="lg" onSearch={go} autoFocus />
        </motion.div>

        <motion.div {...fade(0.32)} className="mt-5 flex flex-wrap items-center justify-center gap-2">
          <span className="text-sm text-ink-3">Try</span>
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => go(s)}
              className="focus-ring rounded-full border border-line bg-surface/70 px-3.5 py-1.5 text-sm text-ink-2 glass transition hover:-translate-y-0.5 hover:border-brand/40 hover:text-ink"
            >
              {s}
            </button>
          ))}
        </motion.div>

        <motion.div {...fade(0.4)}>
          <LiveStats />
        </motion.div>

        <motion.section {...fade(0.5)} className="mt-20 text-left" aria-labelledby="topics-title">
          <div className="flex items-end justify-between">
            <h2 id="topics-title" className="font-display text-sm font-semibold uppercase tracking-[0.14em] text-ink-3">
              Popular topics
            </h2>
            <span className="hidden items-center gap-1.5 text-xs text-ink-3 sm:inline-flex">
              <Timer size={13} /> Results in milliseconds
            </span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {TOPICS.map(({ title, icon: Icon, query, blurb }) => (
              <button
                key={title}
                onClick={() => go(query)}
                className="focus-ring group relative overflow-hidden rounded-2xl border border-line bg-surface/80 p-4 text-left glass transition-all duration-300 hover:-translate-y-1 hover:border-brand/30 hover:shadow-lift"
              >
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand/15 to-brand-2/15 text-brand-ink transition group-hover:scale-110">
                  <Icon size={18} />
                </span>
                <div className="mt-3 font-display font-semibold">{title}</div>
                <p className="mt-1 text-[13px] leading-snug text-ink-3">{blurb}</p>
                <ArrowUpRight size={16} className="absolute right-3 top-3 text-ink-3 opacity-0 transition group-hover:opacity-100" />
              </button>
            ))}
          </div>
        </motion.section>
      </main>

      <footer className="relative z-10 border-t border-line/70 py-6 text-center text-xs text-ink-3">
        QuirkSearch · built from scratch with FastAPI, SQLite & React · <span className="font-serif italic">Curiosity deserves better results.</span>
      </footer>
    </div>
  );
}
