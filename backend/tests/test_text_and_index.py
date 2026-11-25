"""Phase 3 – text processing, inverted index and trie."""
from __future__ import annotations

from collections import Counter

import pytest

from quirksearch.index.inverted_index import InvertedIndex
from quirksearch.index.trie import Trie
from quirksearch.text.analyzer import analyze, analyze_document, tokenize
from quirksearch.text.porter import stem

# Examples taken from Porter (1980) and his reference vocabulary/output files.
PORTER_CASES = {
    "caresses": "caress", "ponies": "poni", "ties": "ti", "caress": "caress", "cats": "cat",
    "feed": "feed", "agreed": "agre", "plastered": "plaster", "bled": "bled", "motoring": "motor",
    "sing": "sing", "conflated": "conflat", "troubled": "troubl", "sized": "size", "hopping": "hop",
    "tanned": "tan", "falling": "fall", "hissing": "hiss", "fizzed": "fizz", "failing": "fail",
    "filing": "file", "happy": "happi", "sky": "sky", "relational": "relat", "conditional": "condit",
    "rational": "ration", "valenci": "valenc", "hesitanci": "hesit", "digitizer": "digit",
    "conformabli": "conform", "radicalli": "radic", "differentli": "differ", "vileli": "vile",
    "analogousli": "analog", "vietnamization": "vietnam", "predication": "predic", "operator": "oper",
    "feudalism": "feudal", "decisiveness": "decis", "hopefulness": "hope", "callousness": "callous",
    "formaliti": "formal", "sensitiviti": "sensit", "sensibiliti": "sensibl", "triplicate": "triplic",
    "formative": "form", "formalize": "formal", "electriciti": "electr", "electrical": "electr",
    "hopeful": "hope", "goodness": "good", "revival": "reviv", "allowance": "allow",
    "inference": "infer", "airliner": "airlin", "gyroscopic": "gyroscop", "adjustable": "adjust",
    "defensible": "defens", "irritant": "irrit", "replacement": "replac", "adjustment": "adjust",
    "dependent": "depend", "adoption": "adopt", "homologou": "homolog", "communism": "commun",
    "activate": "activ", "angulariti": "angular", "homologous": "homolog", "effective": "effect",
    "bowdlerize": "bowdler", "probate": "probat", "rate": "rate", "cease": "ceas",
    "controll": "control", "roll": "roll", "generalization": "gener", "oscillators": "oscil",
    "connection": "connect", "connected": "connect", "connecting": "connect", "connections": "connect",
}


@pytest.mark.parametrize("word,expected", sorted(PORTER_CASES.items()))
def test_porter_stemmer(word, expected):
    assert stem(word) == expected


def test_tokenize_and_analyze():
    assert tokenize("Hello, World! It's TCP/IP's day—café_au_lait") == \
        ["hello", "world", "its", "tcp", "ips", "day", "café", "au", "lait"]
    # stop words removed, stems applied, numbers kept
    assert analyze("The databases are connected to the networks via HTTP 404") == \
        ["databas", "connect", "network", "http", "404"]
    # query and document normalize to the same terms
    assert analyze("Connecting Databases") == analyze("connected database")


def test_analyze_document_field_weighting():
    doc = analyze_document("BM25 ranking", ["Scoring"], "BM25 ranking scoring uses term frequency")
    # body 1 + title weight 3
    assert doc.term_freqs["bm25"] == 4
    assert doc.term_freqs["score"] == 2  # body 1 + heading 1
    assert doc.term_freqs["frequenc"] == 1
    assert doc.length == 6
    assert doc.surface_to_term["ranking"] == "rank"


def test_inverted_index_postings_and_df():
    idx = InvertedIndex()
    idx.add_document(1, Counter(analyze("database index")), 2)
    idx.add_document(2, Counter(analyze("network protocol")), 2)
    idx.add_document(3, Counter(analyze("database network network")), 3)
    assert idx.get_postings("databas") == {1: 1, 3: 1}
    assert idx.get_postings("network") == {2: 1, 3: 2}
    assert idx.df("databas") == 2 and idx.df("protocol") == 1 and idx.df("missing") == 0
    assert idx.num_docs == 3 and idx.num_terms == 4
    assert idx.avg_doc_len == pytest.approx(7 / 3)

    # update: re-adding a document replaces its old postings
    idx.add_document(3, Counter(analyze("protocol")), 1)
    assert idx.get_postings("network") == {2: 1}
    assert idx.df("protocol") == 2 and idx.df("databas") == 1

    # delete: terms whose df drops to zero disappear from the dictionary
    idx.remove_document(1)
    assert "index" not in idx.postings and idx.df("databas") == 0
    assert idx.num_docs == 2 and idx.total_len == 3


def test_trie_completion():
    t = Trie()
    for word, w in [("data", 5), ("database", 9), ("datagram", 2), ("date", 4), ("dns", 7)]:
        t.insert(word, w)
    t.insert("data", 1)  # weights accumulate
    assert t.complete("dat", 3) == [("database", 9), ("data", 6), ("date", 4)]
    assert t.complete("x") == []
    assert t.contains("dns") and not t.contains("dn")
    assert t.size == 5
