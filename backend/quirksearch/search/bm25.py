r"""Okapi BM25 ranking.

For a query Q = {q₁ … qₙ} and a document D:

    score(D, Q) = Σᵢ IDF(qᵢ) · tf(qᵢ, D) · (k₁ + 1)
                             ─────────────────────────────────────────
                             tf(qᵢ, D) + k₁ · (1 − b + b · |D| / avgdl)

    IDF(q) = ln( 1 + (N − df(q) + 0.5) / (df(q) + 0.5) )

* N      – number of indexed documents;   df(q) – documents containing q
* tf     – (field-weighted) frequency of q in D
* |D|    – document length in tokens;     avgdl – average document length
* k₁     – term-frequency saturation (1.2): the 1st occurrence matters most, the 10th little
* b      – length normalization (0.75): a match in a short page counts more than in a long one

Intuition:
* **IDF** rewards rare terms. "bm25" (df small) is far more informative than "data".
  The "1 +" inside the log (Lucene's variant) keeps IDF positive even for very common terms.
* **TF saturation**: as tf → ∞ the fraction approaches (k₁ + 1), so keyword stuffing has
  bounded benefit – unlike raw TF-IDF, which grows linearly.
* **Length normalization**: the denominator grows with |D|/avgdl, so long pages that
  mention a term once in passing do not beat focused pages.
"""
from __future__ import annotations

import math


def idf(n_docs: int, df: int) -> float:
    return math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))


def term_score(tf: float, doc_len: int, avgdl: float, idf_value: float, k1: float = 1.2, b: float = 0.75) -> float:
    if tf <= 0:
        return 0.0
    norm = k1 * (1.0 - b + b * (doc_len / avgdl if avgdl else 1.0))
    return idf_value * (tf * (k1 + 1.0)) / (tf + norm)
