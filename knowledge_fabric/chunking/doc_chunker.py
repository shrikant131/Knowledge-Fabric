"""Structure-aware chunking for docs (markdown, plain text, extracted PDF text)."""
from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


def split_doc_sections(text: str, max_chars: int = 1600) -> list[tuple[str, str]]:
    """Split into (heading, body) sections.

    Markdown headings define section boundaries when present. Text without
    headings is split into max_chars-ish paragraph groups instead, so long
    plain-text docs still produce retrieval-sized chunks.
    """
    headings = list(_HEADING_RE.finditer(text))
    if headings:
        sections: list[tuple[str, str]] = []
        for i, h in enumerate(headings):
            title = h.group(2).strip()
            start = h.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            body = text[start:end].strip()
            if body:
                sections.extend(_split_long_section(title, body, max_chars))
        preamble = text[: headings[0].start()].strip()
        if preamble:
            sections = _split_long_section("<intro>", preamble, max_chars) + sections
        return sections

    return _split_long_section("<document>", text.strip(), max_chars)


def _split_long_section(title: str, body: str, max_chars: int) -> list[tuple[str, str]]:
    if len(body) <= max_chars:
        return [(title, body)]
    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    out: list[tuple[str, str]] = []
    buf: list[str] = []
    buf_len = 0
    part = 1
    for para in paragraphs:
        if buf_len + len(para) > max_chars and buf:
            out.append((f"{title} (part {part})", "\n\n".join(buf)))
            part += 1
            buf, buf_len = [], 0
        buf.append(para)
        buf_len += len(para)
    if buf:
        out.append((f"{title} (part {part})" if part > 1 else title, "\n\n".join(buf)))
    return out
