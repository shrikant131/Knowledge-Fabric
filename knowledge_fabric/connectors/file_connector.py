"""Generic file-system connector.

Stands in for both the GitHub connector (code files) and the Confluence/
SharePoint connectors (doc files) from the reference architecture, using
the local filesystem as the source. Swapping this for a real GitHub or
Confluence connector later means implementing the same four methods
against their APIs instead of `pathlib` -- nothing downstream changes.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from knowledge_fabric.chunking.code_chunker import split_code_symbols
from knowledge_fabric.chunking.doc_chunker import split_doc_sections
from knowledge_fabric.connectors.base import SourceConnector
from knowledge_fabric.types import Chunk, ParsedDocument, RawItem

CODE_EXTENSIONS = {".py": "python", ".java": "java"}
DOC_EXTENSIONS = {".md": "markdown", ".txt": "text"}
PDF_EXTENSIONS = {".pdf": "pdf"}

DEFAULT_IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}


class FileConnector(SourceConnector):
    def __init__(self, root_path: str, source_id: str = "local_files"):
        self.root_path = Path(root_path)
        self.source_id = source_id

    # ---- fetch -------------------------------------------------------
    def fetch(self) -> Iterable[RawItem]:
        for path in sorted(self.root_path.rglob("*")):
            if not path.is_file():
                continue
            if any(part in DEFAULT_IGNORE_DIRS for part in path.parts):
                continue
            ext = path.suffix.lower()
            rel = str(path.relative_to(self.root_path))

            if ext in CODE_EXTENSIONS:
                content = _read_text(path)
                if content is None:
                    continue
                yield RawItem(source_id=self.source_id, item_id=rel, content=content,
                               content_type="code", language=CODE_EXTENSIONS[ext])
            elif ext in DOC_EXTENSIONS:
                content = _read_text(path)
                if content is None:
                    continue
                yield RawItem(source_id=self.source_id, item_id=rel, content=content,
                               content_type="doc", language=DOC_EXTENSIONS[ext])
            elif ext in PDF_EXTENSIONS:
                content = _read_pdf(path)
                if content is None:
                    continue
                yield RawItem(source_id=self.source_id, item_id=rel, content=content,
                               content_type="doc", language="pdf")

    # ---- detect_delta --------------------------------------------------
    def detect_delta(self, items: Iterable[RawItem], seen_hashes: dict[str, str]) -> list[RawItem]:
        changed = []
        for item in items:
            prior = seen_hashes.get(item.item_id)
            if prior != item.content_hash:
                changed.append(item)
        return changed

    # ---- parse ---------------------------------------------------------
    def parse(self, item: RawItem) -> ParsedDocument:
        if item.content_type == "code":
            symbols = split_code_symbols(item.content, item.language or "")
            sections = [(f"{s.kind}:{s.name}", s.text) for s in symbols]
        else:
            sections = split_doc_sections(item.content)
        return ParsedDocument(
            source_id=item.source_id, item_id=item.item_id,
            content_type=item.content_type, language=item.language,
            sections=sections, extra={"content_hash": item.content_hash},
        )

    # ---- chunk -----------------------------------------------------
    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        chunks = []
        for i, (symbol, text) in enumerate(doc.sections):
            if not text.strip():
                continue
            chunk_id = _chunk_id(doc.source_id, doc.item_id, i)
            chunks.append(Chunk(
                chunk_id=chunk_id, source_id=doc.source_id, item_id=doc.item_id,
                text=text, symbol=symbol, language=doc.language,
                content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                extra={"parent_content_hash": doc.extra.get("content_hash")},
            ))
        return chunks


def _chunk_id(source_id: str, item_id: str, index: int) -> str:
    raw = f"{source_id}:{item_id}:{index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def _read_pdf(path: Path) -> str | None:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return None
