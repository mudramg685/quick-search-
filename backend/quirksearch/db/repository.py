"""Repository layer: every SQL statement in QuirkSearch lives in this module.

Callers never build SQL strings; they call intention-revealing methods. All statements use
``?`` parameters (no string interpolation of user data ⇒ no SQL injection). Porting to
PostgreSQL means re-implementing this one module (placeholders and upsert syntax differ).
"""
from __future__ import annotations

import sqlite3
import threading
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from ..index.inverted_index import InvertedIndex
from ..index.trie import Trie
from .database import connect, init_schema, transaction

_CHUNK = 500  # stay well below SQLite's bound-parameter limit
SNIPPET_SCAN_CHARS = 25_000
NETWORK_ERROR_TYPES = ("dns", "connection", "tls", "timeout", "http_error", "protocol", "redirect", "too_large", "internal")


def _chunks(items: list, n: int = _CHUNK) -> Iterable[list]:
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class Repository:
    def __init__(self, db_path: Path | str):
        self.db_path = db_path
        self._local = threading.local()
        self._all: list[sqlite3.Connection] = []
        self._all_lock = threading.Lock()
        with self.connect() as conn:
            init_schema(conn)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield this thread's persistent connection (a tiny per-thread connection pool).

        Opening a SQLite connection (file open, WAL shared-memory setup, PRAGMAs) costs
        milliseconds; a search touches the database twice, so reusing one connection per
        worker thread removes that cost from every request. Transactions stay explicit
        (BEGIN … COMMIT/ROLLBACK), so a reused connection never carries an open transaction.
        """
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = connect(self.db_path)
            self._local.conn = conn
            with self._all_lock:
                self._all.append(conn)
        yield conn

    def close(self) -> None:
        with self._all_lock:
            for conn in self._all:
                try:
                    conn.close()
                except sqlite3.ProgrammingError:
                    pass
            self._all.clear()
        self._local = threading.local()

    # =============================================================== crawl jobs
    def create_crawl_job(self, seeds: list[str], max_depth: int, max_pages: int) -> int:
        with self.connect() as conn, transaction(conn):
            cur = conn.execute("INSERT INTO crawl_jobs(max_depth, max_pages) VALUES (?, ?)", (max_depth, max_pages))
            job_id = cur.lastrowid
            conn.executemany("INSERT OR IGNORE INTO crawl_job_seeds(job_id, url) VALUES (?, ?)",
                             [(job_id, s) for s in seeds])
        return job_id

    def mark_job_running(self, job_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE crawl_jobs SET status='running', started_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                         "WHERE id=?", (job_id,))

    def update_job_progress(self, job_id: int, discovered: int, fetched: int, stored: int, failed: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE crawl_jobs SET pages_discovered=?, pages_fetched=?, pages_stored=?, pages_failed=? "
                         "WHERE id=?", (discovered, fetched, stored, failed, job_id))

    def finish_job(self, job_id: int, status: str, error: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE crawl_jobs SET status=?, error_message=?, "
                         "started_at=COALESCE(started_at, strftime('%Y-%m-%dT%H:%M:%SZ','now')), "
                         "finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?", (status, error, job_id))

    def fail_stale_jobs(self) -> int:
        """Crash recovery: jobs still 'running'/'queued' at startup can never finish."""
        with self.connect() as conn:
            return conn.execute(
                "UPDATE crawl_jobs SET status='failed', error_message='Interrupted by server restart', "
                "started_at=COALESCE(started_at, created_at), finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                "WHERE status IN ('running','queued')").rowcount

    def get_job(self, job_id: int) -> dict | None:
        with self.connect() as conn:
            job = _row(conn.execute("SELECT * FROM crawl_jobs WHERE id=?", (job_id,)).fetchone())
            if job:
                job["seeds"] = [r[0] for r in conn.execute("SELECT url FROM crawl_job_seeds WHERE job_id=?", (job_id,))]
                job["errors_by_type"] = {r[0]: r[1] for r in conn.execute(
                    "SELECT error_type, COUNT(*) FROM crawl_errors WHERE job_id=? GROUP BY error_type", (job_id,))}
            return job

    def list_jobs(self, limit: int = 10) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM crawl_jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def record_crawl_error(self, job_id: int, url: str, depth: int, error_type: str,
                           status_code: int | None, message: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO crawl_errors(job_id, url, depth, error_type, status_code, message) "
                         "VALUES (?, ?, ?, ?, ?, ?)", (job_id, url, depth, error_type, status_code, message[:500]))

    def recent_errors(self, limit: int = 20, job_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM crawl_errors"
        args: tuple = ()
        if job_id is not None:
            sql += " WHERE job_id=?"
            args = (job_id,)
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql + " ORDER BY id DESC LIMIT ?", (*args, limit))]

    # =============================================================== documents + postings
    def known_content_hashes(self) -> dict[str, str]:
        with self.connect() as conn:
            return {r[0]: r[1] for r in conn.execute("SELECT content_hash, url FROM documents")}

    @staticmethod
    def get_document_by_hash(conn: sqlite3.Connection, url_hash: str) -> dict | None:
        return _row(conn.execute("SELECT id, title, content FROM documents WHERE url_hash=?", (url_hash,)).fetchone())

    @staticmethod
    def _domain_id(conn: sqlite3.Connection, name: str) -> int:
        conn.execute("INSERT OR IGNORE INTO domains(name) VALUES (?)", (name,))
        return conn.execute("SELECT id FROM domains WHERE name=?", (name,)).fetchone()[0]

    def save_document(self, conn: sqlite3.Connection, *, existing_id: int | None, fields: dict) -> int:
        """INSERT or UPDATE the documents row (must run inside the caller's transaction)."""
        fields = dict(fields)
        fields["domain_id"] = self._domain_id(conn, fields.pop("domain"))
        cols = list(fields)
        if existing_id is None:
            cur = conn.execute(
                f"INSERT INTO documents({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                [fields[c] for c in cols])
            return cur.lastrowid
        conn.execute(f"UPDATE documents SET {', '.join(c + '=?' for c in cols)} WHERE id=?",
                     [*(fields[c] for c in cols), existing_id])
        return existing_id

    @staticmethod
    def save_postings(conn: sqlite3.Connection, doc_id: int, term_freqs: Counter,
                      surface_counts: Counter, surface_to_term: dict[str, str]) -> None:
        terms = list(term_freqs)
        conn.executemany("INSERT OR IGNORE INTO terms(term) VALUES (?)", [(t,) for t in terms])
        term_ids: dict[str, int] = {}
        for chunk in _chunks(terms):
            q = f"SELECT term, id FROM terms WHERE term IN ({','.join('?' * len(chunk))})"
            term_ids.update({r[0]: r[1] for r in conn.execute(q, chunk)})
        # The AFTER INSERT trigger increments terms.doc_freq for every posting row.
        conn.executemany("INSERT INTO postings(term_id, doc_id, term_freq) VALUES (?, ?, ?)",
                         [(term_ids[t], doc_id, tf) for t, tf in term_freqs.items()])
        conn.executemany(
            "INSERT INTO vocabulary(word, term_id, frequency) VALUES (?, ?, ?) "
            "ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency, term_id = excluded.term_id",
            [(w, term_ids[surface_to_term[w]], c) for w, c in surface_counts.items() if surface_to_term[w] in term_ids])

    @staticmethod
    def remove_document_postings(conn: sqlite3.Connection, doc_id: int, old_surface_counts: Counter) -> None:
        """Undo a document's contribution to the index (re-crawl or deletion)."""
        term_ids = [r[0] for r in conn.execute("SELECT term_id FROM postings WHERE doc_id=?", (doc_id,))]
        for word, c in old_surface_counts.items():
            conn.execute("DELETE FROM vocabulary WHERE word=? AND frequency<=?", (word, c))
            conn.execute("UPDATE vocabulary SET frequency=frequency-? WHERE word=?", (c, word))
        conn.execute("DELETE FROM postings WHERE doc_id=?", (doc_id,))  # trigger decrements doc_freq
        for chunk in _chunks(term_ids):  # garbage-collect terms no document uses any more
            conn.execute(f"DELETE FROM terms WHERE doc_freq=0 AND id IN ({','.join('?' * len(chunk))})", chunk)

    @staticmethod
    def save_links(conn: sqlite3.Connection, doc_id: int, links: list[str]) -> None:
        conn.execute("DELETE FROM links WHERE source_doc_id=?", (doc_id,))
        conn.executemany("INSERT OR IGNORE INTO links(source_doc_id, target_url) VALUES (?, ?)",
                         [(doc_id, u) for u in links[:300]])

    def delete_document_row(self, conn: sqlite3.Connection, doc_id: int) -> None:
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))

    # =============================================================== reads for search/UI
    def load_index(self) -> tuple[InvertedIndex, Trie]:
        """Rebuild the in-memory inverted index + autocomplete trie from durable storage."""
        index, trie = InvertedIndex(), Trie()
        with self.connect() as conn:
            for doc_id, length in conn.execute("SELECT id, doc_length FROM documents"):
                index.set_doc_len(doc_id, length)
            # Ordered by the clustered PK ⇒ a sequential B-tree walk, no sort step.
            for term, doc_id, tf in conn.execute(
                    "SELECT t.term, p.doc_id, p.term_freq FROM postings p JOIN terms t ON t.id = p.term_id"):
                index.add_posting(term, doc_id, tf)
            for word, freq in conn.execute("SELECT word, frequency FROM vocabulary"):
                trie.insert(word, freq)
        return index, trie

    def popular_queries(self, limit: int = 200) -> list[tuple[str, int]]:
        with self.connect() as conn:
            return [(r[0], r[1]) for r in conn.execute(
                "SELECT normalized_query, COUNT(*) AS n FROM search_logs WHERE result_count > 0 "
                "GROUP BY normalized_query ORDER BY n DESC, normalized_query LIMIT ?", (limit,))]

    def fetch_documents(self, ids: list[int], with_content: bool = True) -> dict[int, dict]:
        cols = "d.id, d.url, d.title, d.description, d.fetched_at, d.doc_length, dom.name AS domain"
        if with_content:
            # Like Lucene's highlighter (maxAnalyzedChars), snippets only analyse a bounded
            # prefix of each page; substr() runs inside SQLite so the rest is never copied.
            cols += f", substr(d.content, 1, {SNIPPET_SCAN_CHARS}) AS content"
        out: dict[int, dict] = {}
        with self.connect() as conn:
            for chunk in _chunks(ids):
                q = (f"SELECT {cols} FROM documents d JOIN domains dom ON dom.id = d.domain_id "
                     f"WHERE d.id IN ({','.join('?' * len(chunk))})")
                out.update({r["id"]: dict(r) for r in conn.execute(q, chunk)})
        return out

    def fetch_texts(self, ids: list[int]) -> dict[int, tuple[str, str]]:
        """Full title + content, used to verify quoted phrases on the candidate set only."""
        out: dict[int, tuple[str, str]] = {}
        with self.connect() as conn:
            for chunk in _chunks(ids):
                q = f"SELECT id, title, content FROM documents WHERE id IN ({','.join('?' * len(chunk))})"
                out.update({r[0]: (r[1] or "", r[2] or "") for r in conn.execute(q, chunk)})
        return out

    def get_document(self, doc_id: int) -> dict | None:
        with self.connect() as conn:
            doc = _row(conn.execute(
                "SELECT d.*, dom.name AS domain FROM documents d JOIN domains dom ON dom.id=d.domain_id WHERE d.id=?",
                (doc_id,)).fetchone())
            if doc:
                doc["outlinks"] = conn.execute("SELECT COUNT(*) FROM links WHERE source_doc_id=?", (doc_id,)).fetchone()[0]
                doc["unique_terms"] = conn.execute("SELECT COUNT(*) FROM postings WHERE doc_id=?", (doc_id,)).fetchone()[0]
            return doc

    def list_documents(self, limit: int, offset: int, domain: str | None = None) -> tuple[int, list[dict]]:
        where, args = "", []
        if domain:
            where, args = "WHERE dom.name = ?", [domain]
        with self.connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM documents d JOIN domains dom ON dom.id=d.domain_id {where}",
                                 args).fetchone()[0]
            rows = conn.execute(
                f"SELECT d.id, d.url, d.title, d.description, dom.name AS domain, d.doc_length, d.depth, "
                f"d.status_code, d.fetched_at, d.indexed_at FROM documents d JOIN domains dom ON dom.id=d.domain_id "
                f"{where} ORDER BY d.indexed_at DESC, d.id DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
        return total, [dict(r) for r in rows]

    def domain_doc_ids(self, domain: str) -> set[int]:
        with self.connect() as conn:
            return {r[0] for r in conn.execute(
                "SELECT d.id FROM documents d JOIN domains dom ON dom.id=d.domain_id WHERE dom.name=?", (domain,))}

    def doc_domains(self) -> dict[int, str]:
        with self.connect() as conn:
            return {r[0]: r[1] for r in conn.execute(
                "SELECT d.id, dom.name FROM documents d JOIN domains dom ON dom.id=d.domain_id")}

    # =============================================================== search logs
    def log_search(self, query: str, normalized: str, result_count: int, latency_ms: float, page: int) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO search_logs(query, normalized_query, result_count, latency_ms, page) "
                         "VALUES (?, ?, ?, ?, ?)", (query[:256], normalized[:256], result_count, latency_ms, page))

    def recent_searches(self, limit: int = 10) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT query, result_count, latency_ms, created_at FROM search_logs ORDER BY id DESC LIMIT ?", (limit,))]

    # =============================================================== analytics
    def stats(self) -> dict:
        with self.connect() as conn:
            one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]  # noqa: E731
            s: dict = {
                "documents": one("SELECT COUNT(*) FROM documents"),
                "domains": one("SELECT COUNT(*) FROM domains WHERE id IN (SELECT domain_id FROM documents)"),
                "terms": one("SELECT COUNT(*) FROM terms"),
                "postings": one("SELECT COUNT(*) FROM postings"),
                "vocabulary": one("SELECT COUNT(*) FROM vocabulary"),
                "links": one("SELECT COUNT(*) FROM links"),
                "avg_doc_length": one("SELECT COALESCE(AVG(doc_length), 0) FROM documents"),
                "crawl_jobs": one("SELECT COUNT(*) FROM crawl_jobs"),
                "pages_fetched": one("SELECT COALESCE(SUM(pages_fetched), 0) FROM crawl_jobs"),
                "failed_requests": one(
                    f"SELECT COUNT(*) FROM crawl_errors WHERE error_type IN ({','.join('?' * len(NETWORK_ERROR_TYPES))})",
                    *NETWORK_ERROR_TYPES),
                "searches": one("SELECT COUNT(*) FROM search_logs"),
                "avg_latency_ms": one("SELECT COALESCE(AVG(latency_ms), 0) FROM search_logs"),
            }
            latencies = [r[0] for r in conn.execute(
                "SELECT latency_ms FROM search_logs ORDER BY id DESC LIMIT 1000")]
            latencies.sort()
            s["p95_latency_ms"] = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))] if latencies else 0.0
            attempts = s["pages_fetched"] + s["failed_requests"]
            s["crawl_success_rate"] = (s["pages_fetched"] / attempts) if attempts else 0.0
            s["errors_by_type"] = {r[0]: r[1] for r in conn.execute(
                "SELECT error_type, COUNT(*) FROM crawl_errors GROUP BY error_type ORDER BY 2 DESC")}
            s["top_domains"] = [dict(r) for r in conn.execute(
                "SELECT dom.name AS domain, COUNT(*) AS documents FROM documents d JOIN domains dom ON dom.id=d.domain_id "
                "GROUP BY dom.name ORDER BY documents DESC LIMIT 8")]
            s["top_terms"] = [dict(r) for r in conn.execute(
                "SELECT v.word AS term, t.doc_freq AS df FROM terms t "
                "JOIN vocabulary v ON v.term_id = t.id AND v.word = (SELECT word FROM vocabulary WHERE term_id = t.id "
                "ORDER BY frequency DESC LIMIT 1) ORDER BY t.doc_freq DESC LIMIT 10")]
            s["indexing_timeline"] = [dict(r) for r in conn.execute(
                "SELECT substr(indexed_at, 1, 16) AS bucket, COUNT(*) AS documents FROM documents "
                "GROUP BY bucket ORDER BY bucket DESC LIMIT 30")][::-1]
            s["search_timeline"] = [dict(r) for r in conn.execute(
                "SELECT substr(created_at, 1, 13) AS bucket, COUNT(*) AS searches, AVG(latency_ms) AS avg_latency_ms "
                "FROM search_logs GROUP BY bucket ORDER BY bucket DESC LIMIT 24")][::-1]
            s["recent_latencies"] = [dict(r) for r in conn.execute(
                "SELECT id, latency_ms, result_count, created_at FROM search_logs ORDER BY id DESC LIMIT 60")][::-1]
            s["top_queries"] = [dict(r) for r in conn.execute(
                "SELECT normalized_query AS query, COUNT(*) AS count FROM search_logs "
                "GROUP BY normalized_query ORDER BY count DESC LIMIT 8")]
        db_file = Path(self.db_path)
        s["db_size_bytes"] = db_file.stat().st_size if db_file.exists() else 0
        return s
