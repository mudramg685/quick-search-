"""Snippet generation and keyword highlighting.

Best-window algorithm (sliding window, O(n) in the number of words):
  1. split the stored page text into words and mark which ones stem to a query term
  2. slide a fixed window of W words across the text, maintaining counts of matched terms
     incrementally (add the entering word, remove the leaving one)
  3. keep the window with the most *distinct* query terms (ties → more total matches →
     earlier position)
The snippet is returned as segments ``[{"text": ..., "highlight": bool}]`` so the frontend
can render <mark> without ever injecting raw HTML (no XSS risk).
"""
from __future__ import annotations

import re
from collections import Counter

from ..text.analyzer import is_indexable, normalize
from ..text.porter import stem

_WORD_SPLIT = re.compile(r"(\w+)", re.UNICODE)
_CLEAN = re.compile(r"[^\w]", re.UNICODE)


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

    marks = [(_term_of(w) if any(c.isalnum() for c in w) else None) for w in words]
    marks = [m if m in query_terms else None for m in marks]

    counts: Counter = Counter(m for m in marks[:window] if m)
    best_key = (len(counts), sum(counts.values()))
    best_start = 0
    for start in range(1, len(words) - window + 1):
        leaving, entering = marks[start - 1], marks[start + window - 1]
        if leaving:
            counts[leaving] -= 1
            if counts[leaving] == 0:
                del counts[leaving]
        if entering:
            counts[entering] += 1
        key = (len(counts), sum(counts.values()))
        if key > best_key:
            best_key, best_start = key, start

    # Nudge the window back a few words so the first match isn't the very first word.
    if best_start > 0:
        first_hit = next((i for i in range(best_start, best_start + window) if marks[i]), best_start)
        best_start = max(0, min(best_start, first_hit - 4))
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
