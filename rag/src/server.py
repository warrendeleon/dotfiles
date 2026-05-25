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

logger = logging.getLogger(__name__)

mcp = FastMCP("rag", log_level="WARNING")

_store: Store | None = None
_queue: JobQueue | None = None
_audit: AuditLog | None = None

_ALLOWED_ROOTS = (
    Path.home() / ".claude",
)

MAX_SEARCH_RESULTS = 100
MAX_AUDIT_ENTRIES = 500


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
def search(query: str, n_results: int = 10) -> str:
    """Search indexed conversations semantically.

    Use this to find past discussions, decisions, or context from previous
    Claude Code sessions.

    Args:
        query: Natural language search query.
        n_results: Number of results to return (default 10).
    """
    n_results = min(max(1, n_results), MAX_SEARCH_RESULTS)
    store = _get_store()

    try:
        results = store.search(query, n_results=n_results)
    except Exception:
        logger.exception("Search failed")
        return "Search failed. Check that the embedding model is available."

    if not results:
        return "No results found."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        meta = r.get("metadata", {})
        source = meta.get("file_path", "unknown")
        distance = r.get("distance", 0)
        relevance = f"{max(0, (1 - distance)) * 100:.0f}%" if distance < 1 else "low"

        header = f"[{i}] {source} -- relevance: {relevance}"

        meta_parts = []
        if meta.get("session_id"):
            meta_parts.append(f"session: {meta['session_id']}")
        if meta.get("project"):
            meta_parts.append(f"project: {meta['project']}")
        if meta.get("timestamp"):
            meta_parts.append(f"time: {meta['timestamp']}")

        if meta_parts:
            header += f" [{', '.join(meta_parts)}]"

        doc = r.get("document", "")

        if len(doc) > 500:
            doc = doc[:500] + "..."

        parts.append(f"{header}\n{doc}")

    return "\n\n---\n\n".join(parts)


@mcp.tool()
def get_context(topic: str, n_results: int = 5) -> str:
    """Quick context retrieval for a topic.

    Use this when you need quick background on a topic discussed previously.

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
    """Manually trigger indexing for a conversation JSONL file.

    Use this when you want a file indexed immediately rather than
    waiting for the background watcher.

    Args:
        path: Absolute path to the JSONL file to index.
    """
    file_path = Path(path)
    if not file_path.exists():
        return f"File not found: {path}"

    if not file_path.is_file():
        return "Path is not a regular file."

    if file_path.suffix != ".jsonl":
        return "Only conversation JSONL files are supported."

    if not _is_allowed_path(file_path):
        return "Path is outside allowed directories."

    if "-dotfiles-rag" in str(file_path):
        return "Files in the dotfiles-rag project are excluded (pipeline artifacts)."

    if file_path.is_symlink():
        resolved = file_path.resolve()
        if not _is_allowed_path(resolved):
            return "Symlink target is outside allowed directories."

    try:
        queue = _get_queue()
    except Exception:
        logger.exception("Failed to access job queue")
        return "Failed to access job queue."

    try:
        job_id = queue.enqueue(str(file_path.resolve()), JobType.CONVERSATION.value, priority=100)
    except Exception:
        logger.exception("Failed to enqueue file")
        return "Failed to enqueue file for indexing."
    if job_id:
        return f"Queued for indexing (job #{job_id}): {path}"
    return f"Already queued or unchanged: {path}"


@mcp.tool()
def get_indexing_status() -> str:
    """Check whether the indexing queue is idle or still processing.

    Returns job counts by status (pending, processing, completed, failed)
    and details of any currently processing jobs.
    """
    try:
        queue = _get_queue()
    except Exception:
        logger.exception("Failed to access job queue")
        return "Job queue unavailable."

    counts = queue.stats()
    if not counts:
        return "Queue is empty. No jobs have been submitted."

    pending = counts.get("pending", 0)
    processing = counts.get("processing", 0)
    completed = counts.get("completed", 0)
    failed = counts.get("failed", 0)

    if pending == 0 and processing == 0:
        status = "idle"
    elif processing > 0:
        status = "processing"
    else:
        status = "queued"

    parts = [
        f"Status: {status}",
        f"Pending: {pending}  |  Processing: {processing}  |  Completed: {completed}  |  Failed: {failed}",
    ]

    if processing > 0:
        active = queue.get_processing_jobs()
        if active:
            parts.append("\nCurrently processing:")
            for job in active:
                parts.append(f"  - [{job['job_type']}] {job['file_path']} (attempt {job['attempts']})")

    if pending > 0:
        parts.append(f"\n{pending} job(s) waiting in queue.")

    return "\n".join(parts)


@mcp.tool()
def get_failed_jobs(limit: int = 20) -> str:
    """View jobs that failed indexing, with error details.

    Args:
        limit: Maximum entries to return (default 20).
    """
    limit = min(max(1, limit), MAX_AUDIT_ENTRIES)

    try:
        queue = _get_queue()
    except Exception:
        logger.exception("Failed to access job queue")
        return "Job queue unavailable."

    jobs = queue.get_failed_jobs(limit=limit)
    if not jobs:
        return "No failed jobs."

    parts: list[str] = []
    for job in jobs:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(job["created_at"]))
        error = job.get("error") or "unknown error"
        parts.append(
            f"[{ts}] #{job['id']} ({job['job_type']}) {job['file_path']}\n"
            f"  Attempts: {job['attempts']}/{job['max_attempts']}  |  Error: {error}"
        )

    return "\n\n".join(parts)


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
            pass

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
