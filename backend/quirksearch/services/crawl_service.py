"""Crawl-job orchestration.

A crawl runs on a background thread with its own asyncio event loop, so the FastAPI
server keeps answering searches while pages are fetched and indexed (SQLite WAL lets
readers proceed during writes). Only one crawl job runs at a time – a simple, explicit
form of request management that keeps load on remote servers bounded.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable

from ..config import Settings
from ..crawler.crawler import CrawlConfig, CrawledPage, Crawler
from ..db.repository import Repository
from ..index.indexer import index_page

log = logging.getLogger("quirksearch.crawl")


class CrawlAlreadyRunning(RuntimeError):
    pass


class DbSink:
    """CrawlSink that indexes pages and records errors in the database."""

    def __init__(self, repo: Repository, job_id: int, settings: Settings,
                 on_batch: Callable[[], None] | None = None, batch_size: int = 15):
        self.repo, self.job_id, self.settings = repo, job_id, settings
        self.on_batch, self.batch_size = on_batch, batch_size
        self.crawler: Crawler | None = None
        self._since_refresh = 0

    def _progress(self) -> None:
        if self.crawler:
            st = self.crawler.stats
            self.repo.update_job_progress(self.job_id, st.discovered, st.fetched, st.stored, st.failed)

    def on_page(self, page: CrawledPage) -> None:
        index_page(self.repo, self.job_id, page, self.settings.max_stored_chars)
        self._since_refresh += 1
        self._progress()
        if self.on_batch and self._since_refresh >= self.batch_size:
            self._since_refresh = 0
            self.on_batch()  # make freshly indexed pages searchable mid-crawl

    def on_error(self, url: str, depth: int, error_type: str, status_code: int | None, message: str) -> None:
        self.repo.record_crawl_error(self.job_id, url, depth, error_type, status_code, message)
        self._progress()


class CrawlService:
    def __init__(self, repo: Repository, settings: Settings, on_index_changed: Callable[[], None]):
        self.repo = repo
        self.settings = settings
        self.on_index_changed = on_index_changed
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._crawler: Crawler | None = None
        self.current_job_id: int | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _build(self, seeds: list[str], max_depth: int, max_pages: int, same_domain_only: bool):
        job_id = self.repo.create_crawl_job(seeds, max_depth, max_pages)
        sink = DbSink(self.repo, job_id, self.settings, on_batch=self.on_index_changed)
        config = CrawlConfig(seeds=seeds, max_depth=max_depth, max_pages=max_pages,
                             same_domain_only=same_domain_only)
        try:
            crawler = Crawler(self.settings, config, sink, known_content_hashes=self.repo.known_content_hashes())
        except ValueError as exc:
            self.repo.finish_job(job_id, "failed", str(exc))
            raise
        sink.crawler = crawler
        return job_id, crawler

    def _execute(self, job_id: int, crawler: Crawler) -> None:
        self.repo.mark_job_running(job_id)
        status, error = "completed", None
        try:
            asyncio.run(crawler.run())
            if crawler._stop.is_set():
                status = "cancelled"
        except Exception as exc:  # noqa: BLE001 – job must always reach a terminal state
            log.exception("Crawl job %s failed", job_id)
            status, error = "failed", f"{type(exc).__name__}: {exc}"
        finally:
            st = crawler.stats
            self.repo.update_job_progress(job_id, st.discovered, st.fetched, st.stored, st.failed)
            # Reload BEFORE publishing the terminal status: once a client sees "completed",
            # every page of the job is guaranteed to be searchable.
            try:
                self.on_index_changed()
            finally:
                self.repo.finish_job(job_id, status, error)

    def start(self, seeds: list[str], max_depth: int, max_pages: int, same_domain_only: bool = True) -> int:
        """Start a crawl in the background and return its job id immediately."""
        with self._lock:
            if self.running:
                raise CrawlAlreadyRunning(f"Crawl job {self.current_job_id} is still running")
            job_id, crawler = self._build(seeds, max_depth, max_pages, same_domain_only)
            self._crawler, self.current_job_id = crawler, job_id
            self._thread = threading.Thread(target=self._execute, args=(job_id, crawler),
                                            name=f"crawl-{job_id}", daemon=True)
            self._thread.start()
            return job_id

    def run_blocking(self, seeds: list[str], max_depth: int, max_pages: int, same_domain_only: bool = True) -> int:
        """Synchronous variant for the CLI and tests."""
        job_id, crawler = self._build(seeds, max_depth, max_pages, same_domain_only)
        self._crawler, self.current_job_id = crawler, job_id
        self._execute(job_id, crawler)
        return job_id

    def cancel(self) -> bool:
        if self.running and self._crawler:
            self._crawler.cancel()
            return True
        return False

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def live_stats(self) -> dict | None:
        if not (self.running and self._crawler):
            return None
        st = self._crawler.stats
        return dict(discovered=st.discovered, fetched=st.fetched, stored=st.stored, failed=st.failed,
                    duplicates=st.duplicates, robots_blocked=st.robots_blocked, queued=st.discovered - st.fetched - st.failed)
