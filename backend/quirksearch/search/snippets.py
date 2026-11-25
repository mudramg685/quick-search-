"""Snippet generation and keyword highlighting.

Best-window algorithm (O(n) cheap filtering + O(m) window work, m = matching words):
  1. find the words that stem to a query term (prefix pre-filter, cached stemming)
  2. two-pointer sweep: for each match as window start, count matches within W words,
     adding entering matches and removing the leaving one incrementally
  3. keep the window with the most *distinct* query terms (ties → more total matches →
     earlier position)
The snippet is returned as segments ``[{"text": ..., "highlight": bool}]`` so the frontend
can render <mark> without ever injecting raw HTML (no XSS risk).
"""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

from ..text.analyzer import is_indexable, normalize
from ..text.porter import stem

_WORD_SPLIT = re.compile(r"(\w+)", re.UNICODE)
_CLEAN = re.compile(r"[^\w]", re.UNICODE)


@lru_cache(maxsize=200_000)
def _term_of(word: str) -> str | None:
    tok = _CLEAN.sub("", normalize(word))
    if not tok or not is_indexable(tok):
        return None
    return stem(tok)


def best_window(text: str, query_terms: set[str], window: int = 32) -> tuple[str, bool, bool]:
    """Return (snippet_text, starts_mid_text, ends_mid_text)."""
    words = text.split()
    if not words:
        return "", False, False
    if len(words) <= window or not query_terms:
        return " ".join(words[:window]), False, len(words) > window

    # 1. Candidate positions. Porter only rewrites suffixes, so a word can stem to a query
    #    term only if its first two letters equal the term's: an O(1) set test (run at C
    #    speed inside a comprehension) discards ~95% of words before normalize+stem.
    prefixes = {t[:2] for t in query_terms}
    lowered = text.lower().split()
    # w[1:3] also catches one leading punctuation char ('(index', '"query'); false positives
    # are harmless because stemming below confirms every candidate.
    cands = [i for i, w in enumerate(lowered) if w[:2] in prefixes or w[1:3] in prefixes]
    hits = [(i, t) for i in cands if (t := _term_of(words[i])) in query_terms]
    if not hits:
        return " ".join(words[:window]), False, True

    # 2. Two-pointer sweep over match positions only. An optimal window can always be
    #    shifted right until it starts at a match, so trying each match as the start is
    #    exhaustive. Counter tracks matches inside [hits[lo].pos, hits[lo].pos + window).
    counts: Counter = Counter()
    best_key, best_start = (-1, -1), 0
    hi = 0
    for lo, (start, _) in enumerate(hits):
        while hi < len(hits) and hits[hi][0] < start + window:
            counts[hits[hi][1]] += 1
            hi += 1
        key = (len(counts), sum(counts.values()))
        if key > best_key:
            best_key, best_start = key, start
        leaving = hits[lo][1]
        counts[leaving] -= 1
        if counts[leaving] == 0:
            del counts[leaving]

    # 3. Back off a few words so the first match isn't glued to the leading ellipsis.
    best_start = max(0, min(best_start - 4, len(words) - window))
    end = min(len(words), best_start + window)
    return " ".join(words[best_start:end]), best_start > 0, end < len(words)


def highlight(text: str, query_terms: set[str]) -> list[dict]:
    """Split ``text`` into segments, flagging words whose stem is a query term."""
    segments: list[dict] = []
    for part in _WORD_SPLIT.split(text):
        if not part:
            continue
        hl = bool(query_terms) and part[0].isalnum() and _term_of(part) in query_terms
        if segments and segments[-1]["highlight"] == hl:
            segments[-1]["text"] += part
        else:
            segments.append({"text": part, "highlight": hl})
    return segments


def make_snippet(content: str, description: str, query_terms: set[str], window: int = 32) -> list[dict]:
    text, lead, trail = best_window(content, query_terms, window)
    if not text:
        text, lead, trail = description, False, False
    segments = highlight(text, query_terms)
    if lead:
        segments.insert(0, {"text": "… ", "highlight": False})
    if trail:
        segments.append({"text": " …", "highlight": False})
    return segments
