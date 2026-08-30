import os
import tempfile

from knowledge_fabric.evaluation.fairness import source_diversity_report
from knowledge_fabric.evaluation.query_log import QueryLogEntry
from knowledge_fabric.types import Chunk
from knowledge_fabric.vectorstore.faiss_store import FaissVectorStore


def _store(counts: dict[str, int]) -> FaissVectorStore:
    store = FaissVectorStore(dimension=4, index_path=os.path.join(tempfile.mkdtemp(), "t.faiss"))
    chunks = []
    for item_id, n in counts.items():
        for i in range(n):
            chunks.append(Chunk(chunk_id=f"{item_id}-{i}", source_id="s", item_id=item_id,
                                  text="x", symbol=None, language=None, content_hash=f"h{i}"))
    store.chunks = chunks
    return store


def _entries(citations: list[str]) -> list[QueryLogEntry]:
    return [
        QueryLogEntry(timestamp="t", source_id="s", query="q", intent="code",
                      retrieved=[{"item_id": item_id, "citation": item_id}], answer="a")
        for item_id in citations
    ]


def test_over_cited_source_is_flagged():
    store = _store({"a.py": 10, "b.py": 90})  # a is 10% of index
    entries = _entries(["a.py"] * 50 + ["b.py"] * 50)  # a is 50% of citations

    report = source_diversity_report(entries, store, deviation_threshold=0.5)
    flagged_ids = {f.item_id for f in report.findings}
    assert "a.py" in flagged_ids


def test_proportionally_cited_source_is_not_flagged():
    store = _store({"a.py": 50, "b.py": 50})
    entries = _entries(["a.py"] * 50 + ["b.py"] * 50)  # citation share matches index share exactly

    report = source_diversity_report(entries, store, deviation_threshold=0.5)
    assert report.findings == []


def test_empty_log_produces_no_findings():
    store = _store({"a.py": 10, "b.py": 10})
    report = source_diversity_report([], store, deviation_threshold=0.5)
    assert report.findings == []
    assert report.total_queries == 0
