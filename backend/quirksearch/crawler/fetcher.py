"""Asynchronous HTTP fetching – the Computer Networks heart of the crawler.

What happens on every ``Fetcher.get(url)``:

1. **Rate limiting** – a per-host limiter guarantees at least ``per_host_delay`` seconds
   between two requests to the same host (politeness; avoids overloading servers).
2. **DNS resolution + TCP handshake** – performed by httpx/httpcore. Connections are kept
   alive in a pool, so later requests to the same host skip the TCP (and TLS) handshake.
3. **HTTP/1.1 request** – ``GET`` with our ``User-Agent`` and ``Accept: text/html``.
4. **Timeouts** – separate *connect* and *read* timeouts so a dead host or a server that
   stops sending bytes cannot stall a crawler worker forever.
5. **Redirects** – 3xx responses are followed (bounded by ``max_redirects``).
6. **Streaming with a size cap** – the body is read incrementally and abandoned beyond
   ``max_page_bytes``.
7. **Error classification** – DNS failure, connection refused, timeout, HTTP 4xx/5xx,
   non-HTML content… each becomes a typed ``error_type`` that is stored in ``crawl_errors``.
"""
from __future__ import annotations

import asyncio
import ssl
import time
from dataclasses import dataclass

import httpx

from ..config import Settings
from .url_utils import domain_of

try:  # Use the operating system's certificate store (Windows/macOS keychains, Linux CA dir)
    import truststore

    def _ssl_context() -> ssl.SSLContext | bool:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:  # fall back to certifi's bundle shipped with httpx
    def _ssl_context() -> ssl.SSLContext | bool:
        return True


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int | None = None
    content_type: str = ""
    body: bytes = b""
    encoding: str | None = None
    error_type: str | None = None  # dns | connection | tls | timeout | http_error | not_html | too_large | redirect | protocol
    error: str | None = None
    elapsed_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error_type is None


class HostRateLimiter:
    """Enforces a minimum delay between consecutive requests to the same host.

    One ``asyncio.Lock`` per host serializes access, and the timestamp of the last request
    is kept in a hash map → O(1) per request. Different hosts proceed in parallel.
    """

    def __init__(self, delay: float):
        self.delay = delay
        self._last: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def wait(self, host: str, delay: float | None = None) -> None:
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            gap = self.delay if delay is None else max(self.delay, delay)
            now = time.monotonic()
            ready_at = self._last.get(host, 0.0) + gap
            if ready_at > now:
                await asyncio.sleep(ready_at - now)
            self._last[host] = time.monotonic()


def _classify_connect_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "ssl" in msg or "certificate" in msg or "tls" in msg:
        return "tls"
    dns_markers = ("getaddrinfo", "name or service not known", "nodename nor servname",
                   "no address associated", "temporary failure in name resolution", "11001")
    return "dns" if any(m in msg for m in dns_markers) else "connection"


class Fetcher:
    """Thin, well-behaved wrapper around ``httpx.AsyncClient``."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.rate_limiter = HostRateLimiter(settings.per_host_delay)
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self.crawl_delays: dict[str, float] = {}  # host -> Crawl-delay from robots.txt

    async def __aenter__(self) -> "Fetcher":
        s = self.settings
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": s.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
                "Accept-Language": "en;q=1.0,*;q=0.5",
            },
            timeout=httpx.Timeout(s.read_timeout, connect=s.connect_timeout),
            follow_redirects=True,
            max_redirects=s.max_redirects,
            limits=httpx.Limits(max_connections=max(4, s.concurrency * 2), max_keepalive_connections=s.concurrency),
            transport=self._transport,
            verify=_ssl_context(),
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None, "use 'async with Fetcher(...)'"
        return self._client

    async def get(self, url: str, *, html_only: bool = True) -> FetchResult:
        result = FetchResult(url=url, final_url=url)
        host = domain_of(url)
        await self.rate_limiter.wait(host, self.crawl_delays.get(host))
        started = time.perf_counter()
        try:
            async with self.client.stream("GET", url) as resp:
                result.final_url = str(resp.url)
                result.status_code = resp.status_code
                result.content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                result.encoding = resp.charset_encoding  # from the Content-Type header, may be None

                if resp.status_code >= 400:
                    result.error_type = "http_error"
                    result.error = f"HTTP {resp.status_code} {resp.reason_phrase}"
                    return result
                if html_only and result.content_type not in ("text/html", "application/xhtml+xml", ""):
                    result.error_type = "not_html"
                    result.error = f"Skipped non-HTML content ({result.content_type})"
                    return result

                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self.settings.max_page_bytes:
                    result.error_type = "too_large"
                    result.error = f"Content-Length {declared} exceeds limit"
                    return result

                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > self.settings.max_page_bytes:
                        result.error_type = "too_large"
                        result.error = f"Body exceeded {self.settings.max_page_bytes} bytes"
                        return result
                    chunks.append(chunk)
                result.body = b"".join(chunks)
        except httpx.TimeoutException as exc:
            result.error_type = "timeout"
            result.error = f"{type(exc).__name__}: request timed out"
        except httpx.TooManyRedirects:
            result.error_type = "redirect"
            result.error = "Too many redirects"
        except httpx.ConnectError as exc:
            result.error_type = _classify_connect_error(exc)
            result.error = f"{type(exc).__name__}: {exc}"
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            result.error_type = "protocol"
            result.error = f"{type(exc).__name__}: {exc}"
        finally:
            result.elapsed_ms = (time.perf_counter() - started) * 1000
        return result
