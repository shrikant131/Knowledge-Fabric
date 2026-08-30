"""Shared data types used across connectors, chunking, retrieval, and generation.

These mirror the concepts from the Connector Framework and Retrieval Pipeline
design docs: RawItem -> ParsedDocument -> Chunk flows through ingestion;
Ranked / RetrievedChunk flow through retrieval.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RawItem:
    """A single unit fetched from a source before parsing (e.g. one file)."""
    source_id: str
    item_id: str          # stable id within the source, e.g. relative file path
    content: str
    content_type: str     # "code" | "doc"
    language: Optional[str] = None   # "python" | "java" | "markdown" | "text" | ...
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass
class ParsedDocument:
    """Structured representation of a RawItem after format-specific parsing."""
    source_id: str
    item_id: str
    content_type: str
    language: Optional[str]
    # list of (heading_or_symbol, text) structural units, in order
    sections: list[tuple[str, str]]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A retrieval-sized unit, tagged with metadata for filtering and citation."""
    chunk_id: str
    source_id: str
    item_id: str
    text: str
    symbol: Optional[str]        # function/class name or section heading
    language: Optional[str]
    content_hash: str
    sensitivity: str = "internal"
    extra: dict[str, Any] = field(default_factory=dict)

    def citation_label(self) -> str:
        loc = f"{self.item_id}"
        if self.symbol:
            loc += f" :: {self.symbol}"
        return loc


@dataclass
class RankedChunk:
    """A chunk with a retrieval score, produced by lexical/vector/fused search."""
    chunk: Chunk
    score: float


@dataclass
class JudgeResult:
    groundedness_score: float
    verdict: str
    unsupported_claims: list[str] = field(default_factory=list)
