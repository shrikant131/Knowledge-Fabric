"""Generic file-system connector."""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Iterable
from knowledge_fabric.chunking.code_chunker import split_code_symbols
from knowledge_fabric.chunking.doc_chunker import split_doc_sections
from knowledge_fabric.connectors.base import SourceConnector
from knowledge_fabric.runtime_paths import root_path
from knowledge_fabric.types import Chunk, ParsedDocument, RawItem

CODE_EXTENSIONS={".py":"python",".java":"java"}; DOC_EXTENSIONS={".md":"markdown",".txt":"text"}; PDF_EXTENSIONS={".pdf":"pdf"}
DEFAULT_IGNORE_DIRS={".git","__pycache__","node_modules",".venv","venv"}
class FileConnector(SourceConnector):
    def __init__(self,root_path: str,source_id: str="local_files"):
        self.root_path=root_path_fn(root_path); self.source_id=source_id
    def fetch(self)->Iterable[RawItem]:
        if not self.root_path.exists():
            raise FileNotFoundError(f"Knowledge source path does not exist: {self.root_path}")
        if not self.root_path.is_dir(): raise NotADirectoryError(f"Knowledge source path is not a directory: {self.root_path}")
        for path in sorted(self.root_path.rglob("*")):
            if not path.is_file() or any(part in DEFAULT_IGNORE_DIRS for part in path.parts): continue
            ext=path.suffix.lower(); rel=str(path.relative_to(self.root_path))
            if ext in CODE_EXTENSIONS:
                content=_read_text(path)
                if content is not None: yield RawItem(source_id=self.source_id,item_id=rel,content=content,content_type="code",language=CODE_EXTENSIONS[ext])
            elif ext in DOC_EXTENSIONS:
                content=_read_text(path)
                if content is not None: yield RawItem(source_id=self.source_id,item_id=rel,content=content,content_type="doc",language=DOC_EXTENSIONS[ext])
            elif ext in PDF_EXTENSIONS:
                content=_read_pdf(path)
                if content is not None: yield RawItem(source_id=self.source_id,item_id=rel,content=content,content_type="doc",language="pdf")
    def detect_delta(self,items,seen_hashes): return [i for i in items if seen_hashes.get(i.item_id)!=i.content_hash]
    def parse(self,item):
        if item.content_type=="code": sections=[(f"{s.kind}:{s.name}",s.text) for s in split_code_symbols(item.content,item.language or "")]
        else: sections=split_doc_sections(item.content)
        return ParsedDocument(source_id=item.source_id,item_id=item.item_id,content_type=item.content_type,language=item.language,sections=sections,extra={"content_hash":item.content_hash})
    def chunk(self,doc):
        chunks=[]
        for i,(symbol,text) in enumerate(doc.sections):
            if not text.strip(): continue
            chunks.append(Chunk(chunk_id=_chunk_id(doc.source_id,doc.item_id,i),source_id=doc.source_id,item_id=doc.item_id,text=text,symbol=symbol,language=doc.language,content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),extra={"parent_content_hash":doc.extra.get("content_hash")}))
        return chunks

def root_path_fn(value): return root_path(value)
def _chunk_id(source_id,item_id,index): return hashlib.sha256(f"{source_id}:{item_id}:{index}".encode()).hexdigest()[:16]
def _read_text(path):
    try: return path.read_text(encoding="utf-8",errors="ignore")
    except Exception: return None
def _read_pdf(path):
    try:
        from pypdf import PdfReader
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except Exception: return None
