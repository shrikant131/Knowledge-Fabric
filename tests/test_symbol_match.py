from knowledge_fabric.retrieval.symbol_match import symbol_match_results
from knowledge_fabric.types import Chunk


def _chunk(symbol: str, text: str = "irrelevant filler text") -> Chunk:
    return Chunk(chunk_id=symbol, source_id="s", item_id="i", text=text,
                 symbol=symbol, language="python", content_hash=symbol)


def test_exact_case_match_on_class_symbol():
    chunks = [
        _chunk("class:Context"),
        _chunk("class:CustomContext"),
        _chunk("function:unrelated"),
    ]
    results = symbol_match_results("What does the Context class do?", chunks)
    ids = [rc.chunk.chunk_id for rc in results]
    assert "class:Context" in ids
    assert "function:unrelated" not in ids


def test_exact_case_match_ranks_above_case_insensitive_match():
    chunks = [_chunk("class:context"), _chunk("class:Context")]
    results = symbol_match_results("What does the Context class do?", chunks)
    assert results[0].chunk.chunk_id == "class:Context"  # exact-case match wins


def test_no_match_returns_empty():
    chunks = [_chunk("class:Foo"), _chunk("function:bar")]
    results = symbol_match_results("What is the weather today?", chunks)
    assert results == []


def test_dotted_symbol_matches_on_method_name():
    chunks = [_chunk("Context.invoke"), _chunk("class:Unrelated")]
    results = symbol_match_results("How does invoke work?", chunks)
    ids = [rc.chunk.chunk_id for rc in results]
    assert "Context.invoke" in ids


def test_common_lowercase_word_still_matches_lowercase_symbol():
    # even without exact-case match, a lowercase symbol name should still
    # match a lowercase query term (just scored lower than exact-case)
    chunks = [_chunk("function:parse_args")]
    results = symbol_match_results("how does parse_args work", chunks)
    assert len(results) == 1
