"""Reciprocal Rank Fusion -- combine BM25 and vector result rankings.

RRF is rank-based rather than score-based, so it works even though BM25
scores and cosine-similarity scores live on completely different scales.
"""
from __future__ import annotations

from knowledge_fabric.types import Chunk, RankedChunk


def reciprocal_rank_fusion(
    result_lists: list[list[RankedChunk]],
    k: int = 60,
    top_k: int = 10,
    weights: list[float] | None = None,
) -> list[RankedChunk]:
    if weights is None:
        weights = [1.0] * len(result_lists)

    scores: dict[str, float] = {}
    chunk_by_id: dict[str, Chunk] = {}

    for result_list, weight in zip(result_lists, weights):
        for rank, ranked in enumerate(result_list, start=1):
            cid = ranked.chunk.chunk_id
            scores[cid] = scores.get(cid, 0.0) + weight / (k + rank)
            chunk_by_id[cid] = ranked.chunk

    fused = sorted(scores.items(), key=lambda kv: -kv[1])[:top_k]
    return [RankedChunk(chunk=chunk_by_id[cid], score=score) for cid, score in fused]
