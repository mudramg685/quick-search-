"""In-memory inverted index.

Structure (all hash maps → O(1) average access):

    postings : term   -> { doc_id: tf }      the inverted index proper
    doc_len  : doc_id -> |d|                 document length for BM25 normalization
    forward  : doc_id -> [terms]             forward index, enables O(|d|) deletion

Example after indexing three tiny documents
    d1 "database index"   d2 "network protocol"   d3 "database network"

    "databas"  -> {1: 1, 3: 1}      df = 2
    "index"    -> {1: 1}            df = 1
    "network"  -> {2: 1, 3: 1}      df = 2
    "protocol" -> {2: 1}            df = 1

*Document frequency* df(t) is simply ``len(postings[t])`` – the number of documents whose
postings entry exists for t – so it is always consistent with the postings themselves.

Why it beats a scan: a query for "network" reads one postings list of df("network")
entries instead of tokenizing all N documents. Query cost is O(Σ df(tᵢ)) – the number
of postings touched – which for selective terms is a tiny fraction of N.

The SQLite tables ``terms`` and ``postings`` are the durable copy; this object is rebuilt
from them at startup (``Repository.load_index``) and updated incrementally after crawls.
"""
from __future__ import annotations

from collections import Counter


class InvertedIndex:
    def __init__(self) -> None:
        self.postings: dict[str, dict[int, int]] = {}
        self.doc_len: dict[int, int] = {}
        self.forward: dict[int, list[str]] = {}
        self.total_len = 0

    # --- statistics -------------------------------------------------------------------
    @property
    def num_docs(self) -> int:
        return len(self.doc_len)

    @property
    def avg_doc_len(self) -> float:
        return self.total_len / self.num_docs if self.num_docs else 0.0

    @property
    def num_terms(self) -> int:
        return len(self.postings)

    def df(self, term: str) -> int:
        return len(self.postings.get(term, ()))

    def get_postings(self, term: str) -> dict[int, int]:
        return self.postings.get(term, {})

    # --- updates ---------------------------------------------------------------------------
    def add_document(self, doc_id: int, term_freqs: Counter | dict[str, int], length: int) -> None:
        """Insert (or replace) a document. O(|unique terms in d|)."""
        if doc_id in self.doc_len:
            self.remove_document(doc_id)
        for term, tf in term_freqs.items():
            self.postings.setdefault(term, {})[doc_id] = tf
        self.forward[doc_id] = list(term_freqs.keys())
        self.doc_len[doc_id] = length
        self.total_len += length

    def remove_document(self, doc_id: int) -> None:
        """Delete a document's postings; drop terms whose postings become empty (df=0)."""
        for term in self.forward.pop(doc_id, ()):
            plist = self.postings.get(term)
            if plist is not None:
                plist.pop(doc_id, None)
                if not plist:
                    del self.postings[term]
        self.total_len -= self.doc_len.pop(doc_id, 0)

    def add_posting(self, term: str, doc_id: int, tf: int) -> None:
        """Bulk-load helper used when rebuilding from the database."""
        self.postings.setdefault(term, {})[doc_id] = tf
        self.forward.setdefault(doc_id, []).append(term)

    def set_doc_len(self, doc_id: int, length: int) -> None:
        self.total_len += length - self.doc_len.get(doc_id, 0)
        self.doc_len[doc_id] = length
