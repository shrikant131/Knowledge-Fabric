"""Source-diversity fairness audit.

Compares how often each item (file/page) is cited in answers against how
much of the index that item actually represents. A file that's 5% of the
index being cited in 5% of answers is expected; being cited in 40% or in
0% is worth flagging -- deviation is measured relative to index share, not
raw citation counts, so genuinely more-relevant content isn't penalized
for simply being cited more.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from knowledge_fabric.evaluation.query_log import QueryLogEntry
from knowledge_fabric.vectorstore.faiss_store import FaissVectorStore


@dataclass
class SourceDeviation:
    item_id: str
    index_share: float
    citation_share: float
    deviation: float   # (citation_share - index_share) / index_share


@dataclass
class DiversityReport:
    findings: list[SourceDeviation]
    total_queries: int
    threshold: float


def source_diversity_report(
    log_entries: list[QueryLogEntry],
    store: FaissVectorStore,
    deviation_threshold: float = 1.0,   # flag if cited >2x or <0x expected share
) -> DiversityReport:
    if not log_entries:
        # nothing to audit yet -- every item would trivially show -100%
        # "under-citation" with zero data behind it, which isn't a finding
        return DiversityReport(findings=[], total_queries=0, threshold=deviation_threshold)

    index_counts = Counter(chunk.item_id for chunk in store.chunks)
    total_chunks = sum(index_counts.values()) or 1
    index_share = {item_id: count / total_chunks for item_id, count in index_counts.items()}

    citation_counts: Counter = Counter()
    for entry in log_entries:
        for r in entry.retrieved:
            citation_counts[r.get("item_id", r.get("citation", "").split(" :: ")[0])] += 1
    total_citations = sum(citation_counts.values()) or 1
    citation_share = {item_id: count / total_citations for item_id, count in citation_counts.items()}

    findings = []
    all_items = set(index_share) | set(citation_share)
    for item_id in all_items:
        expected = index_share.get(item_id, 0.0)
        actual = citation_share.get(item_id, 0.0)
        if expected == 0:
            continue  # cited but not in current index (stale log entry) -- not a fairness signal
        deviation = (actual - expected) / expected
        if abs(deviation) > deviation_threshold:
            findings.append(SourceDeviation(item_id=item_id, index_share=expected,
                                              citation_share=actual, deviation=deviation))

    findings.sort(key=lambda f: -abs(f.deviation))
    return DiversityReport(findings=findings, total_queries=len(log_entries), threshold=deviation_threshold)
