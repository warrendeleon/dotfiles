"""File watcher: fswatch subprocess -> enqueue changes to the job queue."""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from .queue_db import JobQueue, JobType
from .parsers.code import SUPPORTED_EXTENSIONS, SKIP_PATTERNS

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".rag" / "config.yaml"

# Directories that are allowed to be hidden (not skipped)
_ALLOWED_HIDDEN_DIRS = {".claude"}


def _load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load watcher config from YAML."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                logger.warning("Config %s is not a YAML mapping, using defaults", path)
                return {}
            return data
    except (yaml.YAMLError, OSError) as e:
        logger.warning("Failed to load config %s: %s, using defaults", path, e)
        return {}


def _classify_file(path: Path) -> str | None:
    """Determine the job type for a file, or None to skip."""
    if path.suffix == ".jsonl":
        # Only index Claude conversation files (boundary-anchored check)
        resolved = str(path.resolve())
        claude_marker = f"{Path.home()}/.claude/projects/"
        if resolved.startswith(claude_marker):
            return JobType.CONVERSATION.value
        return None

    if path.suffix in (".md", ".mdx"):
        return JobType.MARKDOWN.value

    if path.suffix in SUPPORTED_EXTENSIONS:
        return JobType.CODE.value

    # Check if it is a known config file
    from .parsers.config import _is_config_file
    if _is_config_file(path):
        return JobType.CONFIG.value

    return None


def _should_skip_path(path_str: str) -> bool:
    """Check if a path should be skipped."""
    for pattern in SKIP_PATTERNS:
        if f"/{pattern}/" in path_str or path_str.endswith(f"/{pattern}"):
            return True

    # Skip hidden directories (not files), except allowed ones
    path = Path(path_str)
    for part in path.parent.parts:
        if part.startswith(".") and part not in _ALLOWED_HIDDEN_DIRS:
            return True

    return False


class Watcher:
    """Watch filesystem changes via fswatch and enqueue indexing jobs."""

    def __init__(
        self,
        queue: JobQueue | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.queue = queue or JobQueue()
        self.config = _load_config(config_path)
        self._process: subprocess.Popen | None = None
        self._running = False

    def _get_watch_paths(self) -> list[str]:
        """Get paths to watch from config."""
        paths = self.config.get("watch_paths", [])
        if not paths:
            home = str(Path.home())
            paths = [
                f"{home}/Developer",
                f"{home}/.claude/projects",
            ]
        # Expand ~ and filter to paths that exist
        expanded = [str(Path(p).expanduser()) for p in paths]
        return [p for p in expanded if Path(p).exists()]

    def _build_fswatch_cmd(self, paths: list[str]) -> list[str]:
        """Build the fswatch command."""
        cmd = [
            "fswatch",
            "--recursive",
            "--event", "Created",
            "--event", "Updated",
            "--event", "Renamed",
            "--event", "MovedTo",
            # Exclude common noise
            "--exclude", r"\.git/",
            "--exclude", r"node_modules/",
            "--exclude", r"__pycache__/",
            "--exclude", r"\.next/",
            "--exclude", r"build/",
            "--exclude", r"dist/",
            "--exclude", r"\.expo/",
            "--exclude", r"coverage/",
            "--exclude", r"\.yarn/",
            "--exclude", r"Pods/",
            "--exclude", r"\.rag/",
        ]
        cmd.extend(paths)
        return cmd

    def _handle_event(self, path_str: str) -> None:
        """Process a single fswatch event."""
        path_str = path_str.strip()
        if not path_str:
            return

        if _should_skip_path(path_str):
            return

        path = Path(path_str)
        if not path.is_file():
            return

        job_type = _classify_file(path)
        if not job_type:
            return

        # Priority: conversations > code > docs
        priority = 0
        if job_type == JobType.CONVERSATION.value:
            priority = 10
        elif job_type == JobType.CODE.value:
            priority = 5

        job_id = self.queue.enqueue(str(path), job_type, priority=priority)
        if job_id:
            logger.debug("Enqueued %s (%s) job %d", path.name, job_type, job_id)

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

        paths = self._get_watch_paths()
        if not paths:
            logger.error("No valid watch paths found")
            return

        logger.info("Watching: %s", ", ".join(paths))

        cmd = self._build_fswatch_cmd(paths)

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
