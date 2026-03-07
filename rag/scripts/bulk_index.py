#!/usr/bin/env python3
"""First-run bulk indexer. Enqueues all existing files for processing.

Resumable: skips files already in the queue. Run the indexer worker
separately to process the queue.

Usage:
    python -m scripts.bulk_index [--conversations-only] [--code-only] [--recent-days N]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.queue_db import JobQueue, JobType

logger = logging.getLogger(__name__)

CONVERSATION_DIR = Path.home() / ".claude" / "projects"
DEVELOPER_DIR = Path.home() / "Developer"


def _enqueue_conversations(queue: JobQueue, recent_days: int | None = None) -> int:
    """Enqueue conversation JSONL files."""
    count = 0
    if not CONVERSATION_DIR.exists():
        logger.warning("Conversation directory not found: %s", CONVERSATION_DIR)
        return 0

    now = time.time()
    cutoff = now - (recent_days * 86400) if recent_days else 0

    # Collect files with their mtime (single stat call per file)
    file_mtimes: list[tuple[Path, float]] = []
    for path in CONVERSATION_DIR.rglob("*.jsonl"):
        try:
            mtime = path.stat().st_mtime
            file_mtimes.append((path, mtime))
        except OSError:
            continue

    file_mtimes.sort(key=lambda x: x[1], reverse=True)

    for path, mtime in file_mtimes:
        if recent_days and mtime < cutoff:
            continue

        # Priority: newer files get higher priority
        age_days = (now - mtime) / 86400
        priority = max(1, 10 - int(age_days / 3))

        job_id = queue.enqueue(str(path), JobType.CONVERSATION.value, priority=priority)
        if job_id:
            count += 1

    return count


def _enqueue_code(queue: JobQueue) -> int:
    """Enqueue source code files."""
    from src.parsers.code import SUPPORTED_EXTENSIONS, SKIP_PATTERNS

    count = 0
    if not DEVELOPER_DIR.exists():
        logger.warning("Developer directory not found: %s", DEVELOPER_DIR)
        return 0

    for path in DEVELOPER_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SUPPORTED_EXTENSIONS:
            continue
        if any(skip in path.parts for skip in SKIP_PATTERNS):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 500_000:
            continue

        job_id = queue.enqueue(str(path), JobType.CODE.value, priority=3)
        if job_id:
            count += 1

    return count


def _enqueue_docs(queue: JobQueue) -> int:
    """Enqueue markdown and config files."""
    count = 0
    if not DEVELOPER_DIR.exists():
        return 0

    for path in DEVELOPER_DIR.rglob("*.md"):
        if any(skip in path.parts for skip in ("node_modules", ".git", "__pycache__", "dist", "build")):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 200_000:
            continue

        job_id = queue.enqueue(str(path), JobType.MARKDOWN.value, priority=2)
        if job_id:
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk index files into RAG queue")
    parser.add_argument("--conversations-only", action="store_true", help="Only index conversations")
    parser.add_argument("--code-only", action="store_true", help="Only index code files")
    parser.add_argument("--recent-days", type=int, default=None, help="Only index conversations from last N days")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    queue = JobQueue()

    if args.conversations_only:
        count = _enqueue_conversations(queue, recent_days=args.recent_days)
        logger.info("Enqueued %d conversation files", count)
        return

    if args.code_only:
        count = _enqueue_code(queue)
        logger.info("Enqueued %d code files", count)
        return

    # Full index: conversations first (highest priority), then code, then docs
    logger.info("Starting bulk index...")

    conv_count = _enqueue_conversations(queue, recent_days=args.recent_days)
    logger.info("Enqueued %d conversation files", conv_count)

    code_count = _enqueue_code(queue)
    logger.info("Enqueued %d code files", code_count)

    doc_count = _enqueue_docs(queue)
    logger.info("Enqueued %d documentation files", doc_count)

    total = conv_count + code_count + doc_count
    logger.info("Total: %d files enqueued. Run the indexer worker to process them.", total)

    stats = queue.stats()
    logger.info("Queue stats: %s", stats)


if __name__ == "__main__":
    main()
