"""Symbol-name match, the third channel fed into hybrid retrieval fusion.

BM25 and TF-IDF vector search both score chunks by term frequency, which
structurally can't distinguish "this chunk is *about* Context" from "this
chunk merely mentions Context in passing" when the word appears hundreds
of times across the corpus (verified against a real repo: "context"
appeared 391 times in click's core.py alone, giving it very low IDF and
letting short, keyword-dense but far-less-useful chunks outrank the actual
Context class's own docstring).

Symbol-name matching sidesteps that entirely: if the query contains an
identifier that exactly names a chunk's symbol (a function, class, or doc
heading), that's a much stronger signal of relevance than term frequency --
*unless* that exact symbol name is itself overloaded across many chunks.
Verified against the same real repo: "command" and "option" are both
common English words AND real function names (function:command appears in
11 different chunks across click's codebase -- command groups, decorators,
tests). Treating every one of those 11 as a strong match on a query like
"how do I add a command" drowned out the actually-relevant result. The fix
mirrors IDF, but applied to symbol names rather than word content: a
symbol name that's unique or rare across the corpus is a much stronger
identity signal than one that's duplicated everywhere.
"""
from __future__ import annotations

import re
from collections import Counter

from knowledge_fabric.types import Chunk, RankedChunk

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _query_identifiers(query: str) -> set[str]:
    """Extract candidate identifier tokens from the query, preserving case
    so exact-case matches (more likely to be real symbol references, e.g.
    "Context" vs. the common word "context") can be scored higher."""
    return set(_IDENTIFIER_RE.findall(query))


def _symbol_name_candidates(symbol: str) -> list[tuple[str, float]]:
    """A chunk's symbol label looks like 'class:Context' or
    'function:get_user_by_id' (code) or 'Runbook \u2192 Retry Policy' (docs).
    Returns (candidate, fragment_weight) pairs. fragment_weight reflects
    how strong an identity signal the candidate is on its own:
    - 3.0: the *entire* symbol name matched, not a fragment of it
    - 2.0: a dotted-method fragment (Class.method -> method) -- still a
      specific identifier even in isolation
    - 1.0: one word carved out of a multi-word prose heading (e.g.
      "Context" out of "Global Context Access") -- much weaker, since
      common English words routinely appear as fragments of headings
    """
    name_part = symbol.split(":", 1)[-1] if ":" in symbol else symbol
    candidates = [(name_part, 3.0)]
    if "." in name_part:
        candidates.append((name_part.split(".")[-1], 2.0))  # Class.method -> method
    if " " in name_part or "\u2192" in name_part:
        candidates.extend((p, 1.0) for p in re.split(r"[ \u2192]+", name_part) if p)
    return [(c, w) for c, w in candidates if c]


def _build_name_frequency(chunks: list[Chunk]) -> Counter:
    """How many chunks share each exact full symbol name, corpus-wide.
    "Context" appearing once is a strong identity signal; "command"
    appearing 11 times across unrelated files means the name itself
    doesn't reliably point at any one of them."""
    freq: Counter = Counter()
    for chunk in chunks:
        if not chunk.symbol:
            continue
        name_part = chunk.symbol.split(":", 1)[-1] if ":" in chunk.symbol else chunk.symbol
        freq[name_part] += 1
    return freq


def symbol_match_results(query: str, chunks: list[Chunk], top_k: int = 10, min_score: float = 15.0) -> list[RankedChunk]:
    """min_score filters out weak partial matches (e.g. "Version" as one
    word inside "Version 8.5.0") before they ever reach fusion. Verified
    against a real repo that without this filter, a long tail of such
    weak-but-present matches, combined with RRF being rank- not
    score-based, let mediocre matches collectively outweigh a single
    strong lexical/vector match elsewhere."""
    query_identifiers = _query_identifiers(query)
    query_identifiers_lower = {q.lower() for q in query_identifiers}
    name_frequency = _build_name_frequency(chunks)

    matches: list[RankedChunk] = []
    for chunk in chunks:
        if not chunk.symbol:
            continue
        best_score = 0.0
        is_code_symbol = ":" in chunk.symbol  # "class:X" / "function:X" vs. a doc heading
        for candidate, fragment_weight in _symbol_name_candidates(chunk.symbol):
            if candidate in query_identifiers:
                base = len(candidate) * 2.0        # exact-case match
            elif candidate.lower() in query_identifiers_lower:
                base = float(len(candidate))        # case-insensitive match
            else:
                continue
            base *= fragment_weight
            if is_code_symbol:
                base *= 1.5    # a query naming something is usually after the definition, not a doc mention
            # dampen names that are duplicated across many chunks -- a name
            # this common isn't a reliable pointer to any single one of them
            freq = name_frequency.get(candidate, 1)
            base /= freq
            best_score = max(best_score, base)
        if best_score >= min_score:
            matches.append(RankedChunk(chunk=chunk, score=best_score))

    matches.sort(key=lambda rc: -rc.score)
    return matches[:top_k]
