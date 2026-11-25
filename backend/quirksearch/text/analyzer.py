"""Text analysis pipeline shared by the indexer and the query processor.

    raw text ─► Unicode normalize (NFKC) + lowercase ─► strip apostrophes
             ─► tokenize (runs of letters/digits) ─► drop stop words & junk tokens
             ─► Porter stem ─► index terms

Using the *same* analyzer at index time and at query time is essential: the query
"Connecting Databases" must produce the very terms ["connect", "databas"] that were
stored for a document containing "connected database".
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from .porter import stem
from .stopwords import STOP_WORDS

# \w in Python's regex is Unicode-aware; exclude "_" so snake_case splits into words.
_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_APOSTROPHES = re.compile(r"['’ʼ]")
MIN_TOKEN_LEN = 2
MAX_TOKEN_LEN = 40


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return _APOSTROPHES.sub("", text)


def tokenize(text: str) -> list[str]:
    """Split into lowercase word tokens (no stop-word removal, no stemming)."""
    return _TOKEN.findall(normalize(text))


def is_indexable(token: str) -> bool:
    if token in STOP_WORDS:
        return False
    if not (MIN_TOKEN_LEN <= len(token) <= MAX_TOKEN_LEN):
        return token.isdigit() and len(token) <= MAX_TOKEN_LEN  # keep single digits like "3"
    return True


def analyze(text: str) -> list[str]:
    """Full pipeline → list of index terms (order preserved, duplicates kept)."""
    return [stem(t) for t in tokenize(text) if is_indexable(t)]


def analyze_pairs(text: str) -> list[tuple[str, str]]:
    """Like ``analyze`` but returns (surface_word, term) pairs – used for autocomplete
    vocabulary and for highlighting the original words in snippets."""
    return [(t, stem(t)) for t in tokenize(text) if is_indexable(t)]


# Field weights: a match in the title is a much stronger relevance signal than one buried
# in the body. Body text already contains the headings once, so these are *extra* counts.
TITLE_WEIGHT = 3
HEADING_WEIGHT = 1


@dataclass
class DocumentTerms:
    term_freqs: Counter          # term -> weighted term frequency
    length: int                  # number of indexable body tokens (|d| for BM25)
    surface_counts: Counter      # surface word -> count (autocomplete vocabulary)
    surface_to_term: dict        # surface word -> term


def analyze_document(title: str, headings: list[str], body: str) -> DocumentTerms:
    body_pairs = analyze_pairs(body)
    title_pairs = analyze_pairs(title)
    heading_pairs = analyze_pairs(" ".join(headings))

    tf: Counter = Counter(term for _, term in body_pairs)
    for _, term in title_pairs:
        tf[term] += TITLE_WEIGHT
    for _, term in heading_pairs:
        tf[term] += HEADING_WEIGHT

    surface_counts: Counter = Counter()
    surface_to_term: dict[str, str] = {}
    for word, term in (*body_pairs, *title_pairs):
        if word.isalpha() and len(word) >= 3:
            surface_counts[word] += 1
            surface_to_term[word] = term

    length = max(len(body_pairs), len(title_pairs), 1)
    return DocumentTerms(tf, length, surface_counts, surface_to_term)
