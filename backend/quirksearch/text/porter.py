"""Porter stemming algorithm (M. F. Porter, "An algorithm for suffix stripping", 1980).

Stemming conflates morphological variants – connect, connected, connecting, connection –
to one index term ("connect"), so a query for one form matches documents using another.

Definitions used by the rules:
* a *consonant* is a letter other than a, e, i, o, u, and other than y preceded by a consonant
* any word has the form  [C](VC)^m[V]  – ``m`` (the *measure*) counts VC sequences
* rules are written  (condition) S1 → S2 : replace suffix S1 by S2 if the stem before S1
  satisfies the condition, e.g. (m>0) ATIONAL → ATE turns "relational" into "relate".

The algorithm runs five steps in order; each step applies at most one rule (longest
matching suffix). Runs in O(L) per word for a word of length L. Results are memoized
with an LRU cache because natural-language text repeats words heavily (Zipf's law).
"""
from __future__ import annotations

from functools import lru_cache


class _Stemmer:
    def __init__(self, word: str):
        self.b = word
        self.k = len(word) - 1  # index of the last character of the current word
        self.j = 0              # end of the stem when a suffix matched

    # --- helpers -------------------------------------------------------------------------
    def cons(self, i: int) -> bool:
        ch = self.b[i]
        if ch in "aeiou":
            return False
        if ch == "y":
            return i == 0 or not self.cons(i - 1)
        return True

    def m(self) -> int:
        """Measure of b[0..j]: the number of VC sequences."""
        n, i = 0, 0
        while True:
            if i > self.j:
                return n
            if not self.cons(i):
                break
            i += 1
        i += 1
        while True:
            while True:
                if i > self.j:
                    return n
                if self.cons(i):
                    break
                i += 1
            i += 1
            n += 1
            while True:
                if i > self.j:
                    return n
                if not self.cons(i):
                    break
                i += 1
            i += 1

    def vowel_in_stem(self) -> bool:
        return any(not self.cons(i) for i in range(0, self.j + 1))

    def double_c(self, j: int) -> bool:
        return j >= 1 and self.b[j] == self.b[j - 1] and self.cons(j)

    def cvc(self, i: int) -> bool:
        """consonant-vowel-consonant ending, where the last c is not w, x or y (e.g. -hop)."""
        if i < 2 or not self.cons(i) or self.cons(i - 1) or not self.cons(i - 2):
            return False
        return self.b[i] not in "wxy"

    def ends(self, s: str) -> bool:
        length = len(s)
        if length > self.k + 1 or self.b[self.k - length + 1:self.k + 1] != s:
            return False
        self.j = self.k - length
        return True

    def set_to(self, s: str) -> None:
        self.b = self.b[:self.j + 1] + s
        self.k = self.j + len(s)

    def r(self, s: str) -> None:
        if self.m() > 0:
            self.set_to(s)

    # --- steps ----------------------------------------------------------------------------
    def step1ab(self) -> None:
        """Plurals and -ed / -ing:  caresses→caress, ponies→poni, cats→cat, motoring→motor."""
        if self.b[self.k] == "s":
            if self.ends("sses"):
                self.k -= 2
            elif self.ends("ies"):
                self.set_to("i")
            elif self.b[self.k - 1] != "s":
                self.k -= 1
        self.b = self.b[:self.k + 1]
        if self.ends("eed"):
            if self.m() > 0:
                self.k -= 1
        elif (self.ends("ed") or self.ends("ing")) and self.vowel_in_stem():
            self.k = self.j
            self.b = self.b[:self.k + 1]
            if self.ends("at"):
                self.set_to("ate")
            elif self.ends("bl"):
                self.set_to("ble")
            elif self.ends("iz"):
                self.set_to("ize")
            elif self.double_c(self.k):
                if self.b[self.k] not in "lsz":
                    self.k -= 1          # hopping→hop, but falling→fall
            elif self.m() == 1 and self.cvc(self.k):
                self.j = self.k
                self.set_to("e")         # filing→file
        self.b = self.b[:self.k + 1]

    def step1c(self) -> None:
        """y → i when there is another vowel in the stem: happy→happi."""
        if self.ends("y") and self.vowel_in_stem():
            self.b = self.b[:self.k] + "i"

    _STEP2 = {
        "a": (("ational", "ate"), ("tional", "tion")),
        "c": (("enci", "ence"), ("anci", "ance")),
        "e": (("izer", "ize"),),
        "l": (("bli", "ble"), ("alli", "al"), ("entli", "ent"), ("eli", "e"), ("ousli", "ous")),
        "o": (("ization", "ize"), ("ation", "ate"), ("ator", "ate")),
        "s": (("alism", "al"), ("iveness", "ive"), ("fulness", "ful"), ("ousness", "ous")),
        "t": (("aliti", "al"), ("iviti", "ive"), ("biliti", "ble")),
        "g": (("logi", "log"),),
    }
    _STEP3 = {
        "e": (("icate", "ic"), ("ative", ""), ("alize", "al")),
        "i": (("iciti", "ic"),),
        "l": (("ical", "ic"), ("ful", "")),
        "s": (("ness", ""),),
    }
    _STEP4 = {
        "a": ("al",), "c": ("ance", "ence"), "e": ("er",), "i": ("ic",), "l": ("able", "ible"),
        "n": ("ant", "ement", "ment", "ent"), "o": ("ion", "ou"), "s": ("ism",), "t": ("ate", "iti"),
        "u": ("ous",), "v": ("ive",), "z": ("ize",),
    }

    def _apply_table(self, table: dict, key: str) -> None:
        for suffix, repl in table.get(key, ()):
            if self.ends(suffix):
                self.r(repl)
                return

    def step2(self) -> None:
        """Double suffixes → single:  relational→relate, conditional→condition."""
        if self.k >= 1:
            self._apply_table(self._STEP2, self.b[self.k - 1])

    def step3(self) -> None:
        """-ic-, -full, -ness …:  electrical→electric, goodness→good."""
        self._apply_table(self._STEP3, self.b[self.k])

    def step4(self) -> None:
        """Remove -ant, -ence … when m>1:  revival→reviv, adoption→adopt."""
        if self.k < 1:
            return
        for suffix in self._STEP4.get(self.b[self.k - 1], ()):
            if self.ends(suffix):
                if suffix == "ion" and not (self.j >= 0 and self.b[self.j] in "st"):
                    continue
                if self.m() > 1:
                    self.k = self.j
                    self.b = self.b[:self.k + 1]
                return

    def step5(self) -> None:
        """Tidy up: remove final -e (probate→probat) and -ll → -l (controll→control)."""
        self.j = self.k
        if self.b[self.k] == "e":
            a = self.m()
            if a > 1 or (a == 1 and not self.cvc(self.k - 1)):
                self.k -= 1
        if self.b[self.k] == "l" and self.double_c(self.k) and self.m() > 1:
            self.k -= 1
        self.b = self.b[:self.k + 1]

    def run(self) -> str:
        if self.k <= 1:
            return self.b  # words of length 1–2 are left alone
        self.step1ab()
        if self.k >= 0:
            self.step1c()
            self.step2()
            self.step3()
            self.step4()
            self.step5()
        return self.b[:self.k + 1]


@lru_cache(maxsize=100_000)
def stem(word: str) -> str:
    """Return the Porter stem of a lowercase word."""
    if not word.isalpha():
        return word  # leave numbers / alphanumerics such as "http2" or "404" untouched
    return _Stemmer(word).run()
