import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogoMark, Wordmark } from "../components/Logo";
import { SearchBox } from "../components/SearchBox";
import { SettingsButton } from "../components/TopBar";
import { REPO_URL, STATIC, api } from "../lib/api";
import { fmtInt, fmtMs } from "../lib/format";
import { addHistory, getSettings } from "../lib/settings";

const WANDER = [
  ["networks", "http tcp dns protocol"],
  ["databases", "database transactions index"],
  ["algorithms", "heap trie hash table graph"],
  ["search engines", "inverted index ranking"],
  ["oddities", "octopus black holes sourdough"],
];
const CURIOUS = ["octopus neurons", "write ahead log", "sourdough fermentation", "black holes", "bm25 ranking", "tcp handshake", "porter stemming"];

function IndexStatus() {
  const [stats, setStats] = useState(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const ctrl = new AbortController();
    const load = () => api.stats(ctrl.signal).then((s) => { setStats(s); setFailed(false); }).catch((e) => e.name !== "AbortError" && setFailed(true));
    load();
    const id = setInterval(load, 15000);
    return () => { ctrl.abort(); clearInterval(id); };
  }, []);

  if (failed) return <span className="text-ink-3"><span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: "var(--status-critical)" }} />Backend offline</span>;
  if (!stats) return <span className="skeleton inline-block h-3 w-64 align-middle" />;
  return (
    <span className="text-ink-3">
      <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: "var(--status-good)" }} />
      {STATIC ? "Snapshot of " : ""}{fmtInt(stats.documents)} pages · {fmtInt(stats.terms)} terms · {fmtInt(stats.domains)} {stats.domains === 1 ? "site" : "sites"}
      {stats.avg_latency_ms != null && <> · {fmtMs(stats.avg_latency_ms)} average</>}
    </span>
  );
}

export default function Home() {
  const navigate = useNavigate();
  const [feeling, setFeeling] = useState(false);
  const go = (q) => navigate(`/search?q=${encodeURIComponent(q)}`);

  useEffect(() => { document.title = "QuirkSearch"; }, []);

  // "I'm feeling curious": straight to the best page for the query (or a random one).
  const curious = async () => {
    const input = document.querySelector("input[role=combobox]");
    const q = input?.value.trim() || CURIOUS[Math.floor(Math.random() * CURIOUS.length)];
    setFeeling(true);
    try {
      const res = await api.search(q, { pageSize: 1, autocorrect: getSettings().autocorrect });
      if (res.results[0]) {
        addHistory(q);
        window.location.assign(res.results[0].url);
        return;
      }
      go(q);
    } catch {
      go(q);
    } finally {
      setFeeling(false);
    }
  };

  const button = "focus-ring rounded-full border border-line bg-surface px-5 py-2.5 text-[14px] text-ink transition hover:border-ink-3 hover:shadow-soft disabled:opacity-60";

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-end gap-4 px-4 py-3 sm:px-6">
        <Link to="/dashboard" className="focus-ring rounded text-sm text-ink-2 underline-offset-[6px] hover:text-ink hover:underline">Dashboard</Link>
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="focus-ring hidden rounded text-sm text-ink-2 underline-offset-[6px] hover:text-ink hover:underline sm:inline">Source</a>
        <SettingsButton />
      </header>

      <main className="flex flex-1 flex-col items-center px-4 pb-16 pt-[11vh] sm:px-6">
        <h1 className="flex items-start gap-2">
          <Wordmark className="text-[64px] sm:text-[92px]" />
          <LogoMark size={30} className="mt-1 text-brand sm:mt-2" />
          <span className="sr-only">QuirkSearch</span>
        </h1>
        <p className="mt-4 font-read text-[17px] italic text-ink-2">Curiosity deserves better results.</p>

        <div className="mt-9 w-full max-w-[600px]">
          <SearchBox size="lg" onSearch={go} autoFocus />
        </div>

        <div className="mt-7 flex gap-3">
          <button className={button} onClick={() => { const v = document.querySelector("input[role=combobox]")?.value.trim(); v && go(v); }}>
            QuirkSearch
          </button>
          <button className={button} onClick={curious} disabled={feeling}>
            {feeling ? "Wandering…" : "I'm feeling curious"}
          </button>
        </div>

        <p className="mt-10 max-w-[600px] text-center font-read text-[16px] leading-relaxed text-ink-2">
          <span className="italic text-ink-3">Wander into </span>
          {WANDER.map(([label, q], i) => (
            <span key={label}>
              {i > 0 && <span className="text-ink-3"> · </span>}
              <button onClick={() => go(q)} className="result-title focus-ring rounded-sm underline-offset-4 hover:underline">{label}</button>
            </span>
          ))}
        </p>
      </main>

      <footer className="border-t border-line bg-surface-2/60 text-[13px]">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-2 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <IndexStatus />
          <div className="flex gap-5 text-ink-3">
            <span>Own crawler, own index, BM25 ranking</span>
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="focus-ring rounded hover:text-ink hover:underline sm:hidden">Source</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
