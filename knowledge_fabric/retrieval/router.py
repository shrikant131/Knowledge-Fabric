"""Query router.

The retrieval pipeline design calls for a small Bedrock classification call
here. For the pilot (and for local/offline runs without AWS), this uses a
cheap keyword heuristic instead -- same QueryIntent shape, so swapping in a
real Bedrock-backed classifier later is a drop-in replacement, not a
pipeline change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_CODE_HINTS = re.compile(r"\b(function|class|method|bug|error|exception|import|def |code|repo|api|variable)\b", re.I)
_DOC_HINTS = re.compile(r"\b(policy|doc|guide|readme|process|requirement|design|architecture)\b", re.I)


@dataclass
class QueryIntent:
    label: str  # "code" | "doc" | "general"


def route_query(query: str) -> QueryIntent:
    if _CODE_HINTS.search(query):
        return QueryIntent(label="code")
    if _DOC_HINTS.search(query):
        return QueryIntent(label="doc")
    return QueryIntent(label="general")
