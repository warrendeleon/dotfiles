"""Parse markdown files into indexable documents."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 200_000  # 200KB

# Patterns to strip from markdown
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)
TOC_RE = re.compile(r"^\s*-\s*\[.*?\]\(#.*?\)\s*$", re.MULTILINE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_markdown(content: str) -> str:
    """Strip frontmatter, TOC, HTML comments, and excessive formatting."""
    text = FRONTMATTER_RE.sub("", content)
    text = TOC_RE.sub("", text)
    text = HTML_COMMENT_RE.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_doc_type(path: Path) -> str:
    """Classify the markdown document type."""
    name = path.name.lower()
    parent = path.parent.name.lower()

    if name in ("readme.md", "readme"):
        return "readme"
    if name in ("changelog.md", "changes.md"):
        return "changelog"
    if name in ("claude.md",):
        return "ai-config"
    if parent == "planning" or "task" in name or "epic" in name or "story" in name:
        return "planning"
    if parent in ("docs", "documentation"):
        return "documentation"
    if "guide" in name:
        return "guide"
    if "api" in name:
        return "api-doc"

    return "documentation"


def parse_markdown(path: str | Path) -> dict[str, Any] | None:
    """Parse a markdown file into an indexable document.

    Returns a dict with keys: text, metadata, needs_summary, identifier.
    Returns None if the file should be skipped.
    """
    path = Path(path)

    if not path.exists() or not path.is_file():
        return None

    if path.suffix.lower() not in (".md", ".mdx"):
        return None

    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE or size == 0:
            return None
    except OSError:
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.exception("Failed to read %s", path)
        return None

    cleaned = _clean_markdown(content)
    if not cleaned:
        return None

    doc_type = _detect_doc_type(path)

    # Extract title from first heading
    title = path.stem
    for line in cleaned.split("\n"):
        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            break

    # Determine project
    project = ""
    home = Path.home()
    try:
        rel = path.relative_to(home / "Developer")
        project = rel.parts[0] if rel.parts else ""
    except ValueError:
        pass

    metadata = {
        "file_path": str(path),
        "doc_type": doc_type,
        "title": title,
        "project": project,
        "source_type": "docs",
    }

    return {
        "text": cleaned,
        "metadata": metadata,
        "needs_summary": len(cleaned) > 3000,
        "identifier": str(path),
    }
