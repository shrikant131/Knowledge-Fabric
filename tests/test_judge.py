from knowledge_fabric.evaluation.judge import HeuristicJudge
from knowledge_fabric.types import Chunk, RankedChunk


def _ranked(text: str) -> RankedChunk:
    chunk = Chunk(chunk_id="c1", source_id="s", item_id="i", text=text,
                  symbol=None, language=None, content_hash="h")
    return RankedChunk(chunk=chunk, score=1.0)


def test_grounded_answer_scores_high():
    context = [_ranked("The retry policy uses exponential backoff with a maximum of five attempts.")]
    answer = "The retry policy uses exponential backoff with a maximum of five attempts."
    result = HeuristicJudge().score("How does retry work?", context, answer)
    assert result.groundedness_score > 0.6
    assert result.verdict == "grounded"


def test_unrelated_answer_scores_low():
    context = [_ranked("The retry policy uses exponential backoff.")]
    answer = "Paris is the capital of France and has a population of over two million people."
    result = HeuristicJudge().score("What is the capital of France?", context, answer)
    assert result.groundedness_score < 0.3
    assert result.verdict == "hallucinated"


def test_empty_answer_scores_zero():
    context = [_ranked("Some context.")]
    result = HeuristicJudge().score("q", context, "")
    assert result.groundedness_score == 0.0
