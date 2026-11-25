"""FastAPI application factory.

Run:  uvicorn quirksearch.main:app --port 8000      (from the backend/ directory)

Startup sequence:
  1. open/create the SQLite database and apply the schema
  2. mark jobs interrupted by a previous crash as failed
  3. load the inverted index + tries from SQLite into memory
  4. if the database is empty, crawl the bundled corpus in the background (served by this
     very server at /corpus over HTTP) so the engine is useful out of the box
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api.ratelimit import TokenBucketLimiter
from .api.routes import router
from .config import BACKEND_DIR, Settings, get_settings
from .db.repository import Repository
from .search.searcher import SearchEngine
from .services.crawl_service import CrawlService

log = logging.getLogger("quirksearch")
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


def _auto_seed(app: FastAPI, settings: Settings) -> None:
    """Wait until this server answers on its public URL, then crawl the bundled corpus."""
    for _ in range(60):
        try:
            if httpx.get(settings.public_base_url + "/robots.txt", timeout=1.0).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    else:
        log.warning("Auto-seed skipped: %s not reachable", settings.public_base_url)
        return
    try:
        app.state.crawler.start([app.state.default_seed], max_depth=2, max_pages=150)
        log.info("Auto-seeding the bundled corpus from %s", app.state.default_seed)
    except Exception:  # noqa: BLE001
        log.exception("Auto-seed failed")


def create_app(settings: Settings | None = None, auto_seed: bool = True) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repo = Repository(settings.db_path)
        stale = repo.fail_stale_jobs()
        if stale:
            log.warning("Marked %d interrupted crawl job(s) as failed", stale)
        engine = SearchEngine(repo, settings)

        def on_index_changed() -> None:
            app.state.last_reload_ms = round(engine.reload(), 2)

        app.state.settings = settings
        app.state.repo = repo
        app.state.engine = engine
        app.state.crawler = CrawlService(repo, settings, on_index_changed)
        app.state.default_seed = settings.public_base_url.rstrip("/") + "/corpus/index.html"
        app.state.last_reload_ms = None
        app.state.limiter = TokenBucketLimiter(rate=20.0, capacity=40)
        if auto_seed and engine.snapshot.index.num_docs == 0:
            threading.Thread(target=_auto_seed, args=(app, settings), daemon=True).start()
        yield
        app.state.crawler.cancel()
        app.state.crawler.wait(5)
        repo.close()

    app = FastAPI(title="QuirkSearch API", version=__version__, lifespan=lifespan,
                  description="Curiosity deserves better results. A from-scratch search engine: "
                              "crawler, inverted index, BM25 ranking.")
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["*"],
                       expose_headers=["X-Response-Time-ms", "X-RateLimit-Remaining"])

    @app.middleware("http")
    async def timing_and_rate_limit(request: Request, call_next):
        remaining = None
        if request.url.path.startswith("/api/") and request.url.path != "/api/health":
            client = request.client.host if request.client else "unknown"
            ok, retry, remaining = request.app.state.limiter.allow(client)
            if not ok:
                return JSONResponse(status_code=429, content={"detail": "Too many requests – slow down a little."},
                                    headers={"Retry-After": TokenBucketLimiter.retry_header(retry)})
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.2f}"
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(router)

    # robots.txt for the whole origin + the bundled corpus (what the crawler fetches).
    @app.get("/robots.txt", include_in_schema=False)
    def robots_txt():
        return PlainTextResponse((BACKEND_DIR / "robots.txt").read_text(encoding="utf-8"))

    settings.corpus_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/corpus", StaticFiles(directory=settings.corpus_dir, html=True), name="corpus")

    # Production: serve the built React app from the same origin.
    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            candidate = (FRONTEND_DIST / path).resolve()
            if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
