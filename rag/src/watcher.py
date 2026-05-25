"""File watcher: fswatch subprocess -> enqueue conversation JSONL changes."""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from .queue_db import JobQueue, JobType

logger = logging.getLogger(__name__)

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

EXCLUDED_PROJECT_SUFFIXES = [
    "-dotfiles-rag",
]

class Watcher:
    """Watch for new/changed conversation JSONLs and enqueue indexing jobs."""

    def __init__(self, queue: JobQueue | None = None) -> None:
        self.queue = queue or JobQueue()
        self._process: subprocess.Popen | None = None
        self._running = False

    def _build_fswatch_cmd(self) -> list[str]:
        return [
            "fswatch",
            "--recursive",
            "--event", "Created",
            "--event", "Updated",
            "--event", "Renamed",
            "--event", "MovedTo",
            "--include", r"\.jsonl$",
            "--exclude", r".*",
            str(CLAUDE_PROJECTS_DIR),
        ]

    def _handle_event(self, path_str: str) -> None:
        path_str = path_str.strip()
        if not path_str:
            return

        path = Path(path_str)
        if not path.is_file() or path.suffix != ".jsonl":
            return

        if not str(path.resolve()).startswith(str(CLAUDE_PROJECTS_DIR)):
            return

        for suffix in EXCLUDED_PROJECT_SUFFIXES:
            if suffix in str(path):
                return

        job_id = self.queue.enqueue(
            str(path), JobType.CONVERSATION.value, priority=10,
        )
        if job_id:
            logger.debug("Enqueued %s (job %d)", path.name, job_id)

    def run(self) -> None:
        """Run the watcher. Blocks until SIGINT/SIGTERM."""
        self._running = True

        def _stop(signum: int, frame: Any) -> None:
            logger.info("Received signal %d, stopping watcher...", signum)
            self._running = False
            if self._process:
                self._process.terminate()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        watch_path = str(CLAUDE_PROJECTS_DIR)
        if not CLAUDE_PROJECTS_DIR.exists():
            logger.error("Watch path does not exist: %s", watch_path)
            return

        logger.info("Watching: %s", watch_path)

        cmd = self._build_fswatch_cmd()

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )

            for line in self._process.stdout:
                if not self._running:
                    break
                try:
                    self._handle_event(line)
                except Exception:
                    logger.exception("Error handling event: %s", line.strip()[:100])

        except FileNotFoundError:
            logger.error("fswatch not found. Install with: brew install fswatch")
            sys.exit(1)
        except Exception:
            logger.exception("Watcher failed")
        finally:
            if self._process:
                self._process.terminate()
                self._process.wait()

        logger.info("Watcher stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    watcher = Watcher()
    watcher.run()


if __name__ == "__main__":
    main()
