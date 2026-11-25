"""Phase 6 – REST API: happy paths, validation, error handling, rate limiting, restart."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from quirksearch.api.ratelimit import TokenBucketLimiter
from quirksearch.main import create_app


def wait_for_crawl(client: TestClient, job_id: int, timeout: float = 60) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get("/api/crawl/status", params={"job_id": job_id}).json()
        if body["job"]["status"] not in ("queued", "running"):
            return body
        time.sleep(0.2)
    raise AssertionError("crawl did not finish")


@pytest.fixture(scope="module")
def api(site, tmp_path_factory):
    import dataclasses
    from quirksearch.config import Settings
    settings = dataclasses.replace(Settings(), db_path=tmp_path_factory.mktemp("api") / "api.db",
                                   per_host_delay=0.0, read_timeout=2.0)
    app = create_app(settings, auto_seed=False)
    with TestClient(app) as client:
        r = client.post("/api/crawl", json={"seeds": [f"{site}/corpus/index.html"], "max_depth": 2, "max_pages": 100})
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        # a second crawl while the first is running is rejected
        assert client.post("/api/crawl", json={"seeds": [f"{site}/corpus/index.html"]}).status_code == 409
        status = wait_for_crawl(client, job_id)
        assert status["job"]["status"] == "completed"
        client.app_settings = settings  # type: ignore[attr-defined]
        yield client


def test_health(api):
    body = api.get("/api/health").json()
    assert body["status"] == "ok" and body["documents"] >= 39
    assert api.app.state.crawler.wait(5) is None and api.get("/api/health").json()["crawl_running"] is False


def test_search_endpoint(api):
    r = api.get("/api/search", params={"q": "BM25 ranking"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0 and body["results"][0]["url"].endswith("/bm25.html")
    assert body["took_ms"] >= 0 and "X-Response-Time-ms" in r.headers
    first = body["results"][0]
    assert any(seg["highlight"] for seg in first["snippet"])
    assert 0 < first["relevance"] <= 1


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}, {"q": "x", "page": 0},
                                    {"q": "x", "page_size": 500}, {"q": "x" * 300}])
def test_search_validation(api, params):
    r = api.get("/api/search", params=params)
    assert r.status_code == 422
    assert "detail" in r.json()


def test_suggestions(api):
    body = api.get("/api/suggestions", params={"q": "netw"}).json()
    assert body["suggestions"] and all(s.startswith("netw") for s in body["suggestions"])
    assert api.get("/api/suggestions", params={"q": ""}).json()["suggestions"] == []


def test_stats_and_search_logging(api):
    before = api.get("/api/stats").json()
    api.get("/api/search", params={"q": "hash table"})
    after = api.get("/api/stats").json()
    assert after["searches"] == before["searches"] + 1
    assert after["documents"] >= 39 and after["terms"] > 500
    assert after["recent_searches"][0]["query"] == "hash table"
    assert 0 < after["crawl_success_rate"] <= 1
    assert after["errors_by_type"]["robots"] >= 1
    assert after["index"]["documents"] == after["documents"]


def test_documents_endpoints(api):
    body = api.get("/api/documents", params={"page_size": 5}).json()
    assert body["total"] >= 39 and len(body["documents"]) == 5
    doc_id = body["documents"][0]["id"]
    doc = api.get(f"/api/documents/{doc_id}").json()
    assert doc["unique_terms"] > 0 and "content_preview" in doc
    assert api.get("/api/documents/999999").status_code == 404


def test_crawl_validation_and_status(api):
    assert api.post("/api/crawl", json={"seeds": ["ftp://example.com/"]}).status_code == 422
    assert api.post("/api/crawl", json={"max_depth": 50}).status_code == 422
    assert api.post("/api/crawl", json={"max_pages": 0}).status_code == 422
    assert api.post("/api/crawl/cancel").status_code == 409
    status = api.get("/api/crawl/status").json()
    assert status["job"]["status"] == "completed" and status["running"] is False
    assert api.get("/api/crawl/status", params={"job_id": 9999}).status_code == 404
    assert len(api.get("/api/crawl/jobs").json()["jobs"]) >= 1


def test_unknown_route_and_static(api):
    assert api.get("/api/nope").status_code == 404
    assert "Disallow: /corpus/private/" in api.get("/robots.txt").text
    assert api.get("/corpus/bm25.html").status_code == 200


def test_rate_limiter_unit():
    limiter = TokenBucketLimiter(rate=1.0, capacity=3)
    assert [limiter.allow("ip")[0] for _ in range(4)] == [True, True, True, False]
    allowed, retry, _ = limiter.allow("ip")
    assert not allowed and 0 < retry <= 1.0
    assert limiter.allow("other-ip")[0]  # buckets are per client


def test_rate_limit_returns_429(api):
    original = api.app.state.limiter
    api.app.state.limiter = TokenBucketLimiter(rate=0.5, capacity=2)
    try:
        codes = [api.get("/api/suggestions", params={"q": "a"}).status_code for _ in range(4)]
        assert codes[:2] == [200, 200] and codes[-1] == 429
        r = api.get("/api/suggestions", params={"q": "a"})
        assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    finally:
        api.app.state.limiter = original


def test_index_survives_app_restart(api):
    settings = api.app_settings
    count = api.get("/api/health").json()["documents"]
    top = api.get("/api/search", params={"q": "inverted index"}).json()["results"][0]["url"]
    with TestClient(create_app(settings, auto_seed=False)) as fresh:
        assert fresh.get("/api/health").json()["documents"] == count
        assert fresh.get("/api/search", params={"q": "inverted index"}).json()["results"][0]["url"] == top
