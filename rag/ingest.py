"""Turn a directory of documents into search-ready chunks.

Chunking strategy: split Markdown/text on headings first (so a chunk stays
under one topic), then fall back to paragraph splitting for headingless
blocks longer than MAX_CHUNK_CHARS. PDFs have no heading markup to split on,
so they go straight to paragraph splitting per extracted page.

This module is the shared dependency office-agent's knowledge_base/ingest.py
already points to (see its module docstring) — the chunk interface
(RawChunk: source, heading, text) is intentionally the same shape so that
office-agent's BM25 stopgap can be swapped for this pipeline without
touching its ingest -> chunks -> search boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHUNK_CHARS = 1500
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
PDF_EXTENSIONS = {".pdf"}
DOC_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS


@dataclass
class RawChunk:
    source: str
    heading: str
    text: str


def _split_by_heading(text: str) -> list[tuple[str, str]]:
    matches = list(HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        sections.append(("", text[: matches[0].start()]))

    for i, m in enumerate(matches):
        heading = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end]))

    return sections


def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []

    blocks: list[str] = []
    current = ""
    for p in paragraphs:
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) > max_chars and current:
            blocks.append(current)
            current = p
        else:
            current = candidate
    if current:
        blocks.append(current)
    return blocks


def chunk_document(source: str, text: str) -> list[RawChunk]:
    chunks: list[RawChunk] = []
    for heading, body in _split_by_heading(text):
        body = body.strip()
        if not body:
            continue
        for block in _split_paragraphs(body, MAX_CHUNK_CHARS):
            chunks.append(RawChunk(source=source, heading=heading, text=block))
    return chunks


def _read_pdf(path: Path) -> str:
    import pypdf  # lazy import — optional dependency, only needed for PDF corpora

    reader = pypdf.PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def ingest_file(path: Path, rel: str) -> list[RawChunk]:
    if path.suffix.lower() in PDF_EXTENSIONS:
        text = _read_pdf(path)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return chunk_document(rel, text)


def ingest_directory(root: str | Path) -> list[RawChunk]:
    root = Path(root)
    chunks: list[RawChunk] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in DOC_EXTENSIONS:
            rel = str(path.relative_to(root))
            chunks.extend(ingest_file(path, rel))
    return chunks
