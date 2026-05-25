#!/usr/bin/env python3
"""First-run bulk indexer. Enqueues all conversation JSONL files for processing.

Resumable: skips files already in the queue. Run the indexer worker
separately to process the queue.

Usage:
    python -m scripts.bulk_index [--recent-days N]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.queue_db import JobQueue, JobType

logger = logging.getLogger(__name__)

CONVERSATION_DIR = Path.home() / ".claude" / "projects"


def _enqueue_conversations(queue: JobQueue, recent_days: int | None = None) -> int:
    count = 0
    if not CONVERSATION_DIR.exists():
        logger.warning("Conversation directory not found: %s", CONVERSATION_DIR)
        return 0

    now = time.time()
    cutoff = now - (recent_days * 86400) if recent_days else 0

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

        age_days = (now - mtime) / 86400
        priority = max(1, 10 - int(age_days / 3))

        job_id = queue.enqueue(str(path), JobType.CONVERSATION.value, priority=priority)
        if job_id:
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk index conversation files into RAG queue")
    parser.add_argument("--recent-days", type=int, default=None, help="Only index conversations from last N days")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    queue = JobQueue()

    logger.info("Starting bulk index of conversations...")
    count = _enqueue_conversations(queue, recent_days=args.recent_days)
    logger.info("Enqueued %d conversation files", count)

    stats = queue.stats()
    logger.info("Queue stats: %s", stats)


if __name__ == "__main__":
    main()
