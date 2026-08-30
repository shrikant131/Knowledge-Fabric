"""Append-only query/answer log.

Every query the pipeline serves is logged here: the question, retrieved
chunks (with citations), the answer, and which source(s) contributed. This
is the raw material the evaluation pipeline (LLM-as-judge, RAGAS metrics,
fairness audits) consumes, per the Evaluation & Fairness Pipeline design
doc -- logging is intentionally decoupled from scoring so scoring can be
re-run against historical queries without re-hitting the LLM for retrieval.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class QueryLogEntry:
    timestamp: str
    source_id: str
    query: str
    intent: str
    retrieved: list[dict]          # [{citation, score, chunk_id, source_id}, ...]
    answer: str
    cache_hit: bool = False
    corrective_rounds: int = 0
    judge_score: Optional[float] = None
    judge_verdict: Optional[str] = None


class QueryLog:
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, entry: QueryLogEntry) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

    def read_all(self) -> list[QueryLogEntry]:
        if not self.log_path.exists():
            return []
        entries = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entries.append(QueryLogEntry(**json.loads(line)))
        return entries


def new_entry(source_id: str, query: str, intent: str, retrieved: list[dict], answer: str) -> QueryLogEntry:
    return QueryLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source_id=source_id, query=query, intent=intent,
        retrieved=retrieved, answer=answer,
    )
