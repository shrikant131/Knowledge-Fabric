"""Lightweight cross-style reranker. It is deterministic and offline-safe.
A production deployment can replace this implementation with a hosted or local
cross-encoder without changing the pipeline contract.
"""
from __future__ import annotations
import re, math
from knowledge_fabric.types import RankedChunk

def _tokens(s): return set(re.findall(r"[A-Za-z0-9_]{3,}", s.lower()))

def rerank(query: str, candidates: list[RankedChunk], top_k: int = 5, weight: float = .35) -> list[RankedChunk]:
    if not candidates: return []
    qt=_tokens(query)
    max_base=max((c.score for c in candidates), default=1.0) or 1.0
    scored=[]
    for rc in candidates:
        ct=_tokens(rc.chunk.text)
        overlap=len(qt & ct)/max(1,len(qt))
        phrase=1.0 if query.lower().strip() in rc.chunk.text.lower() else 0.0
        symbol=0.12 if rc.chunk.symbol and rc.chunk.symbol.lower() in query.lower() else 0.0
        relevance=.72*(rc.score/max_base)+.18*overlap+.10*phrase+symbol
        final=(1-weight)*(rc.score/max_base)+weight*relevance
        scored.append((final,rc))
    scored.sort(key=lambda x:-x[0])
    return [RankedChunk(x[1].chunk,float(x[0])) for x in scored[:top_k]]
