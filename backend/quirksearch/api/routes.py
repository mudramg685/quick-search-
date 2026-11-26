"""REST endpoints (JSON over HTTP).

GET  /api/health              liveness + index summary
GET  /api/search              ranked search          q, page, page_size, domain, autocorrect
GET  /api/suggestions         autocomplete           q, limit
GET  /api/stats               analytics for the dashboard
GET  /api/documents           paginated document list (page, page_size, domain)
GET  /api/documents/{id}      one document with index metadata
POST /api/crawl               start a background crawl job (202 Accepted)
GET  /api/crawl/status        current/latest (or given) job + live progress + errors
GET  /api/crawl/jobs          recent jobs
POST /api/crawl/cancel        stop the running job
POST /api/index/reload        reload the in-memory index from the database
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .. import __version__
from ..services.crawl_service import CrawlAlreadyRunning
from .schemas import CrawlRequest, CrawlStarted, SearchResponse, SuggestionResponse

router = APIRouter(prefix="/api")


def _state(request: Request):
    return request.app.state


@router.get("/health", tags=["system"])
def health(request: Request):
    st = _state(request)
    with st.repo.connect() as conn:
        conn.execute("SELECT 1").fetchone()
    snap = st.engine.snapshot
    return {
        "status": "ok",
        "version": __version__,
        "documents": snap.index.num_docs,
        "terms": snap.index.num_terms,
        "index_loaded_at": snap.loaded_at,
        "crawl_running": st.crawler.running,
    }


@router.get("/search", response_model=SearchResponse, tags=["search"])
def search(request: Request,
           q: str = Query(..., min_length=1, max_length=256, description="Search query"),
           page: int = Query(1, ge=1, le=100),
           page_size: int = Query(10, ge=1, le=50),
           domain: str | None = Query(None, max_length=253),
           autocorrect: bool = Query(True, description="Run the spelling fix when nothing matches")):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=422, detail="Query must contain non-whitespace characters")
    st = _state(request)
    result = st.engine.search(q, page=page, page_size=page_size, domain=domain, autocorrect=autocorrect)
    st.repo.log_search(q, result["normalized_query"] or q.lower(), result["total"], result["took_ms"], page)
    if result["total"] and page == 1:
        st.engine.record_query(result["normalized_query"])
    return result


@router.get("/suggestions", response_model=SuggestionResponse, tags=["search"])
def suggestions(request: Request, q: str = Query("", max_length=128), limit: int = Query(8, ge=1, le=20)):
    return {"query": q, "suggestions": _state(request).engine.suggest(q, limit)}


@router.get("/stats", tags=["analytics"])
def stats(request: Request):
    st = _state(request)
    s = st.repo.stats()
    snap = st.engine.snapshot
    s["index"] = {
        "documents": snap.index.num_docs,
        "terms": snap.index.num_terms,
        "avg_doc_length": round(snap.index.avg_doc_len, 2),
        "vocabulary": snap.words.size,
        "loaded_at": snap.loaded_at,
        "last_reload_ms": st.last_reload_ms,
    }
    s["recent_searches"] = st.repo.recent_searches(10)
    s["recent_jobs"] = st.repo.list_jobs(6)
    s["recent_errors"] = st.repo.recent_errors(8)
    s["crawl"] = {"running": st.crawler.running, "job_id": st.crawler.current_job_id,
                  "live": st.crawler.live_stats()}
    return s


@router.get("/documents", tags=["documents"])
def documents(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
              domain: str | None = Query(None, max_length=253)):
    total, rows = _state(request).repo.list_documents(page_size, (page - 1) * page_size, domain)
    return {"total": total, "page": page, "page_size": page_size, "documents": rows}


@router.get("/documents/{doc_id}", tags=["documents"])
def document(request: Request, doc_id: int):
    doc = _state(request).repo.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    doc["content_preview"] = doc.pop("content")[:1500]
    doc["headings"] = [h for h in doc["headings"].split("\n") if h]
    return doc


@router.post("/crawl", response_model=CrawlStarted, status_code=202, tags=["crawler"])
def start_crawl(request: Request, body: CrawlRequest):
    st = _state(request)
    seeds = [str(u) for u in body.seeds] or [st.default_seed]
    try:
        job_id = st.crawler.start(seeds, body.max_depth, body.max_pages, body.same_domain_only)
    except CrawlAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"job_id": job_id, "status": "running", "seeds": seeds}


@router.get("/crawl/status", tags=["crawler"])
def crawl_status(request: Request, job_id: int | None = Query(None, ge=1)):
    st = _state(request)
    if job_id is None:
        job_id = st.crawler.current_job_id
        if job_id is None:
            jobs = st.repo.list_jobs(1)
            job_id = jobs[0]["id"] if jobs else None
    if job_id is None:
        return {"running": False, "job": None, "live": None, "recent_errors": []}
    job = st.repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Crawl job {job_id} not found")
    running = st.crawler.running and st.crawler.current_job_id == job_id
    return {"running": running, "job": job, "live": st.crawler.live_stats() if running else None,
            "recent_errors": st.repo.recent_errors(15, job_id)}


@router.get("/crawl/jobs", tags=["crawler"])
def crawl_jobs(request: Request, limit: int = Query(10, ge=1, le=100)):
    return {"jobs": _state(request).repo.list_jobs(limit)}


@router.post("/crawl/cancel", tags=["crawler"])
def cancel_crawl(request: Request):
    if not _state(request).crawler.cancel():
        return JSONResponse(status_code=409, content={"detail": "No crawl is running"})
    return {"status": "cancelling"}


@router.post("/index/reload", tags=["system"])
def reload_index(request: Request):
    st = _state(request)
    t0 = time.perf_counter()
    st.last_reload_ms = round(st.engine.reload(), 2)
    return {"status": "reloaded", "documents": st.engine.snapshot.index.num_docs,
            "took_ms": round((time.perf_counter() - t0) * 1000, 2)}
