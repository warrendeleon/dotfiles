"""Parse source code files into indexable documents."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# File extensions we index
SUPPORTED_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx",
    ".py",
    ".swift", ".kt",
    ".json",
    ".yaml", ".yml",
    ".sh", ".bash", ".zsh",
    ".sql",
    ".graphql", ".gql",
    ".css", ".scss",
}

# Patterns to skip entirely
SKIP_PATTERNS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".next",
    "dist",
    "build",
    ".expo",
    "coverage",
    ".yarn",
    ".rag",
    "Pods",
}

# Multi-segment skip patterns: (parent, child) tuples
SKIP_PAIRS = [
    ("android", "build"),
    ("ios", "build"),
]

# Max file size to index (500KB)
MAX_FILE_SIZE = 500_000


def _detect_language(path: Path) -> str:
    """Detect language from file extension."""
    ext_map = {
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".py": "python",
        ".swift": "swift", ".kt": "kotlin",
        ".json": "json",
        ".yaml": "yaml", ".yml": "yaml",
        ".sh": "shell", ".bash": "shell", ".zsh": "shell",
        ".sql": "sql",
        ".graphql": "graphql", ".gql": "graphql",
        ".css": "css", ".scss": "scss",
    }
    return ext_map.get(path.suffix, "unknown")


def _detect_file_type(path: Path, content: str) -> str:
    """Classify the file type from path and content patterns."""
    name = path.name.lower()
    parent = path.parent.name.lower()

    if name.endswith((".test.ts", ".test.tsx", ".rntl.tsx", ".cucumber.tsx", ".spec.ts")):
        return "test"
    if name.endswith((".stories.tsx", ".stories.ts")):
        return "story"
    if "screen" in name:
        return "screen"
    if parent in ("components", "shared"):
        return "component"
    if parent == "hooks" or name.startswith("use"):
        return "hook"
    if parent in ("store", "slices") or "slice" in name:
        return "state"
    if parent == "api" or "api" in name:
        return "api"
    if parent == "utils" or parent == "helpers":
        return "utility"
    if name in ("package.json", "tsconfig.json", "jest.config.js"):
        return "config"

    return "source"


def _extract_purpose(content: str, language: str) -> str:
    """Extract key structural elements from source code."""
    lines = content.split("\n")
    purpose_parts: list[str] = []

    # Extract exports, component names, function signatures
    for line in lines:
        stripped = line.strip()

        # Skip imports, empty lines, comments
        if not stripped or stripped.startswith("import ") or stripped.startswith("//"):
            continue

        # Capture key declarations (skip trivial const assignments)
        if any(stripped.startswith(kw) for kw in (
            "export ", "function ", "class ", "interface ", "type ", "enum ",
            "def ", "async def ", "struct ",
        )) or (stripped.startswith("const ") and ("=>" in stripped or "function" in stripped)):
            # Truncate long lines
            purpose_parts.append(stripped[:200])

        if len(purpose_parts) >= 30:
            break

    return "\n".join(purpose_parts)


def _should_skip(path: Path) -> bool:
    """Check if path matches a skip pattern."""
    parts = path.parts
    if any(skip in parts for skip in SKIP_PATTERNS):
        return True
    # Check multi-segment patterns (consecutive directory pairs)
    for parent, child in SKIP_PAIRS:
        for i in range(len(parts) - 1):
            if parts[i] == parent and parts[i + 1] == child:
                return True
    return False


def parse_code_file(path: str | Path) -> dict[str, Any] | None:
    """Parse a source code file into an indexable document.

    Returns a dict with keys: text, metadata, needs_summary, identifier.
    Returns None if the file should be skipped.
    """
    path = Path(path)

    if not path.exists() or not path.is_file():
        return None

    if path.suffix not in SUPPORTED_EXTENSIONS:
        return None

    if _should_skip(path):
        return None

    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            return None
        if size == 0:
            return None
    except OSError:
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        logger.exception("Failed to read %s", path)
        return None

    if not content.strip():
        return None

    language = _detect_language(path)
    file_type = _detect_file_type(path, content)
    purpose = _extract_purpose(content, language)

    # Build the text to embed
    text = f"File: {path.name}\nType: {file_type}\nLanguage: {language}\n\n{purpose}"

    # Determine project from path
    project = ""
    home = Path.home()
    try:
        rel = path.relative_to(home / "Developer")
        project = rel.parts[0] if rel.parts else ""
    except ValueError:
        pass

    metadata = {
        "file_path": str(path),
        "language": language,
        "file_type": file_type,
        "project": project,
        "source_type": "code",
        "size": size,
    }

    return {
        "text": text,
        "metadata": metadata,
        "needs_summary": len(content) > 3000,
        "identifier": str(path),
        "raw_content": content,
    }
