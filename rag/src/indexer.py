"""Queue worker: dequeue jobs, parse, summarise, and store in ChromaDB."""

from __future__ import annotations

import logging
import signal
import time
from pathlib import Path
from typing import Any

from .queue_db import JobQueue, JobType
from .store import Store
from .summariser import summarise, fallback_extract
from .parsers.jsonl import parse_conversation
from .parsers.code import parse_code_file
from .parsers.markdown import parse_markdown
from .parsers.config import parse_config

logger = logging.getLogger(__name__)

# Collection mapping by job type
COLLECTION_MAP = {
    JobType.CONVERSATION.value: "conversations",
    JobType.CODE.value: "code",
    JobType.MARKDOWN.value: "docs",
    JobType.CONFIG.value: "docs",
}

POLL_INTERVAL = 2  # seconds between queue checks when idle
BATCH_SIZE = 5
CLEANUP_INTERVAL = 500  # clean completed jobs every N processed


class Indexer:
    """Background worker that processes the job queue."""

    def __init__(
        self,
        store: Store | None = None,
        queue: JobQueue | None = None,
    ) -> None:
        self.store = store or Store()
        self.queue = queue or JobQueue()
        self._running = False
        self._processed_count = 0

    def process_job(self, job: Any) -> None:
        """Process a single job: parse, summarise, store."""
        path = Path(job.file_path)
        job_type = job.job_type

        logger.info("Processing %s (%s)", path, job_type)

        try:
            if job_type == JobType.CONVERSATION.value:
                self._process_conversation(path)
            elif job_type == JobType.CODE.value:
                self._process_code(path)
            elif job_type == JobType.MARKDOWN.value:
                self._process_markdown(path)
            elif job_type == JobType.CONFIG.value:
                self._process_config(path)
            else:
                logger.warning("Unknown job type: %s", job_type)
                self.queue.fail(job.id, f"Unknown job type: {job_type}")
                return

            self.queue.complete(job.id, job.file_hash)
            logger.info("Completed %s", path)

            self._processed_count += 1
            if self._processed_count % CLEANUP_INTERVAL == 0:
                removed = self.queue.clear_completed(older_than_hours=24)
                if removed:
                    logger.info("Cleaned %d old completed jobs", removed)

        except Exception as e:
            logger.exception("Failed to process %s", path)
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"
            self.queue.fail(job.id, error_msg)

    def _process_conversation(self, path: Path) -> None:
        """Index conversation turns from a JSONL file."""
        turns = parse_conversation(path)
        if not turns:
            logger.info("No turns extracted from %s", path)
            return

        for turn in turns:
            text = turn["text"]

            if turn["needs_summary"]:
                summary = summarise(text, "conversation")
                if summary:
                    text = summary
                else:
                    text = fallback_extract(text)

            self.store.upsert(
                collection_name="conversations",
                identifier=turn["identifier"],
                document=text,
                metadata=turn["metadata"],
            )

    def _process_code(self, path: Path) -> None:
        """Index a source code file."""
        parsed = parse_code_file(path)
        if not parsed:
            return

        text = parsed["text"]

        if parsed["needs_summary"]:
            raw = parsed.get("raw_content", text)
            summary = summarise(raw, "code")
            if summary:
                text = f"{text}\n\nSummary: {summary}"

        self.store.upsert(
            collection_name="code",
            identifier=parsed["identifier"],
            document=text,
            metadata=parsed["metadata"],
        )

    def _process_markdown(self, path: Path) -> None:
        """Index a markdown document."""
        parsed = parse_markdown(path)
        if not parsed:
            return

        text = parsed["text"]

        if parsed["needs_summary"]:
            summary = summarise(text, "markdown")
            if summary:
                text = summary
            else:
                text = fallback_extract(text)

        self.store.upsert(
            collection_name="docs",
            identifier=parsed["identifier"],
            document=text,
            metadata=parsed["metadata"],
        )

    def _process_config(self, path: Path) -> None:
        """Index a config file."""
        parsed = parse_config(path)
        if not parsed:
            return

        self.store.upsert(
            collection_name="docs",
            identifier=parsed["identifier"],
            document=parsed["text"],
            metadata=parsed["metadata"],
        )

    def run(self) -> None:
        """Run the worker loop. Blocks until SIGINT/SIGTERM."""
        self._running = True

        def _stop(signum: int, frame: Any) -> None:
            logger.info("Received signal %d, stopping...", signum)
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        self.queue.recover_stale()
        logger.info("Indexer started, polling queue...")

        while self._running:
            try:
                jobs = self.queue.dequeue(batch_size=BATCH_SIZE)
            except Exception:
                logger.exception("Failed to dequeue jobs, retrying in %ds", POLL_INTERVAL)
                time.sleep(POLL_INTERVAL)
                continue

            if not jobs:
                time.sleep(POLL_INTERVAL)
                continue

            for job in jobs:
                if not self._running:
                    break
                self.process_job(job)

        logger.info("Indexer stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    indexer = Indexer()
    indexer.run()


if __name__ == "__main__":
    main()
