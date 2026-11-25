"""Phase 4 – schema constraints, transactions, triggers, persistence across restarts."""
from __future__ import annotations

import sqlite3
from collections import Counter

import pytest

from quirksearch.crawler.crawler import CrawledPage, content_fingerprint
from quirksearch.crawler.parser import ParsedPage
from quirksearch.db.database import transaction
from quirksearch.db.repository import Repository
from quirksearch.index.indexer import delete_document, index_page
from quirksearch.services.crawl_service import CrawlService


def make_page(url: str, title: str, body: str, headings=None, links=None) -> CrawledPage:
    parsed = ParsedPage(title=title, description=body[:50], headings=headings or [], body_text=body, links=links or [])
    return CrawledPage(url=url, final_url=url, depth=0, status_code=200, parsed=parsed,
                       content_hash=content_fingerprint(parsed), fetched_at="2026-11-25T10:00:00+00:00",
                       elapsed_ms=12.5, outlinks=links or [])


def df_consistent(repo: Repository) -> bool:
    """terms.doc_freq must equal the real number of postings for every term."""
    with repo.connect() as conn:
        bad = conn.execute("SELECT COUNT(*) FROM terms t WHERE doc_freq != "
                           "(SELECT COUNT(*) FROM postings p WHERE p.term_id = t.id)").fetchone()[0]
    return bad == 0


@pytest.fixture
def repo(settings):
    r = Repository(settings.db_path)
    yield r
    r.close()


def test_schema_objects_exist(repo):
    with repo.connect() as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
        assert {"documents", "terms", "postings", "domains", "crawl_jobs", "crawl_job_seeds",
                "crawl_errors", "search_logs", "vocabulary", "links"} <= names
        assert {"idx_postings_doc", "idx_documents_domain", "trg_postings_insert", "trg_postings_delete"} <= names
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_constraints_are_enforced(repo):
    with repo.connect() as conn:
        with pytest.raises(sqlite3.IntegrityError):  # FK: posting for a non-existent document
            conn.execute("INSERT INTO terms(term) VALUES ('x')")
            conn.execute("INSERT INTO postings(term_id, doc_id, term_freq) VALUES (1, 999, 1)")
        with pytest.raises(sqlite3.IntegrityError):  # CHECK: invalid job status
            conn.execute("INSERT INTO crawl_jobs(status, max_depth, max_pages) VALUES ('exploded', 1, 1)")
        with pytest.raises(sqlite3.IntegrityError):  # CHECK: depth range
            conn.execute("INSERT INTO crawl_jobs(max_depth, max_pages) VALUES (99, 1)")
        with pytest.raises(sqlite3.IntegrityError):  # CHECK: unknown error type
            conn.execute("INSERT INTO crawl_jobs(max_depth, max_pages) VALUES (1, 1)")
            conn.execute("INSERT INTO crawl_errors(job_id, url, error_type) VALUES (1, 'u', 'gremlins')")


def test_transaction_rolls_back(repo):
    with repo.connect() as conn:
        with pytest.raises(RuntimeError):
            with transaction(conn):
                conn.execute("INSERT INTO domains(name) VALUES ('rollback.test')")
                raise RuntimeError("simulated crash mid-transaction")
        assert conn.execute("SELECT COUNT(*) FROM domains WHERE name='rollback.test'").fetchone()[0] == 0


def test_index_page_postings_triggers_and_reindex(repo):
    d1 = index_page(repo, None, make_page("http://a.test/1", "Databases", "database index database btree"))
    d2 = index_page(repo, None, make_page("http://a.test/2", "Networks", "network database protocol",
                                          links=["http://a.test/1"]))
    with repo.connect() as conn:
        df = dict(conn.execute("SELECT term, doc_freq FROM terms").fetchall())
        assert df["databas"] == 2 and df["network"] == 1 and df["btree"] == 1
        tf = conn.execute("SELECT term_freq FROM postings p JOIN terms t ON t.id=p.term_id "
                          "WHERE t.term='databas' AND p.doc_id=?", (d1,)).fetchone()[0]
        assert tf == 2 + 3  # body occurrences + title weight
        assert conn.execute("SELECT COUNT(*) FROM links WHERE source_doc_id=?", (d2,)).fetchone()[0] == 1
    assert df_consistent(repo)

    # Re-crawl with new content: same doc id, old postings replaced, orphan terms removed
    d1b = index_page(repo, None, make_page("http://a.test/1", "Databases", "relational tables"))
    assert d1b == d1
    with repo.connect() as conn:
        df = dict(conn.execute("SELECT term, doc_freq FROM terms").fetchall())
        assert "btree" not in df and df["databas"] == 2  # title + doc 2
        assert df["relat"] == 1
        vocab = dict(conn.execute("SELECT word, frequency FROM vocabulary").fetchall())
        assert "btree" not in vocab and vocab["relational"] == 1
    assert df_consistent(repo)

    # Deletion cascades to postings, triggers keep df exact
    assert delete_document(repo, d2)
    with repo.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM postings WHERE doc_id=?", (d2,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM links").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM terms WHERE term='network'").fetchone()[0] == 0
    assert df_consistent(repo)


def test_crawl_persists_across_restart(site, settings):
    repo = Repository(settings.db_path)
    reloads = []
    service = CrawlService(repo, settings, on_index_changed=lambda: reloads.append(1))
    job_id = service.run_blocking([f"{site}/corpus/index.html"], max_depth=2, max_pages=100)

    job = repo.get_job(job_id)
    assert job["status"] == "completed" and job["pages_stored"] >= 39
    assert job["errors_by_type"].get("robots") == 1 and job["errors_by_type"].get("duplicate") == 1
    assert job["errors_by_type"].get("http_error") == 1
    index_before, trie_before = repo.load_index()
    assert reloads  # in-memory index refresh hook fired

    # "Restart": a brand-new Repository object on the same database file
    repo.close()
    repo2 = Repository(settings.db_path)
    index_after, trie_after = repo2.load_index()
    assert index_after.num_docs == index_before.num_docs >= 39
    assert index_after.postings == index_before.postings
    assert index_after.doc_len == index_before.doc_len
    assert trie_after.complete("data", 3) == trie_before.complete("data", 3)
    assert df_consistent(repo2)
    stats = repo2.stats()
    assert stats["documents"] == index_after.num_docs and stats["terms"] == index_after.num_terms

    # Re-crawling the same site updates in place instead of duplicating rows
    CrawlService(repo2, settings, lambda: None).run_blocking([f"{site}/corpus/index.html"], 2, 100)
    assert repo2.load_index()[0].num_docs == index_after.num_docs
    assert df_consistent(repo2)
    repo2.close()
