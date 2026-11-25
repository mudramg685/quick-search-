"""Indexer: turns a crawled page into durable index entries inside ONE transaction.

    CrawledPage ─► analyze_document (tokens, stems, field-weighted tf, |d|)
                ─► BEGIN IMMEDIATE
                     upsert documents row (+ domains)
                     if re-crawl: delete old postings  (trigger: doc_freq −1 per term)
                     insert postings                    (trigger: doc_freq +1 per term)
                     upsert vocabulary, replace links
                   COMMIT          (or ROLLBACK on any error ⇒ never a half-indexed page)

Updating the index is therefore incremental: only the terms of the changed document are
touched; no global rebuild is needed.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..crawler.crawler import CrawledPage
from ..crawler.url_utils import domain_of, url_hash
from ..db.database import transaction
from ..db.repository import Repository
from ..text.analyzer import analyze_document


def index_page(repo: Repository, job_id: int | None, page: CrawledPage, max_chars: int = 60_000) -> int:
    parsed = page.parsed
    content = parsed.body_text[:max_chars]
    title = parsed.title[:500] or page.final_url
    doc = analyze_document(title, parsed.headings, content)
    key = url_hash(page.final_url)

    fields = dict(
        url=page.final_url, url_hash=key, domain=domain_of(page.final_url), crawl_job_id=job_id,
        title=title, description=parsed.description[:1000], headings="\n".join(parsed.headings),
        content=content, content_hash=page.content_hash, language=parsed.language or None,
        status_code=page.status_code, depth=page.depth, doc_length=doc.length,
        fetch_ms=round(page.elapsed_ms, 2), fetched_at=page.fetched_at,
        indexed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    with repo.connect() as conn, transaction(conn):
        old = repo.get_document_by_hash(conn, key)
        if old:
            old_surface = analyze_document(old["title"], [], old["content"]).surface_counts
            repo.remove_document_postings(conn, old["id"], old_surface)
        doc_id = repo.save_document(conn, existing_id=old["id"] if old else None, fields=fields)
        repo.save_postings(conn, doc_id, doc.term_freqs, doc.surface_counts, doc.surface_to_term)
        repo.save_links(conn, doc_id, page.outlinks)
    return doc_id


def delete_document(repo: Repository, doc_id: int) -> bool:
    with repo.connect() as conn, transaction(conn):
        row = conn.execute("SELECT title, content FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row is None:
            return False
        repo.remove_document_postings(conn, doc_id, analyze_document(row["title"], [], row["content"]).surface_counts)
        repo.delete_document_row(conn, doc_id)
    return True
