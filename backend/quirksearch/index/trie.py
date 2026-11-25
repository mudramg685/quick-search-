"""Prefix trie for autocomplete.

Each node maps a character to a child node (a hash map, so any alphabet works). A word's
weight (its frequency) is stored at the node where the word ends.

* insert(word)         O(L)                      L = word length
* complete(prefix, k)  O(P + S log k)            P = prefix length, S = nodes in the subtree

Top-k completions are chosen with a bounded min-heap (``heapq.nlargest``) instead of
sorting all candidates.
"""
from __future__ import annotations

import heapq


class _Node:
    __slots__ = ("children", "weight")

    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.weight = 0  # > 0 ⇔ a word ends here


class Trie:
    def __init__(self) -> None:
        self.root = _Node()
        self.size = 0

    def insert(self, word: str, weight: int = 1) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, _Node())
        if node.weight == 0:
            self.size += 1
        node.weight += weight

    def _find(self, prefix: str) -> _Node | None:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def contains(self, word: str) -> bool:
        node = self._find(word)
        return bool(node and node.weight)

    def complete(self, prefix: str, k: int = 8, max_visit: int = 50_000) -> list[tuple[str, int]]:
        """Return up to ``k`` (word, weight) pairs starting with ``prefix``, heaviest first."""
        start = self._find(prefix)
        if start is None:
            return []
        found: list[tuple[str, int]] = []
        stack = [(start, prefix)]  # iterative DFS – no recursion limit issues
        visited = 0
        while stack and visited < max_visit:
            node, word = stack.pop()
            visited += 1
            if node.weight:
                found.append((word, node.weight))
            for ch, child in node.children.items():
                stack.append((child, word + ch))
        # ties broken alphabetically (shorter/earlier words first)
        return heapq.nsmallest(k, found, key=lambda wf: (-wf[1], wf[0]))
