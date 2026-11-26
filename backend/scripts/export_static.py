"""Export the real index to JSON for the static (GitHub Pages) build of the frontend.

In static mode the browser runs the same BM25 / Top-K / snippet logic in JavaScript over this
snapshot of the inverted index, so the hosted demo searches genuinely – it just cannot crawl.

    python scripts/export_static.py   →   frontend/static-data/index.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from quirksearch.config import get_settings  # noqa: E402
from quirksearch.db.repository import Repository  # noqa: E402
from quirksearch.text.stopwords import STOP_WORDS  # noqa: E402



def main() -> None:
    settings = get_settings()
    repo = Repository(settings.db_path)
    index, _ = repo.load_index()
    ids = sorted(index.doc_len)
    pos = {doc_id: i for i, doc_id in enumerate(ids)}
    rows = repo.fetch_documents(ids)
    with repo.connect() as conn:
        # full text: quoted phrases are verified against the whole page, as on the server
        full = {r[0]: r[1] or "" for r in conn.execute("SELECT id, content FROM documents")}
        fetched = {r[0]: r[1] for r in conn.execute("SELECT id, fetched_at FROM documents")}
        vocab = {w: [t, f] for w, t, f in conn.execute(
            "SELECT v.word, t.term, v.frequency FROM vocabulary v JOIN terms t ON t.id = v.term_id")}

    docs = [{"id": d, "url": rows[d]["url"], "domain": rows[d]["domain"], "title": rows[d]["title"],
             "description": rows[d]["description"], "len": index.doc_len[d], "content": full[d],
             "fetched_at": fetched[d]} for d in ids]
    postings = {t: [[pos[d], tf] for d, tf in sorted(p.items())] for t, p in index.postings.items()}

    stats = repo.stats()
    stats["recent_searches"] = repo.recent_searches(10)
    stats["recent_jobs"] = repo.list_jobs(6)
    stats["recent_errors"] = repo.recent_errors(8)
    total, recent_docs = repo.list_documents(6, 0)
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "k1": settings.bm25_k1, "b": settings.bm25_b, "stopwords": sorted(STOP_WORDS),
        "docs": docs, "postings": postings, "vocab": vocab,
        "stats": stats, "documents": {"total": total, "documents": recent_docs},
    }
    dest = ROOT / "frontend" / "static-data" / "index.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    repo.close()
    print(f"{len(docs)} docs, {len(postings)} terms, {len(vocab)} words -> {dest} ({dest.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
