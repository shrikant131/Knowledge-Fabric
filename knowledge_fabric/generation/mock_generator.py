"""Extractive mock generator.

No LLM call at all -- it stitches together the top retrieved chunks with
their citation labels so the full pipeline (ingest -> retrieve -> "answer")
can be exercised and demoed without AWS credentials. Swap in
BedrockGenerator for real generation quality.
"""
from __future__ import annotations

from knowledge_fabric.types import RankedChunk


class MockGenerator:
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
        return (
            "[MockGenerator -- no LLM call made. This is a placeholder answer "
            "assembled from the top retrieved chunks; swap in BedrockGenerator "
            "for a real generated answer.]\n\n"
            + _extract_context_preview(user_prompt)
        )


def _extract_context_preview(user_prompt: str, max_chars: int = 500) -> str:
    if "CONTEXT:" not in user_prompt:
        return ""
    context = user_prompt.split("CONTEXT:", 1)[1].split("QUESTION:", 1)[0].strip()
    return context[:max_chars] + ("..." if len(context) > max_chars else "")
