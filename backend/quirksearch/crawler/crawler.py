"""Concurrent breadth-first web crawler.

The web is a directed graph: pages are vertices, hyperlinks are edges. The crawler performs
a **breadth-first traversal** from the seed URLs:

* ``frontier`` – a FIFO ``asyncio.Queue`` of (url, depth). FIFO order ⇒ BFS, so pages
  closest to the seeds are crawled first and ``max_depth`` bounds the traversal.
* ``visited`` – a hash set of URL fingerprints. A URL is added *when it is enqueued*,
  so each vertex enters the queue at most once (O(1) membership test).
* ``content_hashes`` – a hash map of SHA-256 digests of page text, detecting the same
  content served under different URLs (mirrors, ``?session=`` variants…).
* ``concurrency`` worker coroutines consume the frontier in parallel. I/O waits (DNS, TCP,
  server think-time) overlap, so throughput scales with workers while the per-host rate
  limiter keeps each individual server's load polite.

Complexity: every reachable URL within the limits is enqueued once and every link is
examined once ⇒ O(V + E) set operations, bounded by ``max_pages``.

The crawler is storage-agnostic: results are pushed to a ``CrawlSink`` (the crawl service
persists and indexes them; tests use an in-memory sink).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

import httpx

from ..config import Settings
from .fetcher import Fetcher, FetchResult
from .parser import ParsedPage, parse_html
from .robots import RobotsCache
from .url_utils import domain_of, is_allowed_domain, normalize_url, url_hash

log = logging.getLogger("quirksearch.crawler")


@dataclass
class CrawlConfig:
    seeds: list[str]
    max_depth: int = 2
    max_pages: int = 100
    allowed_domains: set[str] | None = None  # None → restrict to the seeds' domains
    respect_robots: bool = True
    same_domain_only: bool = True


@dataclass
class CrawledPage:
    url: str            # canonical URL that was requested
    final_url: str      # after redirects
    depth: int
    status_code: int
    parsed: ParsedPage
    content_hash: str
    fetched_at: str
    elapsed_ms: float
    outlinks: list[str] = field(default_factory=list)


@dataclass
class CrawlStats:
    discovered: int = 0
    fetched: int = 0
    stored: int = 0
    failed: int = 0
    duplicates: int = 0
    robots_blocked: int = 0
    skipped_noindex: int = 0


class CrawlSink(Protocol):
    def on_page(self, page: CrawledPage) -> None: ...
    def on_error(self, url: str, depth: int, error_type: str, status_code: int | None, message: str) -> None: ...


def content_fingerprint(page: ParsedPage) -> str:
    text = (page.title + "\n" + page.body_text).lower()
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Crawler:
    def __init__(self, settings: Settings, config: CrawlConfig, sink: CrawlSink,
                 transport: httpx.AsyncBaseTransport | None = None,
                 known_content_hashes: dict[str, str] | None = None):
        self.settings = settings
        self.config = config
        self.sink = sink
        self.transport = transport
        self.stats = CrawlStats()
        self.visited: set[str] = set()
        # content fingerprint -> URL that first produced it (seeded from the database)
        self.content_hashes: dict[str, str] = dict(known_content_hashes or {})
        self._reserved = 0  # fetch slots handed out (bounded by max_pages)
        self._stop = asyncio.Event()

        seeds = [u for u in (normalize_url(s) for s in config.seeds) if u]
        if not seeds:
            raise ValueError("No valid http(s) seed URLs supplied")
        self.seeds = seeds
        if config.allowed_domains is None and config.same_domain_only:
            self.allowed_domains: set[str] | None = {domain_of(u) for u in seeds}
        else:
            self.allowed_domains = config.allowed_domains

    def cancel(self) -> None:
        self._stop.set()

    def _enqueue(self, queue: asyncio.Queue, url: str, depth: int) -> None:
        key = url_hash(url)
        if key in self.visited:
            return
        self.visited.add(key)
        self.stats.discovered += 1
        queue.put_nowait((url, depth))

    async def run(self) -> CrawlStats:
        queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        for seed in self.seeds:
            self._enqueue(queue, seed, 0)

        async with Fetcher(self.settings, transport=self.transport) as fetcher:
            robots = RobotsCache(fetcher, self.settings.user_agent)
            workers = [asyncio.create_task(self._worker(queue, fetcher, robots))
                       for _ in range(max(1, self.settings.concurrency))]
            await queue.join()  # every enqueued URL has been processed (or skipped)
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
        return self.stats

    async def _worker(self, queue: asyncio.Queue, fetcher: Fetcher, robots: RobotsCache) -> None:
        while True:
            url, depth = await queue.get()
            try:
                if self._stop.is_set() or self._reserved >= self.config.max_pages:
                    continue  # drain the queue without fetching
                await self._process(url, depth, queue, fetcher, robots)
            except Exception as exc:  # a single bad page must never kill a worker
                log.exception("Unexpected error crawling %s", url)
                self.stats.failed += 1
                self.sink.on_error(url, depth, "internal", None, f"{type(exc).__name__}: {exc}")
            finally:
                queue.task_done()

    async def _process(self, url: str, depth: int, queue: asyncio.Queue,
                       fetcher: Fetcher, robots: RobotsCache) -> None:
        if self.config.respect_robots and not await robots.allowed(url):
            self.stats.robots_blocked += 1
            self.sink.on_error(url, depth, "robots", None, robots.reason(url))
            return

        # Check-and-reserve with no ``await`` in between ⇒ atomic under asyncio's
        # cooperative scheduling, so concurrent workers can never exceed max_pages.
        if self._reserved >= self.config.max_pages:
            return
        self._reserved += 1
        result: FetchResult = await fetcher.get(url)
        if not result.ok:
            self.stats.failed += 1
            self.sink.on_error(url, depth, result.error_type or "unknown", result.status_code, result.error or "")
            return
        self.stats.fetched += 1

        final_url = normalize_url(result.final_url) or url
        if final_url != url:  # redirect: mark the target visited too
            self.visited.add(url_hash(final_url))

        parsed = parse_html(result.body, final_url, result.encoding)

        # Enqueue children first (BFS expansion) – even noindex pages may be followed.
        if depth < self.config.max_depth:
            for link in parsed.links:
                if is_allowed_domain(link, self.allowed_domains):
                    self._enqueue(queue, link, depth + 1)

        if parsed.noindex:
            self.stats.skipped_noindex += 1
            return

        fingerprint = content_fingerprint(parsed)
        owner = self.content_hashes.get(fingerprint)
        if owner is not None and owner != final_url:
            self.stats.duplicates += 1
            self.sink.on_error(final_url, depth, "duplicate", result.status_code,
                               f"Duplicate content of {owner} (identical SHA-256 fingerprint)")
            return
        self.content_hashes[fingerprint] = final_url

        page = CrawledPage(
            url=url, final_url=final_url, depth=depth, status_code=result.status_code or 200,
            parsed=parsed, content_hash=fingerprint, fetched_at=now_iso(),
            elapsed_ms=result.elapsed_ms, outlinks=parsed.links,
        )
        self.sink.on_page(page)
        self.stats.stored += 1
