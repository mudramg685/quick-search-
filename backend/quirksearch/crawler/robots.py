"""robots.txt support (Robots Exclusion Protocol, RFC 9309).

Each origin's robots.txt is fetched once and cached in a hash map, so the check is
O(1) per URL after the first request to a host. Status handling follows RFC 9309 §2.3.1:

* 2xx          → parse the rules
* 4xx          → "unavailable": the crawler may access everything
* 5xx / network failure → "unreachable": assume complete disallow
"""
from __future__ import annotations

import asyncio
from urllib.robotparser import RobotFileParser

from .fetcher import Fetcher
from .url_utils import domain_of, origin_of


class RobotsCache:
    def __init__(self, fetcher: Fetcher, user_agent: str):
        self.fetcher = fetcher
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def _load(self, origin: str) -> RobotFileParser:
        parser = RobotFileParser()
        parser.set_url(origin + "/robots.txt")
        result = await self.fetcher.get(origin + "/robots.txt", html_only=False)
        if result.status_code is not None and 200 <= result.status_code < 300 and result.ok:
            text = result.body.decode(result.encoding or "utf-8", errors="replace")
            parser.parse(text.splitlines())
        elif result.status_code is not None and 400 <= result.status_code < 500:
            parser.allow_all = True
        else:
            parser.disallow_all = True
        parser.modified()  # can_fetch() returns False until a check time is recorded

        delay = parser.crawl_delay(self.user_agent)
        if delay:
            # Cap absurd values so one site cannot stall the crawl for minutes.
            self.fetcher.crawl_delays[domain_of(origin)] = min(float(delay), 5.0)
        return parser

    async def allowed(self, url: str) -> bool:
        origin = origin_of(url)
        if origin not in self._parsers:
            lock = self._locks.setdefault(origin, asyncio.Lock())
            async with lock:
                if origin not in self._parsers:  # double-checked: one fetch per origin
                    self._parsers[origin] = await self._load(origin)
        return self._parsers[origin].can_fetch(self.user_agent, url)
