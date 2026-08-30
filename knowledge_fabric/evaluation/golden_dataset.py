"""Golden dataset regression runner, per the Evaluation Pipeline design doc.

A golden case is a (question, expected_answer_contains, relevant chunk
identifiers) triple. Running the golden set computes retrieval
precision/recall against the labeled relevant items and a groundedness
score per case, then compares against baseline thresholds -- the same
gate a CI pipeline would run before allowing a chunking/embedding/
retrieval/prompt change to deploy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from knowledge_fabric.evaluation.judge import HeuristicJudge, LLMJudge
from knowledge_fabric.pipeline import KnowledgeFabricPipeline


@dataclass
class GoldenCase:
    id: str
    question: str
    relevant_item_ids: list[str]     # item_id substrings expected among top-k retrieved
    min_groundedness: float = 0.3    # per-case override of the global threshold


@dataclass
class GoldenCaseResult:
    case: GoldenCase
    retrieved_item_ids: list[str]
    precision_at_k: float
    recall: float
    groundedness_score: float
    verdict: str
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class RegressionReport:
    results: list[GoldenCaseResult]
    mean_precision: float
    mean_recall: float
    mean_groundedness: float
    passed: bool


def load_golden_set(path: str) -> list[GoldenCase]:
    with open(path) as f:
        raw = yaml.safe_load(f) or []
    return [GoldenCase(**case) for case in raw]


def run_golden_set(
    pipeline: KnowledgeFabricPipeline,
    golden_cases: list[GoldenCase],
    precision_threshold: float = 0.3,
    recall_threshold: float = 0.5,
    groundedness_threshold: float = 0.3,
) -> RegressionReport:
    judge = LLMJudge(pipeline.generator) if pipeline.cfg.generator == "bedrock" else HeuristicJudge()

    results: list[GoldenCaseResult] = []
    for case in golden_cases:
        result = pipeline.query(case.question)
        retrieved_item_ids = [_item_id_from_citation(r["citation"]) for r in result["retrieved"]]

        hits = sum(
            1 for item_id in retrieved_item_ids
            if any(rel in item_id for rel in case.relevant_item_ids)
        )
        precision = hits / len(retrieved_item_ids) if retrieved_item_ids else 0.0
        matched_relevant = sum(
            1 for rel in case.relevant_item_ids
            if any(rel in item_id for item_id in retrieved_item_ids)
        )
        recall = matched_relevant / len(case.relevant_item_ids) if case.relevant_item_ids else 1.0

        from knowledge_fabric.types import RankedChunk
        context_chunks = [
            RankedChunk(chunk=_lookup_chunk(pipeline, r), score=r["score"])
            for r in result["retrieved"]
        ]
        judge_result = judge.score(case.question, context_chunks, result["answer"])

        min_ground = max(case.min_groundedness, groundedness_threshold)
        reasons = []
        if precision < precision_threshold:
            reasons.append(f"precision {precision:.2f} < threshold {precision_threshold:.2f}")
        if recall < recall_threshold:
            reasons.append(f"recall {recall:.2f} < threshold {recall_threshold:.2f}")
        if judge_result.groundedness_score < min_ground:
            reasons.append(f"groundedness {judge_result.groundedness_score:.2f} < threshold {min_ground:.2f}")

        results.append(GoldenCaseResult(
            case=case, retrieved_item_ids=retrieved_item_ids,
            precision_at_k=precision, recall=recall,
            groundedness_score=judge_result.groundedness_score,
            verdict=judge_result.verdict, passed=(len(reasons) == 0), reasons=reasons,
        ))

    mean_precision = sum(r.precision_at_k for r in results) / len(results) if results else 0.0
    mean_recall = sum(r.recall for r in results) / len(results) if results else 0.0
    mean_groundedness = sum(r.groundedness_score for r in results) / len(results) if results else 0.0
    overall_passed = all(r.passed for r in results)

    return RegressionReport(
        results=results, mean_precision=mean_precision, mean_recall=mean_recall,
        mean_groundedness=mean_groundedness, passed=overall_passed,
    )


def _item_id_from_citation(citation: str) -> str:
    return citation.split(" :: ")[0].split(" \u2192 ")[0]


def _lookup_chunk(pipeline: KnowledgeFabricPipeline, retrieved: dict):
    for chunk in pipeline.store.chunks:
        if chunk.citation_label() == retrieved["citation"]:
            return chunk
    from knowledge_fabric.types import Chunk
    return Chunk(chunk_id="unknown", source_id=pipeline.cfg.source_id, item_id="unknown",
                 text=retrieved["preview"], symbol=None, language=None, content_hash="")
