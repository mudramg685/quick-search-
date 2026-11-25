"""Measure QuirkSearch performance on the real database and write docs/benchmarks.json.

    python scripts/benchmark.py [--api http://127.0.0.1:8000]

Measurements (all wall-clock, time.perf_counter):
  1. index load      – rebuilding the in-memory inverted index + trie from SQLite
  2. engine latency  – SearchEngine.search() (retrieval + BM25 + Top-K + snippets) per query
  3. retrieval only  – term-at-a-time BM25 accumulation + heap Top-K, no snippets/DB
  4. HTTP latency    – GET /api/search end to end through FastAPI (if --api reachable)
  5. index vs scan   – inverted-index lookup vs re-tokenizing every document per query
  6. heap vs sort    – heapq.nlargest(k) vs sorted() on synthetic score sets
  7. indexing speed  – analyze + transactional insert of every stored page into a fresh DB
  8. crawl speed     – pages/second of completed crawl jobs (from crawl_jobs timestamps)
"""
from __future__ import annotations

import argparse
import dataclasses
import heapq
import json
import platform
import random
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from quirksearch.config import get_settings  # noqa: E402
from quirksearch.crawler.crawler import CrawledPage  # noqa: E402
from quirksearch.crawler.parser import ParsedPage  # noqa: E402
from quirksearch.db.repository import Repository  # noqa: E402
from quirksearch.index.indexer import index_page  # noqa: E402
from quirksearch.search.bm25 import idf, term_score  # noqa: E402
from quirksearch.search.searcher import SearchEngine, parse_query  # noqa: E402
from quirksearch.text.analyzer import analyze  # noqa: E402

QUERIES = [
    "bm25", "bm25 ranking", "inverted index", "tcp handshake", "write ahead log", "python list comprehension",
    "query planner index", "foreign key constraints", "dns resolver cache", "heap priority queue", "octopus",
    "sourdough fermentation", "hash table collisions", "breadth first search", "porter stemming algorithm",
    "rest api status codes", "python dictionaries", "sqlite when to use", "acid durability", "load balancing",
    "black holes", "full text search", "atomic commit", "tf idf weighting", "robots txt", "python classes",
    "database normalization", "rate limiting token bucket", "tls handshake", "pagerank random surfer",
    "data structures", "error handling exceptions", "virtual environments", "module import", "sorting algorithms",
    "binary search", "transactions isolation", "content delivery network", "http methods", "graph traversal",
]


def pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def summary(values: list[float]) -> dict:
    return {"n": len(values), "mean_ms": round(statistics.mean(values), 3), "p50_ms": round(pct(values, 50), 3),
            "p95_ms": round(pct(values, 95), 3), "p99_ms": round(pct(values, 99), 3),
            "min_ms": round(min(values), 3), "max_ms": round(max(values), 3)}


def timed(fn, *a, **kw) -> tuple[float, object]:
    t0 = time.perf_counter()
    out = fn(*a, **kw)
    return (time.perf_counter() - t0) * 1000, out


def retrieval_only(engine: SearchEngine, query: str, k: int = 10):
    idx = engine.snapshot.index
    q = parse_query(query)
    n, avgdl = idx.num_docs, idx.avg_doc_len
    scores: dict[int, float] = {}
    for t in q.terms:
        w = idf(n, idx.df(t))
        for d, tf in idx.get_postings(t).items():
            scores[d] = scores.get(d, 0.0) + term_score(tf, idx.doc_len[d], avgdl, w)
    return heapq.nlargest(k, scores.items(), key=lambda kv: kv[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--reps", type=int, default=20)
    args = ap.parse_args()
    settings = get_settings()
    repo = Repository(settings.db_path)
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "machine": {"python": platform.python_version(), "platform": platform.platform(),
                             "processor": platform.processor() or platform.machine()}}

    # 1. index load ------------------------------------------------------------------
    loads = [timed(repo.load_index)[0] for _ in range(5)]
    index, trie = repo.load_index()
    out["corpus"] = {"documents": index.num_docs, "terms": index.num_terms,
                     "postings": sum(len(p) for p in index.postings.values()),
                     "avg_doc_length": round(index.avg_doc_len, 1), "vocabulary_words": trie.size,
                     "db_size_bytes": Path(settings.db_path).stat().st_size}
    out["index_load"] = summary(loads)

    # 2./3. engine + retrieval-only latency -------------------------------------------
    engine = SearchEngine(repo, settings)
    for q in QUERIES:  # warm caches (LRU stemmer, page cache)
        engine.search(q)
    eng, ret, totals = [], [], []
    for _ in range(args.reps):
        for q in QUERIES:
            ms, res = timed(engine.search, q)
            eng.append(ms)
            totals.append(res["total"])
            ret.append(timed(retrieval_only, engine, q)[0])
    out["engine_latency"] = summary(eng)
    out["retrieval_latency"] = summary(ret)
    out["queries"] = {"count": len(QUERIES), "reps": args.reps, "avg_hits": round(statistics.mean(totals), 1),
                      "zero_hit_queries": sum(1 for q in QUERIES if engine.search(q)["total"] == 0)}

    # 4. HTTP end-to-end ---------------------------------------------------------------
    try:
        with httpx.Client(base_url=args.api, timeout=10) as client:
            client.get("/api/health").raise_for_status()
            http = []
            for _ in range(5):
                for q in QUERIES:
                    ms, r = timed(client.get, "/api/search", params={"q": q})
                    if r.status_code == 429:
                        time.sleep(1)
                        continue
                    http.append(ms)
                time.sleep(1.5)  # stay within the API's token-bucket rate limit
            out["http_latency"] = summary(http)
    except httpx.HTTPError as exc:
        out["http_latency"] = {"skipped": f"API not reachable: {exc}"}

    # 5. inverted index vs linear scan --------------------------------------------------
    docs = repo.fetch_documents(list(index.doc_len))
    scan_q = QUERIES[:10]
    scan_times, index_times = [], []
    for q in scan_q:
        terms = set(analyze(q))
        t0 = time.perf_counter()
        hits_scan = {d for d, row in docs.items() if terms & set(analyze(row["title"] + " " + row["content"]))}
        scan_times.append((time.perf_counter() - t0) * 1000)
        t0 = time.perf_counter()
        hits_idx = set().union(*(index.get_postings(t).keys() for t in terms)) if terms else set()
        index_times.append((time.perf_counter() - t0) * 1000)
        assert hits_idx <= set(docs) and len(hits_idx) >= len(hits_scan) * 0.9
    out["index_vs_scan"] = {"queries": len(scan_q), "scan_mean_ms": round(statistics.mean(scan_times), 3),
                            "index_mean_ms": round(statistics.mean(index_times), 4),
                            "speedup_x": round(statistics.mean(scan_times) / max(statistics.mean(index_times), 1e-6))}

    # 6. heap Top-K vs full sort ----------------------------------------------------------
    rnd = random.Random(42)
    heap_rows = []
    for n in (1_000, 10_000, 100_000, 1_000_000):
        items = [(i, rnd.random()) for i in range(n)]
        h = min(timed(heapq.nlargest, 10, items, key=lambda kv: kv[1])[0] for _ in range(3))
        s = min(timed(lambda: sorted(items, key=lambda kv: kv[1], reverse=True)[:10])[0] for _ in range(3))
        heap_rows.append({"n": n, "k": 10, "heap_ms": round(h, 3), "sort_ms": round(s, 3), "speedup_x": round(s / h, 2)})
    out["heap_vs_sort"] = heap_rows

    # 7. indexing throughput into a fresh database ------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Repository(Path(tmp) / "bench.db")
        full = {}
        with repo.connect() as conn:
            for r in conn.execute("SELECT url, title, description, headings, content, content_hash FROM documents"):
                full[r["url"]] = dict(r)
        t0 = time.perf_counter()
        for url, r in full.items():
            parsed = ParsedPage(title=r["title"], description=r["description"], headings=r["headings"].split("\n"),
                                body_text=r["content"])
            index_page(fresh, None, CrawledPage(url=url, final_url=url, depth=0, status_code=200, parsed=parsed,
                                                content_hash=r["content_hash"], fetched_at="2026-01-01T00:00:00+00:00",
                                                elapsed_ms=0))
        secs = time.perf_counter() - t0
        fresh.close()
        out["indexing"] = {"documents": len(full), "seconds": round(secs, 3), "docs_per_second": round(len(full) / secs, 1),
                           "ms_per_doc": round(secs * 1000 / len(full), 2)}

    # 8. crawl throughput from real jobs ----------------------------------------------------
    jobs = []
    for j in repo.list_jobs(50):
        if j["status"] == "completed" and j["started_at"] and j["finished_at"] and j["pages_fetched"]:
            dur = (datetime.fromisoformat(j["finished_at"].replace("Z", "+00:00"))
                   - datetime.fromisoformat(j["started_at"].replace("Z", "+00:00"))).total_seconds()
            jobs.append({"job": j["id"], "pages_fetched": j["pages_fetched"], "pages_stored": j["pages_stored"],
                         "failed": j["pages_failed"], "seconds": dur,
                         "pages_per_second": round(j["pages_fetched"] / dur, 2) if dur else None})
    out["crawl_jobs"] = jobs
    out["stats"] = {k: v for k, v in repo.stats().items() if k in
                    ("documents", "domains", "terms", "postings", "links", "pages_fetched", "failed_requests",
                     "crawl_success_rate", "errors_by_type", "searches")}

    dest = Path(__file__).resolve().parents[2] / "docs" / "benchmarks.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"\nwritten to {dest}")


if __name__ == "__main__":
    main()
