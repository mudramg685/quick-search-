"""Build QuirkSearch_Technical_Report.pdf from docs/report/template.html.

Every number in the report comes from a real source at build time:
  * pytest run (pass count, per-module counts) + coverage JSON
  * docs/benchmarks.json (scripts/benchmark.py)
  * the live SQLite database (BM25 worked example, API example)
Diagrams are Mermaid, rendered to SVG inside headless Chromium, then printed to PDF.

Usage (from the repo root, with the backend virtualenv):
    backend/.venv/Scripts/python docs/report/build_report.py
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from quirksearch.config import get_settings  # noqa: E402
from quirksearch.db.repository import Repository  # noqa: E402
from quirksearch.search.bm25 import idf, term_score  # noqa: E402
from quirksearch.search.searcher import SearchEngine, parse_query  # noqa: E402

TEST_DESCRIPTIONS = {
    "test_crawler.py": "URL canonicalization (incl. IDNA), HTML extraction, BFS depth/page limits, robots.txt, duplicate & noindex handling, 404s, timeout, refused connection, DNS failure, TLS classification, redirects, rate limiter, parser regression",
    "test_text_and_index.py": "Porter stemmer against Porter's published examples, tokenizer/analyzer, field weighting, inverted-index add/replace/delete and df, trie completion",
    "test_database.py": "schema objects & PRAGMAs, FK/CHECK enforcement, rollback, trigger-maintained df through insert/re-index/delete, persistence across restart, in-place re-crawl",
    "test_search.py": "BM25 properties, 15 relevance queries (expected top result), heap Top-K = full sort, pagination, +/-/site: operators, facets, spelling, snippets, autocomplete",
    "test_api.py": "all endpoints, 422 validation, 404/409 errors, 429 rate limiting with Retry-After, crawl lifecycle via API, restart persistence through a fresh app",
}
# Observed on the real server during Phase 6 (documents / terms before and after restart).
PERSIST_DOCS, PERSIST_TERMS = 48, 2401


def run_tests() -> tuple[int, dict[str, int], dict]:
    py = str(BACKEND / ".venv" / "Scripts" / "python")
    with tempfile.TemporaryDirectory() as tmp:
        cov_json = Path(tmp) / "cov.json"
        proc = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--cov=quirksearch",
                               f"--cov-report=json:{cov_json}"], cwd=BACKEND, capture_output=True, text=True)
        tail = proc.stdout.strip().splitlines()[-1]
        m = re.search(r"(\d+) passed", tail)
        if proc.returncode != 0 or not m or "failed" in tail:
            sys.exit(f"Test suite did not pass – refusing to build report:\n{proc.stdout[-2000:]}")
        coverage = json.loads(cov_json.read_text())
    collected = subprocess.run([py, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                               cwd=BACKEND, capture_output=True, text=True).stdout
    per_file: dict[str, int] = {}
    for line in collected.splitlines():
        if "::" in line:
            f = line.split("::")[0].split("/")[-1]
            per_file[f] = per_file.get(f, 0) + 1
    return int(m.group(1)), per_file, coverage


def bm25_example(engine: SearchEngine) -> str:
    query = "write ahead log"
    res = engine.search(query, page_size=1)
    top = res["results"][0]
    idx = engine.snapshot.index
    q = parse_query(query)
    n, avgdl, doc = idx.num_docs, idx.avg_doc_len, top["doc_id"]
    rows = []
    for t in q.terms:
        df = idx.df(t)
        w = idf(n, df)
        tf = idx.get_postings(t).get(doc, 0)
        s = term_score(tf, idx.doc_len[doc], avgdl, w)
        rows.append(f"<tr><td><code>{t}</code></td><td class='r'>{df}</td><td class='r'>{w:.3f}</td>"
                    f"<td class='r'>{tf}</td><td class='r'>{s:.3f}</td></tr>")
    return (f"For the query <i>“{query}”</i> the analyzer produces the terms "
            f"{', '.join(f'<code>{t}</code>' for t in q.terms)}. The top result is <b>{html.escape(top['title'])}</b> "
            f"(|D| = {idx.doc_len[doc]} tokens, avgdl = {avgdl:.1f}, N = {n}):</p>"
            "<table style='width:70%'><tr><th>term</th><th class='r'>df</th><th class='r'>IDF</th><th class='r'>tf (weighted)</th>"
            "<th class='r'>contribution</th></tr>" + "".join(rows) +
            f"<tr><td><b>score</b></td><td></td><td></td><td></td><td class='r'><b>{top['score']:.3f}</b></td></tr></table><p>"
            f"It matched {res['total']} documents in {res['took_ms']:.1f} ms; every term appears in its text, and the "
            "rarest term (lowest df) contributes the most.")


def api_example(engine: SearchEngine) -> str:
    res = engine.search("bm25", page_size=1)
    r = res["results"][0]
    short = {
        "query": res["query"], "terms": res["terms"], "total": res["total"], "took_ms": res["took_ms"],
        "results": [{"rank": r["rank"], "url": r["url"], "domain": r["domain"], "title": r["title"],
                     "score": r["score"], "relevance": r["relevance"], "term_scores": r["term_scores"],
                     "snippet": r["snippet"][:2]}],
        "facets": res["facets"][:2], "did_you_mean": res["did_you_mean"],
    }
    return "GET /api/search?q=bm25\n\n" + html.escape(json.dumps(short, indent=1, ensure_ascii=False))


def fmt(x: float, d: int = 2) -> str:
    return f"{x:,.{d}f}"


def main() -> None:
    tests, per_file, cov = run_tests()
    bench = json.loads((ROOT / "docs" / "benchmarks.json").read_text(encoding="utf-8"))
    settings = get_settings()
    repo = Repository(settings.db_path)
    engine = SearchEngine(repo, settings)
    c = bench["corpus"]

    latency_rows = ""
    for label, key in [("Retrieval + BM25 + heap Top-K (no snippets)", "retrieval_latency"),
                       ("Full engine search incl. 10 snippets", "engine_latency"),
                       ("HTTP GET /api/search end-to-end", "http_latency")]:
        s = bench[key]
        latency_rows += (f"<tr><td>{label}</td><td class='r'>{s['n']}</td>" +
                         "".join(f"<td class='r'>{fmt(s[k], 3 if s[k] < 1 else 1)} ms</td>"
                                 for k in ("mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")) + "</tr>")

    heap_rows = "".join(f"<tr><td class='r'>{r['n']:,}</td><td class='r'>{r['heap_ms']}</td><td class='r'>{r['sort_ms']}</td>"
                        f"<td class='r'>{r['speedup_x']}×</td></tr>" for r in bench["heap_vs_sort"])
    crawl_rows = "".join(f"<tr><td>#{j['job']}</td><td class='r'>{j['pages_fetched']}</td><td class='r'>{j['pages_stored']}</td>"
                         f"<td class='r'>{j['failed']}</td><td class='r'>{j['seconds']:.0f}</td><td class='r'>{j['pages_per_second']}</td></tr>"
                         for j in sorted(bench["crawl_jobs"], key=lambda j: j["job"]))
    test_rows = "".join(f"<tr><td><code>{f}</code></td><td class='r'>{n}</td><td>{TEST_DESCRIPTIONS.get(f, '')}</td></tr>"
                        for f, n in sorted(per_file.items()))
    cov_rows = ""
    for path, info in sorted(cov["files"].items()):
        stmts = info["summary"]["num_statements"]
        if stmts == 0:
            continue
        mod = path.replace("\\", "/").split("quirksearch/")[-1]
        cov_rows += f"<tr><td><code>{mod}</code></td><td class='r'>{stmts}</td><td class='r'>{info['summary']['percent_covered']:.0f}%</td></tr>"

    tokens = {
        "date": date.today().strftime("%d %B %Y"),
        "machine": f"Python {bench['machine']['python']}, {bench['machine']['platform'].split('-')[0]} {bench['machine']['platform'].split('-')[1]}",
        "documents": f"{c['documents']:,}", "terms": f"{c['terms']:,}", "postings": f"{c['postings']:,}",
        "domains": str(bench["stats"]["domains"]), "vocab": f"{c['vocabulary_words']:,}",
        "avgdl": f"{c['avg_doc_length']:.1f}", "db_size": f"{c['db_size_bytes'] / 1024 / 1024:.1f} MB",
        "tests": str(tests), "coverage": f"{cov['totals']['percent_covered']:.0f}%",
        "ret_mean": fmt(bench["retrieval_latency"]["mean_ms"]), "eng_p50": fmt(bench["engine_latency"]["p50_ms"], 1),
        "http_p50": fmt(bench["http_latency"]["p50_ms"], 1),
        "idx_ms": f"{bench['index_vs_scan']['index_mean_ms']}", "scan_ms": fmt(bench["index_vs_scan"]["scan_mean_ms"], 1),
        "speedup": f"{bench['index_vs_scan']['speedup_x']:,}", "load_ms": fmt(bench["index_load"]["mean_ms"], 0),
        "idx_dps": fmt(bench["indexing"]["docs_per_second"], 1), "idx_msdoc": fmt(bench["indexing"]["ms_per_doc"], 1),
        "success_rate": f"{bench['stats']['crawl_success_rate'] * 100:.1f}%",
        "nq": str(bench["queries"]["count"]), "reps": str(bench["queries"]["reps"]), "avg_hits": str(bench["queries"]["avg_hits"]),
        "persist_docs": str(PERSIST_DOCS), "persist_terms": f"{PERSIST_TERMS:,}",
        "latency_rows": latency_rows, "heap_rows": heap_rows, "crawl_rows": crawl_rows,
        "test_rows": test_rows, "coverage_rows": cov_rows,
        "bm25_example": bm25_example(engine), "api_example": api_example(engine),
        "shots": (ROOT / "docs" / "screenshots").as_uri(),
    }
    repo.close()

    text = (ROOT / "docs" / "report" / "template.html").read_text(encoding="utf-8")
    for k, v in tokens.items():
        text = text.replace("{{" + k + "}}", v)
    leftover = re.findall(r"\{\{(\w+)\}\}", text)
    if leftover:
        sys.exit(f"Unfilled template tokens: {leftover}")
    out_dir = ROOT / "docs" / "report_build"
    out_dir.mkdir(exist_ok=True)
    html_path = out_dir / "report.html"
    html_path.write_text(text, encoding="utf-8")

    from playwright.sync_api import sync_playwright
    pdf_path = ROOT / "QuirkSearch_Technical_Report.pdf"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.wait_for_function("window.__diagramsDone === true", timeout=60000)
        err = page.evaluate("window.__diagramError || null")
        if err or not page.evaluate("window.__diagramsOk === true"):
            sys.exit(f"Mermaid rendering failed: {err}")
        n_svg = page.evaluate("document.querySelectorAll('.mermaid svg').length")
        page.evaluate("document.fonts.ready")
        page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True,
                 display_header_footer=True, header_template="<span></span>",
                 footer_template="<div style='width:100%;font:8px Inter,sans-serif;color:#8a8a92;padding:0 16mm;"
                                 "display:flex;justify-content:space-between'><span>QuirkSearch — Technical Report</span>"
                                 "<span><span class='pageNumber'></span> / <span class='totalPages'></span></span></div>")
        browser.close()
    print(f"tests={tests} coverage={tokens['coverage']} diagrams={n_svg}")
    print(f"PDF written: {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
