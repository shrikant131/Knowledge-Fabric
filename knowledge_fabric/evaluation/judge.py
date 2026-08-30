"""LLM-as-judge groundedness scoring.

Scores whether an answer's claims are actually supported by the retrieved
context it cites. Uses a generator backend to run the judge prompt -- in
the mock/offline case this is a crude lexical-overlap heuristic, not a real
judgment; swap in BedrockGenerator (ideally a different model than the one
that generated the answer, per the design doc) for real scoring.
"""
from __future__ import annotations

import json
import re

from knowledge_fabric.types import JudgeResult, RankedChunk

JUDGE_PROMPT_TEMPLATE = """You are scoring an AI answer for groundedness. \
Given the QUESTION, the RETRIEVED CONTEXT, and the ANSWER, determine \
whether every factual claim in the ANSWER is supported by the CONTEXT.

QUESTION: {question}
CONTEXT: {context}
ANSWER: {answer}

Respond in JSON only:
{{
  "groundedness_score": <0.0-1.0>,
  "unsupported_claims": [<list of claim strings, if any>],
  "verdict": "grounded" | "partially_grounded" | "hallucinated"
}}"""


class LLMJudge:
    """Real judge: delegates to a generator backend (ideally a different
    model than the one that produced the answer being scored)."""

    def __init__(self, generator):
        self.generator = generator

    def score(self, question: str, context_chunks: list[RankedChunk], answer: str) -> JudgeResult:
        context_text = "\n\n".join(rc.chunk.text for rc in context_chunks) or "(no context)"
        prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, context=context_text, answer=answer)
        raw = self.generator.generate(
            system_prompt="You are a careful, skeptical grading assistant. Respond with JSON only.",
            user_prompt=prompt,
            max_tokens=400,
        )
        return _parse_judge_response(raw)


class HeuristicJudge:
    """Offline stand-in: scores groundedness via lexical overlap between
    the answer and the retrieved context, since there's no LLM call to make
    without AWS credentials. This is NOT a real groundedness judgment --
    it's a placeholder so the evaluation pipeline is exercisable end to end
    without Bedrock access. Swap in LLMJudge with BedrockGenerator for real
    scoring."""

    def score(self, question: str, context_chunks: list[RankedChunk], answer: str) -> JudgeResult:
        context_text = " ".join(rc.chunk.text for rc in context_chunks).lower()
        context_tokens = set(re.findall(r"[a-z0-9_]{4,}", context_text))

        # strip the mock generator's boilerplate preamble before scoring
        answer_body = answer.split("]\n\n", 1)[-1] if "[MockGenerator" in answer else answer
        answer_tokens = set(re.findall(r"[a-z0-9_]{4,}", answer_body.lower()))
        answer_tokens -= {"context", "answer", "question", "mockgenerator"}

        if not answer_tokens:
            return JudgeResult(groundedness_score=0.0, verdict="hallucinated",
                                unsupported_claims=["(empty answer)"])

        overlap = answer_tokens & context_tokens
        score = len(overlap) / len(answer_tokens)
        verdict = "grounded" if score >= 0.6 else "partially_grounded" if score >= 0.3 else "hallucinated"
        unsupported = sorted(answer_tokens - context_tokens)[:5]
        return JudgeResult(groundedness_score=round(score, 3), verdict=verdict, unsupported_claims=unsupported)


def _parse_judge_response(raw: str) -> JudgeResult:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(match.group(0)) if match else json.loads(raw)
        return JudgeResult(
            groundedness_score=float(payload.get("groundedness_score", 0.0)),
            verdict=payload.get("verdict", "unknown"),
            unsupported_claims=payload.get("unsupported_claims", []),
        )
    except Exception:
        return JudgeResult(groundedness_score=0.0, verdict="unparseable",
                            unsupported_claims=["judge response could not be parsed"])
