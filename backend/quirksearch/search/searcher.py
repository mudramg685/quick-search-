"""Query execution: parse → retrieve → score (BM25) → Top-K (heap) → snippets.

Query language (small but useful):
    bm25 ranking            documents matching any term, ranked (OR semantics)
    +required term          "+" forces a term to appear (AND for that term)
    -excluded               documents containing the term are dropped
    site:example.com        restrict to a domain (or pass ``domain=``)
    "write ahead log"       exact phrase: the stemmed words must appear consecutively

Ranking is BM25 times a *coverage* factor (1 + matched) / (1 + |query terms|), so a page
that contains every query word beats one that repeats a single rare word (Lucene's classic
"coord" idea, smoothed). When nothing matches and a spelling fix exists, the corrected query
is run automatically (``autocorrect``) - the response says so in ``corrected_query``.

Retrieval is *term-at-a-time*: for each query term we walk its postings list once and
add that term's BM25 contribution into a score accumulator (a hash map doc_id → score).
Work = O(Σ df(t)) – only documents containing at least one query term are ever touched.

Top-K: ``heapq.nlargest(k, …)`` keeps a min-heap of size k while scanning the m candidate
scores ⇒ O(m log k) time, O(k) extra memory, versus O(m log m) for a full sort.
"""
from __future__ import annotations

import heapq
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field

from ..config import Settings
from ..db.repository import Repository
from ..index.inverted_index import InvertedIndex
from ..index.trie import Trie
from ..text.analyzer import is_indexable, normalize, tokenize
from ..text.porter import stem
from .bm25 import idf, term_score
from .snippets import highlight, make_snippet

_SITE = re.compile(r"\bsite:([^\s]+)", re.I)
# a chunk is either an (optionally +/-) quoted phrase or a run of non-space characters
_CHUNK = re.compile(r'([+-]?)"([^"]*)"?|(\S+)')


@dataclass
class ParsedQuery:
    raw: str
    terms: list[str]                 # stemmed terms used for scoring (deduplicated, ordered)
    required: set[str] = field(default_factory=set)
    excluded: set[str] = field(default_factory=set)
    domain: str | None = None
    words: list[str] = field(default_factory=list)  # surface words (for spelling suggestions)
    phrases: list[list[str]] = field(default_factory=list)  # quoted phrases as stemmed term lists

    @property
    def normalized(self) -> str:
        return " ".join(self.words)


def parse_query(raw: str) -> ParsedQuery:
    domain = None
    m = _SITE.search(raw)
    if m:
        domain = m.group(1).lower().strip("/")
        raw_wo_site = _SITE.sub(" ", raw)
    else:
        raw_wo_site = raw
    terms: list[str] = []
    required, excluded, words, phrases = set(), set(), [], []
    for m in _CHUNK.finditer(raw_wo_site):
        if m.group(3) is not None:
            chunk = m.group(3)
            prefix = chunk[0] if chunk[0] in "+-" and len(chunk) > 1 else ""
            body, quoted = (chunk[1:] if prefix else chunk), False
        else:
            prefix, body, quoted = m.group(1), m.group(2), True
        phrase: list[str] = []
        for tok in tokenize(body):
            if not is_indexable(tok):
                continue
            t = stem(tok)
            if prefix == "-":
                excluded.add(t)
                continue
            words.append(tok)
            phrase.append(t)
            if prefix == "+" or quoted:
                required.add(t)
            if t not in terms:
                terms.append(t)
        if quoted and len(phrase) > 1:
            phrases.append(phrase)
    return ParsedQuery(raw=raw, terms=terms, required=required, excluded=excluded, domain=domain, words=words,
                       phrases=phrases)


def coverage(matched: int, n_terms: int) -> float:
    """Smoothed share of query terms a page contains: 1.0 when it has all of them."""
    return (1 + matched) / (1 + n_terms) if n_terms else 1.0


def term_sequence(text: str) -> list[str]:
    """The stemmed, indexable token stream of a text - what a phrase is matched against."""
    return [stem(t) for t in tokenize(text) if is_indexable(t)]


def contains_phrase(seq: list[str], phrase: list[str]) -> bool:
    n, first = len(phrase), phrase[0]
    return any(seq[i] == first and seq[i:i + n] == phrase for i in range(len(seq) - n + 1))


def replace_words(raw: str, fixes: dict[str, str]) -> str | None:
    """Swap misspelled words inside the raw query, keeping operators, quotes and site:."""
    out = raw
    for wrong, right in fixes.items():
        new = re.sub(rf"(?<!\w){re.escape(wrong)}(?!\w)", right, out, flags=re.I)
        if new == out:
            return None
        out = new
    return out


def levenshtein(a: str, b: str, limit: int = 2) -> int:
    """Edit distance with early exit once every cell of a DP row exceeds ``limit``."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


@dataclass
class _Snapshot:
    index: InvertedIndex
    words: Trie
    doc_domain: dict[int, str]
    loaded_at: float


class SearchEngine:
    def __init__(self, repo: Repository, settings: Settings):
        self.repo = repo
        self.settings = settings
        self.queries = Trie()
        self._reload_lock = threading.Lock()
        self.snapshot = _Snapshot(InvertedIndex(), Trie(), {}, 0.0)
        self.reload()

    # ------------------------------------------------------------------ index lifecycle
    def reload(self) -> float:
        """Rebuild the in-memory index from SQLite, then swap it in atomically.
        Searches in flight keep using the old snapshot – readers never see a half-built index."""
        with self._reload_lock:
            t0 = time.perf_counter()
            index, words = self.repo.load_index()
            snap = _Snapshot(index, words, self.repo.doc_domains(), time.time())
            queries = Trie()
            for q, n in self.repo.popular_queries():
                queries.insert(q, n)
            self.snapshot, self.queries = snap, queries  # single reference assignment = atomic swap
            return (time.perf_counter() - t0) * 1000

    # ------------------------------------------------------------------ search
    def search(self, raw_query: str, page: int = 1, page_size: int = 10, domain: str | None = None,
               autocorrect: bool = True) -> dict:
        t0 = time.perf_counter()
        snap = self.snapshot
        idx = snap.index
        q = parse_query(raw_query)
        domain = (domain or q.domain or "").lower() or None
        k1, b = self.settings.bm25_k1, self.settings.bm25_b
        n_docs, avgdl = idx.num_docs, idx.avg_doc_len

        # 1. retrieve + score: term-at-a-time accumulation into a hash map
        scores: dict[int, float] = {}
        matched: dict[int, int] = {}
        idfs = {t: idf(n_docs, idx.df(t)) for t in q.terms}
        for term in q.terms:
            for doc_id, tf in idx.get_postings(term).items():
                scores[doc_id] = scores.get(doc_id, 0.0) + term_score(tf, idx.doc_len[doc_id], avgdl, idfs[term], k1, b)
                matched[doc_id] = matched.get(doc_id, 0) + 1

        # 2. boolean constraints and domain facet counts
        def allowed(doc_id: int) -> bool:
            if q.required and any(doc_id not in idx.get_postings(t) for t in q.required):
                return False
            if q.excluded and any(doc_id in idx.get_postings(t) for t in q.excluded):
                return False
            return True

        candidates = {d: s * coverage(matched[d], len(q.terms)) for d, s in scores.items() if allowed(d)}
        if q.phrases and candidates:
            texts = self.repo.fetch_texts(list(candidates))

            def has_phrases(doc_id: int) -> bool:
                title, content = texts.get(doc_id, ("", ""))
                seqs = (term_sequence(title), term_sequence(content))
                return all(any(contains_phrase(seq, ph) for seq in seqs) for ph in q.phrases)

            candidates = {d: s for d, s in candidates.items() if has_phrases(d)}
        facets = Counter(snap.doc_domain.get(d, "?") for d in candidates)
        if domain:
            candidates = {d: s for d, s in candidates.items()
                          if snap.doc_domain.get(d) == domain or snap.doc_domain.get(d, "").endswith("." + domain)}

        # 3. Top-K with a bounded heap: only page*page_size best are materialized
        k = page * page_size
        top = heapq.nlargest(k, candidates.items(), key=lambda kv: (kv[1], -kv[0]))
        page_hits = top[(page - 1) * page_size:]
        max_score = top[0][1] if top else 1.0

        # 4. fetch display data for just this page and build snippets
        docs = self.repo.fetch_documents([d for d, _ in page_hits])
        qset = set(q.terms)
        results = []
        for rank, (doc_id, score) in enumerate(page_hits, start=(page - 1) * page_size + 1):
            doc = docs.get(doc_id)
            if not doc:
                continue
            breakdown = {
                t: round(term_score(idx.get_postings(t).get(doc_id, 0), idx.doc_len[doc_id], avgdl, idfs[t], k1, b), 4)
                for t in q.terms if doc_id in idx.get_postings(t)
            }
            results.append({
                "rank": rank,
                "doc_id": doc_id,
                "url": doc["url"],
                "domain": doc["domain"],
                "title": doc["title"],
                "title_segments": highlight(doc["title"], qset),
                "snippet": make_snippet(doc["content"], doc["description"], qset),
                "description": doc["description"],
                "score": round(score, 4),
                "relevance": round(score / max_score, 4) if max_score else 0.0,
                "matched_terms": matched.get(doc_id, 0),
                "query_terms": len(q.terms),
                "coverage": round(coverage(matched.get(doc_id, 0), len(q.terms)), 4),
                "term_scores": breakdown,
                "fetched_at": doc["fetched_at"],
            })

        # unknown words get a suggestion even when other words matched ("netwrk protocol")
        did_you_mean = self.spelling_suggestion(q)
        if did_you_mean and autocorrect and not candidates:
            fixed = self.search(did_you_mean, page, page_size, domain, autocorrect=False)
            if fixed["total"]:
                fixed.update(query=raw_query, corrected_query=did_you_mean, did_you_mean=None,
                             took_ms=round((time.perf_counter() - t0) * 1000, 3))
                return fixed

        took_ms = (time.perf_counter() - t0) * 1000
        return {
            "query": raw_query,
            "normalized_query": q.normalized,
            "terms": q.terms,
            "excluded": sorted(q.excluded),
            "domain": domain,
            "total": len(candidates),
            "page": page,
            "page_size": page_size,
            "took_ms": round(took_ms, 3),
            "results": results,
            "facets": [{"domain": d, "count": c} for d, c in facets.most_common(10)],
            "did_you_mean": did_you_mean,
            "corrected_query": None,
            "phrases": [" ".join(p) for p in q.phrases],
            "index_size": n_docs,
        }

    def record_query(self, normalized: str) -> None:
        if normalized:
            self.queries.insert(normalized, 1)

    # ------------------------------------------------------------------ spelling + autocomplete
    def _correct_word(self, word: str) -> str | None:
        words = self.snapshot.words
        if words.contains(word) or len(word) < 3:
            return None
        limit = 1 if len(word) <= 4 else 2
        best: tuple[int, int, str] | None = None
        # candidates share the first letter (cheap pruning), weighted by corpus frequency
        for cand, freq in words.complete(word[0], k=100_000):
            d = levenshtein(word, cand, limit)
            if d <= limit and (best is None or (d, -freq) < (best[0], best[1])):
                best = (d, -freq, cand)
        return best[2] if best else None

    def spelling_suggestion(self, q: ParsedQuery) -> str | None:
        if not q.words:
            return None
        fixes = {w: f for w in dict.fromkeys(q.words) if (f := self._correct_word(w))}
        if not fixes:
            return None
        return replace_words(q.raw, fixes) or " ".join(fixes.get(w, w) for w in q.words)

    def suggest(self, prefix: str, limit: int = 8) -> list[str]:
        text = normalize(prefix).strip()
        if not text:
            return []
        seen: list[str] = []

        def add(s: str) -> None:
            if s not in seen and s != text:
                seen.append(s)

        # 1. popular past queries starting with the full typed text
        for q, _ in self.queries.complete(text, limit):
            add(q)
        # 2. complete the last word from the corpus vocabulary
        head, _, last = text.rpartition(" ")
        last = re.sub(r"[^\w]", "", last)
        if last:
            for w, _ in self.snapshot.words.complete(last, limit * 2):
                add(f"{head} {w}".strip())
                if len(seen) >= limit:
                    break
        return seen[:limit]
