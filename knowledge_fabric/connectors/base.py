"""Common connector interface.

Every source connector implements: fetch -> detect_delta -> parse -> chunk.
The rest of the pipeline (embedding, storage, retrieval) never touches
source-specific logic -- it only calls these four methods.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from knowledge_fabric.types import Chunk, ParsedDocument, RawItem


class SourceConnector(ABC):
    source_id: str

    @abstractmethod
    def fetch(self) -> Iterable[RawItem]:
        """Pull raw items from the source."""

    @abstractmethod
    def detect_delta(self, items: Iterable[RawItem], seen_hashes: dict[str, str]) -> list[RawItem]:
        """Filter to items that are new or changed since the last run.

        seen_hashes maps item_id -> content_hash from the previous ingestion.
        """

    @abstractmethod
    def parse(self, item: RawItem) -> ParsedDocument:
        """Extract structured content from a raw item."""

    @abstractmethod
    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        """Split a parsed document into retrieval-sized chunks."""
