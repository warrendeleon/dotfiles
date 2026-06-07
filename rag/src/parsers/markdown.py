"""Parse wiki markdown pages into indexable, section-level chunks.

Mirrors the turn contract used by the JSONL parser: each chunk is a dict with
`identifier`, `text`, and `metadata`. Chunking by level-2 (`##`) section keeps
retrieval granular, so a search returns the relevant section of a curated page
rather than a whole document or a stray sentence.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 24_000  # match the embedding window guard used for conversations

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_TITLE_RE = re.compile(r'^title:\s*["\']?(.*?)["\']?\s*$', re.MULTILINE)
_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_SECTION_SPLIT_RE = re.compile(r"^##\s+", re.MULTILINE)


def _domain_for(rel_path: str) -> str:
    """Top-level wiki domain (personal or hl) from a path relative to wiki root."""
    head = rel_path.split("/", 1)[0]
    return head if head in ("personal", "hl") else "unknown"


def _strip_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Frontmatter is '' when absent."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _extract_title(frontmatter: str, body: str, path: Path) -> str:
    """Title from frontmatter, else the first H1, else the file stem."""
    m = _TITLE_RE.search(frontmatter)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = _H1_RE.search(body)
    if m:
        return m.group(1).strip()
    return path.stem


def parse_wiki_page(path: Path, wiki_root: Path) -> list[dict[str, Any]]:
    """Parse a single wiki markdown file into section chunks.

    Each chunk's text is prefixed with the page title and section heading so the
    embedding carries that context. The identifier is stable across reindexes
    (`relative/path.md#N`), so upserts replace rather than duplicate.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Could not read %s", path)
        return []

    rel_path = str(path.relative_to(wiki_root))
    frontmatter, body = _strip_frontmatter(raw)
    title = _extract_title(frontmatter, body, path)
    domain = _domain_for(rel_path)

    # Split into the intro (everything before the first '## ') plus one piece per
    # level-2 section. re.split keeps the text after each '## ' marker.
    pieces = _SECTION_SPLIT_RE.split(body)
    chunks: list[dict[str, Any]] = []

    for idx, piece in enumerate(pieces):
        piece = piece.strip()
        if not piece:
            continue

        if idx == 0:
            section = "(intro)"
            section_text = piece
        else:
            # The split removed the leading '## '; the heading is the first line.
            first_nl = piece.find("\n")
            if first_nl == -1:
                section = piece.strip()
                section_text = piece
            else:
                section = piece[:first_nl].strip()
                section_text = piece[first_nl + 1:].strip()

        if not section_text:
            continue

        document = f"{title}: {section}\n\n{section_text}"
        if len(document) > MAX_CHUNK_CHARS:
            document = document[:MAX_CHUNK_CHARS]

        chunks.append({
            "identifier": f"{rel_path}#{idx}",
            "text": document,
            "metadata": {
                "file_path": str(path),
                "title": title,
                "section": section,
                "domain": domain,
            },
        })

    return chunks
