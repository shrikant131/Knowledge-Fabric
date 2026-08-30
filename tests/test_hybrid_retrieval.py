from knowledge_fabric.retrieval.hybrid import reciprocal_rank_fusion
from knowledge_fabric.types import Chunk, RankedChunk


def _chunk(cid: str) -> Chunk:
    return Chunk(chunk_id=cid, source_id="s", item_id="i", text=f"text {cid}",
                 symbol=None, language=None, content_hash=cid)


def test_item_ranked_first_in_both_lists_wins():
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    bm25 = [RankedChunk(a, 10.0), RankedChunk(b, 5.0), RankedChunk(c, 1.0)]
    vector = [RankedChunk(a, 0.9), RankedChunk(c, 0.8), RankedChunk(b, 0.5)]

    fused = reciprocal_rank_fusion([bm25, vector], top_k=3)
    assert fused[0].chunk.chunk_id == "a"  # ranked #1 in both lists


def test_item_only_in_one_list_still_included():
    a, b = _chunk("a"), _chunk("b")
    bm25 = [RankedChunk(a, 10.0)]
    vector = [RankedChunk(b, 0.9)]

    fused = reciprocal_rank_fusion([bm25, vector], top_k=5)
    ids = {rc.chunk.chunk_id for rc in fused}
    assert ids == {"a", "b"}


def test_top_k_is_respected():
    chunks = [_chunk(str(i)) for i in range(10)]
    bm25 = [RankedChunk(c, float(10 - i)) for i, c in enumerate(chunks)]
    fused = reciprocal_rank_fusion([bm25, []], top_k=3)
    assert len(fused) == 3


def test_default_weights_are_equal():
    a, b = _chunk("a"), _chunk("b")
    list1 = [RankedChunk(a, 1.0), RankedChunk(b, 1.0)]
    list2 = [RankedChunk(b, 1.0), RankedChunk(a, 1.0)]
    # symmetric inputs, no weights -> a and b should score identically
    fused = reciprocal_rank_fusion([list1, list2], top_k=2)
    scores = {rc.chunk.chunk_id: rc.score for rc in fused}
    assert scores["a"] == scores["b"]


def test_weighted_channel_can_overcome_multi_channel_presence():
    # "b" is ranked #1 in two channels (lexical, vector) but absent from the
    # third; "a" is ranked #1 in only the third channel and absent from the
    # other two entirely. This mirrors the exact failure mode found testing
    # against a real repo: the real Context class was found ONLY by the
    # symbol-match channel (never appeared in lexical/vector top results at
    # all), while short test-file snippets mentioning "Context" repeatedly
    # showed up across multiple channels and outranked it on breadth alone.
    a, b = _chunk("a"), _chunk("b")
    lexical = [RankedChunk(b, 5.0)]
    vector = [RankedChunk(b, 0.9)]
    symbol = [RankedChunk(a, 10.0)]

    unweighted = reciprocal_rank_fusion([lexical, vector, symbol], top_k=2)
    assert unweighted[0].chunk.chunk_id == "b"  # b wins on breadth, unweighted

    weighted = reciprocal_rank_fusion([lexical, vector, symbol], top_k=2, weights=[1.0, 1.0, 5.0])
    assert weighted[0].chunk.chunk_id == "a"  # a wins once its channel is weighted up


def test_a_dozen_common_word_matches_do_not_bury_a_unique_exact_match():
    from knowledge_fabric.retrieval.symbol_match import symbol_match_results

    def _symbol_chunk(cid: str, symbol: str) -> Chunk:
        return Chunk(chunk_id=cid, source_id="s", item_id="i", text="x",
                     symbol=symbol, language=None, content_hash=cid)

    # "target" is a unique, exact symbol match; a dozen chunks share the
    # common-word heading fragment "version", mirroring a real repo's
    # changelog (a dozen "Version X.Y.Z" headings). The min_score filter
    # inside symbol_match_results is what actually prevents those weak
    # fragment matches from ever reaching fusion -- verified end to end
    # against pallets/click, where an earlier version without this filter
    # let exactly this scenario bury a correct result.
    target = _symbol_chunk("target", "class:UniqueThing")
    noise_chunks = [_symbol_chunk(f"noise{i}", f"Version {i}.0.0 (part 1)") for i in range(12)]
    all_chunks = [target] + noise_chunks

    sym = symbol_match_results("What does UniqueThing do, and check the version history", all_chunks, top_k=20)
    sym_ids = [rc.chunk.chunk_id for rc in sym]
    assert "target" in sym_ids
    # the weak "version" fragment matches should have been filtered by
    # min_score before ever reaching this list
    assert not any(cid.startswith("noise") for cid in sym_ids)
    # Important limitation, found testing against a real repo: RRF fusion
    # itself provides NO protection against a long tail of weak-but-present
    # matches in a weighted channel -- a query like "add a version option
    # to a command" produced a dozen weak symbol-channel matches on the
    # common words "version"/"command" (changelog headings like
    # "Version 8.5.0"), which nearly buried a chunk ranked #1 in BOTH
    # lexical and vector search. This test demonstrates that fact directly:
    # weighting alone is not enough.
    target = _chunk("target")
    noise_chunks = [_chunk(f"noise{i}") for i in range(12)]

    lexical = [RankedChunk(target, 10.0)]
    vector = [RankedChunk(target, 0.9)]
    symbol = [RankedChunk(c, 7.0 - i * 0.1) for i, c in enumerate(noise_chunks)]

    fused = reciprocal_rank_fusion([lexical, vector, symbol], top_k=5, weights=[1.0, 1.0, 3.0])
    top_ids = [rc.chunk.chunk_id for rc in fused]
    # this asserts the failure mode, not the fix -- the actual fix is
    # upstream: symbol_match_results applies a min_score threshold so weak
    # matches like these never reach fusion in the first place. See
    # test_symbol_match.py for coverage of that filter, and
    # KnowledgeFabricPipeline._retrieve_with_correction for where the two
    # combine in the real query path.
    assert "target" not in top_ids
