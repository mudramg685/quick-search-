"""Shared fixtures.

``site`` starts a *real* HTTP server on an ephemeral localhost port (real TCP sockets,
real HTTP/1.1) that serves the bundled corpus plus a few endpoints for failure modes.
"""
from __future__ import annotations

import dataclasses
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from quirksearch.config import Settings

BACKEND = Path(__file__).resolve().parent.parent
CORPUS = BACKEND / "corpus"
ROBOTS = BACKEND / "robots.txt"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep pytest output clean
        pass

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/robots.txt":
            return self._send(200, ROBOTS.read_bytes(), "text/plain")
        if path == "/slow":
            time.sleep(1.5)
            return self._send(200, b"<html><title>slow</title></html>")
        if path == "/redirect":
            return self._send(301, b"", headers={"Location": "/corpus/bm25.html"})
        if path == "/error500":
            return self._send(500, b"boom")
        if path == "/image.png":
            return self._send(200, b"\x89PNG....", "image/png")
        if path.startswith("/corpus/"):
            target = (CORPUS / path[len("/corpus/"):]).resolve()
            if CORPUS.resolve() in target.parents and target.is_file():
                ctype = "text/css" if target.suffix == ".css" else "text/html; charset=utf-8"
                return self._send(200, target.read_bytes(), ctype)
        return self._send(404, b"<html><title>Not found</title></html>")


@pytest.fixture(scope="session")
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def settings(tmp_path):
    return dataclasses.replace(
        Settings(), db_path=tmp_path / "test.db", per_host_delay=0.0, concurrency=4,
        read_timeout=0.5, connect_timeout=0.5, max_pages=200, max_depth=3,
    )
