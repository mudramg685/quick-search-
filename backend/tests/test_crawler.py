"""Phase 2 – crawler tests: URL normalization, extraction, BFS, dedupe, robots, errors."""
from __future__ import annotations

import asyncio
import time

import pytest

from quirksearch.crawler.crawler import CrawlConfig, Crawler
from quirksearch.crawler.fetcher import Fetcher, HostRateLimiter
from quirksearch.crawler.parser import parse_html
from quirksearch.crawler.url_utils import is_allowed_domain, normalize_url


class MemorySink:
    def __init__(self):
        self.pages = []
        self.errors = []

    def on_page(self, page):
        self.pages.append(page)

    def on_error(self, url, depth, error_type, status_code, message):
        self.errors.append((url, error_type, status_code))

    def by_type(self, t):
        return [e for e in self.errors if e[1] == t]


# ----------------------------------------------------------------- URL normalization
@pytest.mark.parametrize("raw,expected", [
    ("HTTP://Example.COM:80/a/./b/../c#frag", "http://example.com/a/c"),
    ("https://example.com:443", "https://example.com/"),
    ("https://example.com:8443/x", "https://example.com:8443/x"),
    ("http://example.com/s?b=2&a=1&utm_source=x", "http://example.com/s?a=1&b=2"),
    ("http://example.com/a%7Eb", "http://example.com/a~b"),
    ("http://example.com/dir/", "http://example.com/dir/"),
    ("mailto:someone@example.com", None),
    ("javascript:void(0)", None),
    ("http://example.com:abc/", None),
])
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_normalize_relative_and_idna():
    assert normalize_url("../b.html", "http://x.org/a/c/page.html") == "http://x.org/a/b.html"
    assert normalize_url("http://bücher.de/") == "http://xn--bcher-kva.de/"


def test_domain_restriction():
    assert is_allowed_domain("https://docs.python.org/3/", {"python.org"})
    assert not is_allowed_domain("https://evilpython.org/", {"python.org"})


# ----------------------------------------------------------------- HTML extraction
def test_parse_html_extracts_fields():
    html = b"""<html lang="en"><head><title> Hello  World </title>
    <meta name="description" content="A test page"></head>
    <body><nav><a href="/nav">Menu</a></nav><main><h1>Main heading</h1>
    <p>Some <b>bold</b> text here.</p><script>var x = 'nope';</script>
    <a href="other.html#x">other</a><a href="mailto:a@b.c">mail</a><a href="pic.png">img</a>
    <a href="/skip" rel="nofollow">skip</a></main><footer>footer text</footer></body></html>"""
    page = parse_html(html, "http://site.test/dir/index.html")
    assert page.title == "Hello World"
    assert page.description == "A test page"
    assert page.headings == ["Main heading"]
    assert "Some bold text here." in page.body_text
    assert "nope" not in page.body_text and "footer text" not in page.body_text
    assert page.links == ["http://site.test/nav", "http://site.test/dir/other.html"]
    assert page.language == "en"


def test_parse_noindex_meta():
    page = parse_html(b'<html><head><meta name="robots" content="noindex,nofollow"></head><body><a href="/x">x</a></body></html>',
                      "http://a.test/")
    assert page.noindex and page.nofollow and page.links == []


# ----------------------------------------------------------------- full crawl over real HTTP
def test_crawl_corpus_bfs_dedupe_robots_errors(site, settings):
    sink = MemorySink()
    crawler = Crawler(settings, CrawlConfig(seeds=[f"{site}/corpus/index.html"], max_depth=3, max_pages=200), sink)
    stats = asyncio.run(crawler.run())

    urls = {p.final_url for p in sink.pages}
    # every article reachable from the hub is crawled exactly once
    assert len(urls) == len(sink.pages)
    assert f"{site}/corpus/bm25.html" in urls
    assert stats.stored == len(sink.pages) >= 39
    # BFS: the seed is depth 0 and articles are depth 1
    depths = {p.final_url: p.depth for p in sink.pages}
    assert depths[f"{site}/corpus/index.html"] == 0
    assert depths[f"{site}/corpus/bm25.html"] == 1
    # robots.txt blocked the private page – it was never fetched
    assert any("private/secret-roadmap" in u for u, *_ in sink.by_type("robots"))
    assert not any("private" in u for u in urls)
    # the mirror is an exact duplicate → detected by content hash
    assert any("mirror/hash-tables" in u for u, *_ in sink.by_type("duplicate"))
    # noindex draft not stored
    assert not any("drafts" in u for u in urls)
    assert stats.skipped_noindex == 1
    # the broken link produced an HTTP 404 error record
    assert (f"{site}/corpus/crawler-faq.html", "http_error", 404) in sink.errors
    # extracted content
    bm25 = next(p for p in sink.pages if p.final_url.endswith("/bm25.html"))
    assert bm25.parsed.title.startswith("BM25 Ranking Function")
    assert "saturating" in bm25.parsed.body_text


def test_max_pages_and_depth_limits(site, settings):
    sink = MemorySink()
    asyncio.run(Crawler(settings, CrawlConfig(seeds=[f"{site}/corpus/index.html"], max_depth=3, max_pages=5), sink).run())
    assert len(sink.pages) <= 5

    sink = MemorySink()
    asyncio.run(Crawler(settings, CrawlConfig(seeds=[f"{site}/corpus/bm25.html"], max_depth=0), sink).run())
    assert [p.depth for p in sink.pages] == [0]


# ----------------------------------------------------------------- network failure modes
def _fetch(settings, url):
    async def go():
        async with Fetcher(settings) as f:
            return await f.get(url)
    return asyncio.run(go())


def test_fetch_timeout(site, settings):
    r = _fetch(settings, f"{site}/slow")
    assert r.error_type == "timeout"


def test_fetch_connection_refused(settings):
    r = _fetch(settings, "http://127.0.0.1:9/")  # port 9 (discard) is closed locally
    assert r.error_type in ("connection", "timeout")


def test_fetch_dns_failure(settings):
    r = _fetch(settings, "http://no-such-host.invalid/")  # .invalid is reserved (RFC 2606)
    assert r.error_type in ("dns", "connection")


def test_fetch_http_errors_redirect_and_content_type(site, settings):
    assert _fetch(settings, f"{site}/error500").status_code == 500
    assert _fetch(settings, f"{site}/error500").error_type == "http_error"
    redirected = _fetch(settings, f"{site}/redirect")
    assert redirected.ok and redirected.final_url.endswith("/corpus/bm25.html")
    assert _fetch(settings, f"{site}/image.png").error_type == "not_html"


def test_rate_limiter_spaces_requests():
    async def go():
        limiter = HostRateLimiter(0.2)
        t0 = time.monotonic()
        for _ in range(3):
            await limiter.wait("a.test")
        return time.monotonic() - t0
    assert asyncio.run(go()) >= 0.38  # two enforced gaps of 0.2s
