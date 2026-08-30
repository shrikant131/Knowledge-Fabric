"""GitHub public-repository connector.

Fetches a repository tree through GitHub's public REST API, with no token
required for public repositories. Files are normalized into the same RawItem
contract used by the local file connector.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from knowledge_fabric.chunking.code_chunker import split_code_symbols
from knowledge_fabric.chunking.doc_chunker import split_doc_sections
from knowledge_fabric.connectors.base import SourceConnector
from knowledge_fabric.types import Chunk, ParsedDocument, RawItem

CODE_EXTENSIONS = {".py": "python", ".java": "java", ".js": "javascript", ".ts": "typescript", ".go": "go"}
DOC_EXTENSIONS = {".md": "markdown", ".txt": "text", ".rst": "text"}
IGNORE_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__"}
DEFAULT_MAX_FILE_BYTES = 1_000_000


class GitHubConnector(SourceConnector):
    def __init__(self, owner: str, repo: str, source_id: str | None = None,
                 ref: str | None = None, token_env_var: str = "GITHUB_TOKEN",
                 max_file_bytes: int = DEFAULT_MAX_FILE_BYTES, timeout: int = 30, max_files: int = 10000):
        if not re.match(r'^[A-Za-z0-9_.-]{1,100}$', owner) or not re.match(r'^[A-Za-z0-9_.-]{1,100}$', repo):
            raise ValueError('Invalid GitHub owner/repository name')
        self.owner = owner
        self.repo = repo
        self.source_id = source_id or f"github:{owner}/{repo}"
        self.ref = ref
        self.token = os.getenv(token_env_var)
        self.max_file_bytes = max_file_bytes
        self.max_files = max_files
        self.timeout = timeout
        self.session = requests.Session()
        retry=Retry(total=4, connect=4, read=4, status=4, backoff_factor=0.5,
                    status_forcelist=(429,500,502,503,504), allowed_methods=frozenset(["GET"]),
                    respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10))
        self.session.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    @property
    def base(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repo}"

    def fetch(self) -> Iterable[RawItem]:
        repo_info = self._get(self.base)
        ref = self.ref or repo_info.get("default_branch", "main")
        commit = self._get(f"{self.base}/commits/{ref}")
        sha = commit["sha"]
        tree = self._get(f"{self.base}/git/trees/{sha}?recursive=1")
        if tree.get("truncated"):
            raise RuntimeError("GitHub tree is truncated; use a narrower ref or a repository-specific connector configuration")
        yielded=0
        for node in tree.get("tree", []):
            if yielded >= self.max_files:
                break
            if node.get("type") != "blob":
                continue
            path = node.get("path", "")
            if any(part in IGNORE_DIRS for part in path.split("/")):
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in CODE_EXTENSIONS and ext not in DOC_EXTENSIONS:
                continue
            size = int(node.get("size") or 0)
            if size > self.max_file_bytes:
                continue
            blob = self._get(f"{self.base}/git/blobs/{node['sha']}")
            if blob.get("encoding") != "base64":
                continue
            try:
                content = base64.b64decode(blob["content"]).decode("utf-8", errors="ignore")
            except Exception:
                continue
            yielded += 1
            yield RawItem(
                source_id=self.source_id,
                item_id=path,
                content=content,
                content_type="code" if ext in CODE_EXTENSIONS else "doc",
                language=CODE_EXTENSIONS.get(ext) or DOC_EXTENSIONS.get(ext),
                extra={"repo": f"{self.owner}/{self.repo}", "ref": ref, "commit": sha, "url": f"https://github.com/{self.owner}/{self.repo}/blob/{sha}/{path}"},
            )

    def detect_delta(self, items: Iterable[RawItem], seen_hashes: dict[str, str]) -> list[RawItem]:
        return [item for item in items if seen_hashes.get(item.item_id) != item.content_hash]

    def parse(self, item: RawItem) -> ParsedDocument:
        if item.content_type == "code":
            symbols = split_code_symbols(item.content, item.language or "")
            sections = [(f"{s.kind}:{s.name}", s.text) for s in symbols]
        else:
            sections = split_doc_sections(item.content)
        return ParsedDocument(item.source_id, item.item_id, item.content_type, item.language, sections,
                               extra={"content_hash": item.content_hash, **item.extra})

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        chunks=[]
        for i,(symbol,text) in enumerate(doc.sections):
            if not text.strip(): continue
            raw=f"{doc.source_id}:{doc.item_id}:{i}"
            chunks.append(Chunk(
                chunk_id=hashlib.sha256(raw.encode()).hexdigest()[:16],
                source_id=doc.source_id, item_id=doc.item_id, text=text, symbol=symbol,
                language=doc.language, content_hash=hashlib.sha256(text.encode()).hexdigest(),
                extra={"parent_content_hash": doc.extra.get("content_hash"), **{k:v for k,v in doc.extra.items() if k != "content_hash"}},
            ))
        return chunks

    def _get(self, url: str):
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"GitHub API {response.status_code}: {response.text[:300]}")
        return response.json()
