"""Pydantic models: request validation + OpenAPI documentation (/docs)."""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, field_validator


class CrawlRequest(BaseModel):
    seeds: list[HttpUrl] = Field(default_factory=list, max_length=10,
                                 description="Seed URLs. Empty ⇒ the bundled QuirkPedia corpus.")
    max_depth: int = Field(2, ge=0, le=5, description="BFS depth limit (0 = seeds only)")
    max_pages: int = Field(100, ge=1, le=1000, description="Maximum number of pages to fetch")
    same_domain_only: bool = Field(True, description="Stay on the seeds' domains (recommended)")

    @field_validator("seeds")
    @classmethod
    def http_only(cls, v: list[HttpUrl]) -> list[HttpUrl]:
        for url in v:
            if url.scheme not in ("http", "https"):
                raise ValueError("only http(s) URLs can be crawled")
        return v


class Segment(BaseModel):
    text: str
    highlight: bool


class SearchResult(BaseModel):
    rank: int
    doc_id: int
    url: str
    domain: str
    title: str
    title_segments: list[Segment]
    snippet: list[Segment]
    description: str
    score: float = Field(description="Raw BM25 score")
    relevance: float = Field(description="Score relative to the best hit (0–1)")
    matched_terms: int
    query_terms: int
    term_scores: dict[str, float] = Field(description="BM25 contribution of each matched term")
    fetched_at: str


class Facet(BaseModel):
    domain: str
    count: int


class SearchResponse(BaseModel):
    query: str
    normalized_query: str
    terms: list[str]
    excluded: list[str]
    domain: str | None
    total: int
    page: int
    page_size: int
    took_ms: float
    results: list[SearchResult]
    facets: list[Facet]
    did_you_mean: str | None
    index_size: int


class SuggestionResponse(BaseModel):
    query: str
    suggestions: list[str]


class CrawlStarted(BaseModel):
    job_id: int
    status: str
    seeds: list[str]
