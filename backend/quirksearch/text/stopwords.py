"""English stop words: extremely frequent function words with near-zero IDF.

Stored in a ``frozenset`` → O(1) average membership test during tokenization.
"""

STOP_WORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because been before
being below between both but by can can't cannot could couldn't did didn't do does doesn't
doing don't down during each few for from further had hadn't has hasn't have haven't having he
he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've if in
into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once
only or other ought our ours ourselves out over own same shan't she she'd she'll she's should
shouldn't so some such than that that's the their theirs them themselves then there there's
these they they'd they'll they're they've this those through to too under until up very was
wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while
who who's whom why why's will with won't would wouldn't you you'd you'll you're you've your
yours yourself yourselves also may might must shall us via etc per
""".split())
# Apostrophes are stripped by the tokenizer ("don't" → "dont"), so add those forms too.
STOP_WORDS = STOP_WORDS | frozenset(w.replace("'", "") for w in STOP_WORDS)
