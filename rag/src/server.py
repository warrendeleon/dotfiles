"""FastMCP server exposing RAG tools to Claude Code."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .store import Store
from .queue_db import JobQueue, JobType
from .audit import AuditLog
from .parsers.code import SUPPORTED_EXTENSIONS
from .parsers.jsonl import parse_conversation

logger = logging.getLogger(__name__)

mcp = FastMCP("rag", log_level="WARNING")

# Lazy-initialised singletons
_store: Store | None = None
_queue: JobQueue | None = None
_audit: AuditLog | None = None

# Allowed roots for index_file path validation
_ALLOWED_ROOTS = (
    Path.home() / "Developer",
    Path.home() / ".claude",
)

MAX_SEARCH_RESULTS = 100
MAX_AUDIT_ENTRIES = 500


MAX_RAW_FETCH_SIZE = 50 * 1024 * 1024  # 50MB


def _fetch_raw_turn(file_path: str | None, turn_number: Any) -> str | None:
    """Read the original unsummarised turn from a JSONL file."""
    if not file_path or not turn_number:
        return None
    try:
        p = Path(file_path)
        if not p.exists() or p.stat().st_size > MAX_RAW_FETCH_SIZE:
            return None
        turn_num = int(turn_number)
        turns = parse_conversation(file_path)
        for turn in turns:
            if turn["metadata"].get("turn_number") == turn_num:
                return turn["text"]
    except Exception:
        logger.debug("Failed to fetch raw turn from %s", file_path)
    return None


def _get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue()
    return _queue


def _get_audit() -> AuditLog:
    global _audit
    if _audit is None:
        _audit = AuditLog()
    return _audit


def _is_allowed_path(path: Path) -> bool:
    """Check that a resolved path falls under an allowed root."""
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False

    return any(
        resolved == root or root in resolved.parents
        for root in _ALLOWED_ROOTS
    )


@mcp.tool()
def search(query: str, scope: str | None = None, n_results: int = 10) -> str:
    """Search indexed conversations, code, and docs semantically.

    Use this to find past discussions, code patterns, or documentation.

    Args:
        query: Natural language search query.
        scope: Optional. One of "conversations", "code", "docs" to limit search.
               If omitted, searches all collections.
        n_results: Number of results to return (default 10).
    """
    n_results = min(max(1, n_results), MAX_SEARCH_RESULTS)
    store = _get_store()

    collection_names = None
    if scope and scope in ("conversations", "code", "docs"):
        collection_names = [scope]

    try:
        results = store.search(query, collection_names=collection_names, n_results=n_results)
    except Exception:
        logger.exception("Search failed")
        return "Search failed. Check that Ollama is running (ollama serve)."

    if not results:
        return "No results found."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        source = meta.get("file_path", "unknown")
        collection = r.get("collection", "unknown")
        distance = r.get("distance", 0)
        relevance = f"{max(0, (1 - distance)) * 100:.0f}%" if distance < 1 else "low"

        header = f"[{i}] ({collection}) {source} -- relevance: {relevance}"

        # Add useful metadata
        meta_parts = []
        if meta.get("session_id"):
            meta_parts.append(f"session: {meta['session_id']}")
        if meta.get("project"):
            meta_parts.append(f"project: {meta['project']}")
        if meta.get("language"):
            meta_parts.append(f"lang: {meta['language']}")
        if meta.get("doc_type"):
            meta_parts.append(f"type: {meta['doc_type']}")
        if meta.get("timestamp"):
            meta_parts.append(f"time: {meta['timestamp']}")

        if meta_parts:
            header += f" [{', '.join(meta_parts)}]"

        doc = r.get("document", "")

        # If this conversation turn was summarised, fetch the raw text
        if meta.get("summarised") and collection == "conversations":
            raw_turn = _fetch_raw_turn(meta.get("file_path"), meta.get("turn_number"))
            if raw_turn:
                doc = raw_turn

        # Truncate long documents for display
        if len(doc) > 500:
            doc = doc[:500] + "..."

        if meta.get("summarised"):
            header += " [summarised]"
        if meta.get("tags"):
            header += f" [tags: {meta['tags']}]"

        parts.append(f"{header}\n{doc}")

    return "\n\n---\n\n".join(parts)


@mcp.tool()
def get_context(topic: str, n_results: int = 5) -> str:
    """Quick context retrieval for a topic. Searches all collections.

    Use this when you need quick background on a topic discussed previously
    or documented in the codebase.

    Args:
        topic: The topic to get context for.
        n_results: Number of results (default 5).
    """
    return search(query=topic, n_results=n_results)


@mcp.tool()
def log_action(description: str, files_affected: list[str] | None = None) -> str:
    """Record an action in the audit log.

    Call this after completing significant work (commits, refactors,
    architectural decisions) so the action is searchable later.

    Args:
        description: What was done.
        files_affected: Optional list of file paths that were modified.
    """
    try:
        audit = _get_audit()
        entry_id = audit.log(description=description, files_affected=files_affected)
        return f"Logged (entry #{entry_id}): {description}"
    except Exception:
        logger.exception("Failed to write audit log")
        return "Failed to write audit log entry."


@mcp.tool()
def index_file(path: str) -> str:
    """Manually trigger indexing for a specific file.

    Use this when you want a file indexed immediately rather than
    waiting for the background watcher.

    Args:
        path: Absolute path to the file to index.
    """
    file_path = Path(path)
    if not file_path.exists():
        return f"File not found: {path}"

    if not file_path.is_file():
        return "Path is not a regular file."

    if not _is_allowed_path(file_path):
        return "Path is outside allowed directories."

    # Reject symlinks pointing outside allowed roots
    if file_path.is_symlink():
        resolved = file_path.resolve()
        if not _is_allowed_path(resolved):
            return "Symlink target is outside allowed directories."

    try:
        queue = _get_queue()
    except Exception:
        logger.exception("Failed to access job queue")
        return "Failed to access job queue."

    # Determine job type
    resolved = file_path.resolve()
    claude_marker = f"{Path.home()}/.claude/projects/"
    if resolved.suffix == ".jsonl" and str(resolved).startswith(claude_marker):
        job_type = JobType.CONVERSATION.value
    elif resolved.suffix in (".md", ".mdx"):
        job_type = JobType.MARKDOWN.value
    elif resolved.suffix in SUPPORTED_EXTENSIONS:
        job_type = JobType.CODE.value
    else:
        from .parsers.config import _is_config_file
        if _is_config_file(resolved):
            job_type = JobType.CONFIG.value
        else:
            return f"Unsupported file type: {resolved.suffix}"

    try:
        job_id = queue.enqueue(str(resolved), job_type, priority=100)
    except Exception:
        logger.exception("Failed to enqueue file")
        return "Failed to enqueue file for indexing."
    if job_id:
        return f"Queued for indexing (job #{job_id}): {path}"
    return f"Already queued or unchanged: {path}"


@mcp.tool()
def get_audit_log(since: str | None = None, limit: int = 20) -> str:
    """View recent audit log entries.

    Args:
        since: Optional time filter — hours ago (e.g. "24h"), days ago (e.g. "7d"), or Unix timestamp.
               If omitted, returns the most recent entries.
        limit: Maximum entries to return (default 20).
    """
    limit = min(max(1, limit), MAX_AUDIT_ENTRIES)

    try:
        audit = _get_audit()
    except Exception:
        logger.exception("Failed to connect to audit log")
        return "Audit log unavailable."

    since_ts: float | None = None
    if since:
        now = time.time()
        try:
            if since.endswith("h") and len(since) > 1:
                hours = float(since[:-1])
                if hours > 0:
                    since_ts = now - (hours * 3600)
            elif since.endswith("d") and len(since) > 1:
                days = float(since[:-1])
                if days > 0:
                    since_ts = now - (days * 86400)
            else:
                parsed = float(since)
                if parsed <= now:
                    since_ts = parsed
        except ValueError:
            pass  # Invalid format; ignore and return all recent entries

    entries = audit.get_entries(since=since_ts, limit=limit)

    if not entries:
        return "No audit entries found."

    parts: list[str] = []
    for entry in entries:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry["timestamp"]))
        desc = entry["description"]
        files = entry.get("files_affected")

        line = f"[{ts}] {desc}"
        if files:
            line += f"\n  Files: {', '.join(files)}"
        parts.append(line)

    return "\n\n".join(parts)


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
