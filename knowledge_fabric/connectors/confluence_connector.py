"""Confluence connector.

Confluence has no reliable org-wide push webhook, so this uses the
Scheduler Adapter pattern from the Reference Architecture: poll the REST
API for pages updated since the last successful run, using a persisted
cursor rather than re-scanning the whole space every time.

Requires network access to your Confluence instance and an API token; not
runnable in this sandbox (no egress to Atlassian domains). The connector
still implements the full fetch/detect_delta/parse/chunk interface so it
plugs into the same registry, scheduler, and pipeline as every other
source -- only fetch() talks to a real API.

Auth: set the token via the environment variable named in
connector_options["auth_env_var"] (default CONFLUENCE_API_TOKEN).
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Iterable

from knowledge_fabric.chunking.doc_chunker import split_doc_sections
from knowledge_fabric.connectors.base import SourceConnector
from knowledge_fabric.types import Chunk, ParsedDocument, RawItem


class ConfluenceConnector(SourceConnector):
    def __init__(self, source_id: str, base_url: str, space_key: str,
                 auth_env_var: str = "CONFLUENCE_API_TOKEN",
                 user_email_env_var: str = "CONFLUENCE_USER_EMAIL",
                 cursor_path: str = "./data/confluence_cursor.txt",
                 page_size: int = 50):
        self.source_id = source_id
        self.base_url = base_url.rstrip("/")
        self.space_key = space_key
        self.auth_env_var = auth_env_var
        self.user_email_env_var = user_email_env_var
        self.cursor_path = cursor_path
        self.page_size = page_size

    # ---- cursor persistence --------------------------------------------
    def _read_cursor(self) -> str | None:
        try:
            with open(self.cursor_path) as f:
                return f.read().strip() or None
        except FileNotFoundError:
            return None

    def _write_cursor(self, value: str) -> None:
        import pathlib
        pathlib.Path(self.cursor_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.cursor_path, "w") as f:
            f.write(value)

    def _session(self):
        import requests
        token = os.environ.get(self.auth_env_var)
        email = os.environ.get(self.user_email_env_var)
        if not token or not email:
            raise RuntimeError(
                f"Missing credentials: set {self.user_email_env_var} and {self.auth_env_var} "
                "environment variables (Confluence API token auth)."
            )
        session = requests.Session()
        session.auth = (email, token)
        session.headers.update({"Accept": "application/json"})
        return session

    # ---- fetch -----------------------------------------------------
    def fetch(self) -> Iterable[RawItem]:
        session = self._session()
        cursor = self._read_cursor()
        cql = f'space="{self.space_key}" and type=page'
        if cursor:
            cql += f' and lastmodified >= "{cursor}"'

        start, run_started_at = 0, datetime.now(timezone.utc).isoformat()
        while True:
            resp = session.get(
                f"{self.base_url}/wiki/rest/api/content/search",
                params={"cql": cql, "start": start, "limit": self.page_size,
                        "expand": "body.storage,version,history"},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            results = payload.get("results", [])
            if not results:
                break
            for page in results:
                body = page.get("body", {}).get("storage", {}).get("value", "")
                yield RawItem(
                    source_id=self.source_id,
                    item_id=page["id"],
                    content=body,
                    content_type="doc",
                    language="confluence_html",
                    extra={
                        "title": page.get("title"),
                        "version": page.get("version", {}).get("number"),
                        "url": f"{self.base_url}/wiki{page.get('_links', {}).get('webui', '')}",
                    },
                )
            start += self.page_size
            if start >= payload.get("size", 0) + payload.get("start", 0) and len(results) < self.page_size:
                break

        self._write_cursor(run_started_at)

    # ---- detect_delta --------------------------------------------------
    def detect_delta(self, items: Iterable[RawItem], seen_hashes: dict[str, str]) -> list[RawItem]:
        # The CQL query above already limits fetch() to pages modified
        # since the last cursor, but we still hash-compare in case a page
        # was touched without a meaningful content change (e.g. permissions).
        changed = []
        for item in items:
            if seen_hashes.get(item.item_id) != item.content_hash:
                changed.append(item)
        return changed

    # ---- parse ---------------------------------------------------------
    def parse(self, item: RawItem) -> ParsedDocument:
        text = _strip_confluence_html(item.content)
        sections = split_doc_sections(text)
        return ParsedDocument(
            source_id=item.source_id, item_id=item.item_id,
            content_type="doc", language="confluence",
            sections=sections,
            extra={"content_hash": item.content_hash, "title": item.extra.get("title"),
                   "url": item.extra.get("url")},
        )

    # ---- chunk -----------------------------------------------------
    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        chunks = []
        title = doc.extra.get("title", doc.item_id)
        for i, (heading, text) in enumerate(doc.sections):
            if not text.strip():
                continue
            symbol = f"{title} \u2192 {heading}" if heading not in ("<document>", "<intro>") else title
            chunk_id = hashlib.sha256(f"{doc.source_id}:{doc.item_id}:{i}".encode()).hexdigest()[:16]
            chunks.append(Chunk(
                chunk_id=chunk_id, source_id=doc.source_id, item_id=doc.item_id,
                text=text, symbol=symbol, language="confluence",
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
                extra={"parent_content_hash": doc.extra.get("content_hash"), "url": doc.extra.get("url")},
            ))
        return chunks


def _strip_confluence_html(html: str) -> str:
    """Very small HTML-to-text step; a production version would use a
    proper HTML parser (e.g. BeautifulSoup) to preserve tables/lists better."""
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()
