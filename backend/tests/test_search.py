"""Phase 5 – BM25 maths, Top-K, relevance on the real crawled corpus, snippets, suggestions."""
from __future__ import annotations

import dataclasses
import math

import pytest

from quirksearch.config import Settings
from quirksearch.db.repository import Repository
from quirksearch.search.bm25 import idf, term_score
from quirksearch.search.searcher import SearchEngine, levenshtein, parse_query
from quirksearch.search.snippets import best_window, highlight
from quirksearch.services.crawl_service import CrawlService


@pytest.fixture(scope="module")
def engine(site, tmp_path_factory):
    settings = dataclasses.replace(Settings(), db_path=tmp_path_factory.mktemp("db") / "s.db",
                                   per_host_delay=0.0, read_timeout=2.0)
    repo = Repository(settings.db_path)
    CrawlService(repo, settings, lambda: None).run_blocking([f"{site}/corpus/index.html"], 2, 100)
    yield SearchEngine(repo, settings)
    repo.close()


def slug(result: dict) -> str:
    return result["url"].rsplit("/", 1)[-1].removesuffix(".html")


# ------------------------------------------------------------------ BM25 properties
def test_bm25_idf_and_saturation():
    assert idf(100, 1) > idf(100, 10) > idf(100, 90) > 0  # rarer ⇒ higher, always positive
    assert idf(10, 2) == pytest.approx(math.log(1 + (10 - 2 + 0.5) / 2.5))
    s1, s2, s10, s100 = (term_score(tf, 100, 100, 1.0) for tf in (1, 2, 10, 100))
    assert s1 < s2 < s10 < s100 < 2.2  # monotonic but bounded by k1 + 1
    assert s2 - s1 > s100 - s10       # diminishing returns
    assert term_score(1, 50, 100, 1.0) > term_score(1, 400, 100, 1.0)  # shorter doc wins
    assert term_score(0, 100, 100, 1.0) == 0


# ------------------------------------------------------------------ relevance
@pytest.mark.parametrize("query,expected_top", [
    ("bm25", "bm25"),
    ("inverted index", "inverted-index"),
    ("tcp handshake", "tcp-ip"),
    ("domain name system resolver", "dns"),
    ("database normalization normal forms", "normalization"),
    ("robots exclusion protocol", "robots-txt"),
    ("priority queue heap", "heaps-priority-queues"),
    ("sourdough yeast fermentation", "sourdough-science"),
    ("octopus neurons", "octopus-intelligence"),
    ("porter stemming", "stemming"),
    ("ACID transactions durability", "transactions-acid"),
    ("breadth first search", "graph-traversal"),
    ("tries prefix trees", "tries"),
    ("autocomplete suggestions", "autocomplete"),
])
def test_relevance_top_result(engine, query, expected_top):
    res = engine.search(query)
    assert res["total"] > 0
    assert slug(res["results"][0]) == expected_top, [slug(r) for r in res["results"][:5]]


def test_porter_quirk_trie_vs_tries(engine):
    # Known Porter limitation (documented): "trie" -> "trie" but "tries" -> "tri", so they do
    # not conflate. The Autocomplete article, which says "trie", legitimately ranks first.
    res = engine.search("trie autocomplete prefix")
    assert slug(res["results"][0]) == "autocomplete"
    assert "tries" in [slug(r) for r in res["results"][:3]]


def test_ranking_is_sorted_and_topk_matches_full_sort(engine):
    res = engine.search("database index", page_size=50)
    scores = [r["score"] for r in res["results"]]
    assert scores == sorted(scores, reverse=True)
    assert res["results"][0]["relevance"] == 1.0
    # heap Top-K == brute-force full sort of every scored document
    full = engine.search("database index", page_size=1000)["results"]
    assert [r["doc_id"] for r in full[:10]] == [r["doc_id"] for r in engine.search("database index")["results"]]
    # term contributions add up to the total score
    top = res["results"][0]
    assert sum(top["term_scores"].values()) == pytest.approx(top["score"], abs=1e-3)


def test_pagination_has_no_overlap(engine):
    p1 = engine.search("network", page=1, page_size=5)
    p2 = engine.search("network", page=2, page_size=5)
    ids1, ids2 = {r["doc_id"] for r in p1["results"]}, {r["doc_id"] for r in p2["results"]}
    assert ids1 and ids2 and not ids1 & ids2
    assert p2["results"][0]["rank"] == 6
    assert p1["total"] == p2["total"]


def test_query_operators(engine):
    q = parse_query("+Database -sqlite indexing site:Example.com")
    assert q.terms == ["databas", "index"] and q.required == {"databas"}
    assert q.excluded == {"sqlite"} and q.domain == "example.com"

    with_sqlite = engine.search("database")
    without = engine.search("database -sqlite")
    assert without["total"] < with_sqlite["total"]
    assert all("sqlite" not in slug(r) for r in without["results"])

    # AND semantics with "+": every result must contain "heap"
    req = engine.search("+heap sorting")
    assert req["total"] > 0
    assert all("heap" in r["term_scores"] for r in req["results"])


def test_domain_filter_and_facets(engine):
    res = engine.search("database")
    domains = [f["domain"] for f in res["facets"]]
    assert domains == ["127.0.0.1"]
    assert engine.search("database", domain="127.0.0.1")["total"] == res["total"]
    assert engine.search("database", domain="nowhere.test")["total"] == 0


def test_no_results_and_stopword_only(engine):
    assert engine.search("xylophonequasar")["total"] == 0
    assert engine.search("the and of")["total"] == 0
    # robots-blocked and noindex pages are never searchable
    assert engine.search("flamingo protocol")["total"] == 0 or all(
        "private" not in r["url"] for r in engine.search("flamingo protocol")["results"])
    assert engine.search("zebrafish marmalade")["total"] == 0


def test_spelling_suggestion(engine):
    assert levenshtein("databse", "database") == 1
    assert levenshtein("kitten", "sitting", limit=5) == 3
    # a partial match still suggests the fix for the unknown word
    res = engine.search("netwrk protocol")
    assert res["total"] > 0 and res["corrected_query"] is None
    assert res["did_you_mean"] == "network protocol"
    assert engine.search("network protocol")["did_you_mean"] is None
    assert engine.search("databse", autocorrect=False)["did_you_mean"] == "database"
    assert engine.search("octopsu", autocorrect=False)["did_you_mean"] == "octopus"
    # operators and quotes survive the correction
    assert engine.search("+databse -sqlite", autocorrect=False)["did_you_mean"] == "+database -sqlite"


def test_autocorrect_runs_the_fixed_query(engine):
    res = engine.search("octopsu")
    assert res["corrected_query"] == "octopus" and res["did_you_mean"] is None
    assert res["query"] == "octopsu" and res["total"] > 0
    assert slug(res["results"][0]) == "octopus-intelligence"
    assert engine.search("octopus")["corrected_query"] is None


def test_phrase_queries(engine):
    q = parse_query('"write ahead log" durability')
    assert q.phrases == [["write", "ahead", "log"]]
    assert {"write", "ahead", "log"} <= q.required
    loose = engine.search("ahead log write")
    exact = engine.search('"write ahead log"')
    assert 0 < exact["total"] <= loose["total"]
    assert exact["phrases"] == ["write ahead log"]
    # word order matters inside quotes
    assert engine.search('"log ahead write"')["total"] < exact["total"]


def test_coverage_rewards_matching_every_term(engine):
    res = engine.search("python list comprehension", page_size=50)
    for r in res["results"]:
        assert r["coverage"] == pytest.approx((1 + r["matched_terms"]) / (1 + r["query_terms"]), abs=1e-4)
        assert r["score"] == pytest.approx(sum(r["term_scores"].values()) * r["coverage"], abs=2e-3)
    assert res["results"][0]["matched_terms"] == max(r["matched_terms"] for r in res["results"])


def test_snippets_and_highlighting(engine):
    r = engine.search("congestion control")["results"][0]
    text = "".join(s["text"] for s in r["snippet"])
    marked = {s["text"].lower() for s in r["snippet"] if s["highlight"]}
    assert "congestion control" in text.lower()
    assert any("congestion" in m for m in marked)
    assert any(s["highlight"] for s in r["title_segments"]) or "congestion" not in r["title"].lower()

    segs = highlight("Connected networks connect!", {"connect"})
    assert [s for s in segs if s["highlight"]] == [{"text": "Connected", "highlight": True},
                                                   {"text": "connect", "highlight": True}]
    words = " ".join(["filler"] * 100 + ["bm25", "ranking", "rocks"] + ["filler"] * 100)
    snippet, lead, trail = best_window(words, {"bm25", "rank"}, window=20)
    assert "bm25 ranking" in snippet and lead and trail


def test_autocomplete(engine):
    assert any(s.startswith("database") for s in engine.suggest("datab"))
    assert all(s.startswith("tcp ") for s in engine.suggest("tcp hand"))
    assert "tcp handshake" in engine.suggest("tcp hand")
    engine.record_query("load balancing")
    assert engine.suggest("load b")[0] == "load balancing"
    assert engine.suggest("   ") == []
