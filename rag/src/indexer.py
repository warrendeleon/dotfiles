"""Queue worker: dequeue conversation jobs, parse, and embed in ChromaDB."""

from __future__ import annotations

import gc
import logging
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from .queue_db import JobQueue, JobType
from .store import Store
from .parsers.jsonl import parse_conversation

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2
BATCH_SIZE = 1
CLEANUP_INTERVAL = 500
CLIENT_REFRESH_INTERVAL = 200
MAX_EMBED_CHARS = 24_000  # ~6K tokens, within the 8K token embedding window
EMBED_BATCH_SIZE = 4  # turns per embedding call, prevents GPU OOM on large conversations
RSS_LOG_INTERVAL = 50
IDLE_UNLOAD_SECONDS = 120
BATCH_LOG_INTERVAL = 50  # log every N embedding batches inside a single file
WATCHDOG_TIMEOUT = 600  # seconds; force-exit if a job makes no progress for this long
WATCHDOG_POLL = 30

def _get_rss_mb() -> float:
    """Current process RSS in megabytes (not peak)."""
    try:
        import subprocess as _sp
        result = _sp.run(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip()) / 1024
    except Exception:
        pass
    return 0.0


PAUSE_BELOW = 15
RESUME_ABOVE = 20
POWER_CHECK_INTERVAL = 30
SESSION_CHECK_INTERVAL = 10
DEFAULT_THROTTLE_DELAY = 2.0
DEFAULT_JOB_DELAY = 0.0


def _load_delays() -> tuple[float, float]:
    """Read job_delay_seconds and throttle_delay_seconds from ~/.rag/config.yaml."""
    config_path = Path.home() / ".rag" / "config.yaml"
    job_delay = DEFAULT_JOB_DELAY
    throttle_delay = DEFAULT_THROTTLE_DELAY
    try:
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            val = config.get("job_delay_seconds")
            if val is not None:
                job_delay = float(val)
            val = config.get("throttle_delay_seconds")
            if val is not None:
                throttle_delay = float(val)
    except Exception:
        pass
    return job_delay, throttle_delay


class Indexer:
    """Background worker that processes the conversation job queue."""

    def __init__(
        self,
        store: Store | None = None,
        queue: JobQueue | None = None,
    ) -> None:
        self.store = store or Store()
        self.queue = queue or JobQueue()
        self._running = False
        self._processed_count = 0
        self._paused = False
        self._throttling = False
        self._session_blocked = False
        self._idle_unloaded = False
        self._last_job_time = time.monotonic()
        self._job_delay, self._throttle_delay = _load_delays()
        self._last_power_check = 0.0
        self._cached_power_state: dict[str, Any] = {}
        self._last_session_check = 0.0
        self._cached_session_active = False
        self._progress_ts = time.monotonic()
        self._current_job_id: int | None = None
        self._watchdog_started = False

    def _get_power_state(self) -> dict[str, Any]:
        """Read battery percentage, charging state, and power source from pmset.

        Cached for POWER_CHECK_INTERVAL seconds so we don't fork a subprocess
        on every job.
        """
        now = time.monotonic()
        if now - self._last_power_check < POWER_CHECK_INTERVAL:
            return self._cached_power_state

        self._last_power_check = now
        state: dict[str, Any] = {"percent": None, "ac_attached": False, "discharging": False}

        try:
            result = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                output = result.stdout
                state["ac_attached"] = "AC Power" in output
                for line in output.splitlines():
                    if "InternalBattery" in line:
                        for part in line.split(";"):
                            part = part.strip()
                            if "%" in part:
                                pct_str = part.split("%")[0].strip().split()[-1]
                                state["percent"] = int(pct_str)
                            elif part == "discharging":
                                state["discharging"] = True
        except Exception:
            logger.debug("Failed to read battery status")

        self._cached_power_state = state
        return state

    def _should_pause(self) -> bool:
        """Check if indexing should pause due to low battery."""
        state = self._get_power_state()
        pct = state.get("percent")
        if pct is None:
            return False

        if self._paused:
            if pct >= RESUME_ABOVE:
                self._paused = False
                logger.info("Battery at %d%%, resuming indexing", pct)
            return self._paused
        else:
            if pct < PAUSE_BELOW:
                self._paused = True
                logger.info("Battery at %d%%, pausing indexing until %d%%", pct, RESUME_ABOVE)
            return self._paused

    def _should_throttle(self) -> bool:
        """Throttle when on AC but the battery is discharging (charger can't keep up)."""
        state = self._get_power_state()
        throttle = state.get("ac_attached", False) and state.get("discharging", False)

        if throttle and not self._throttling:
            self._throttling = True
            logger.info(
                "Battery discharging on AC power, throttling (%.1fs delay between jobs)",
                self._throttle_delay,
            )
        elif not throttle and self._throttling:
            self._throttling = False
            logger.info("Battery no longer discharging on AC, full speed resumed")

        return throttle

    def _session_active(self) -> bool:
        """Check if any Claude Code session is running."""
        now = time.monotonic()
        if now - self._last_session_check < SESSION_CHECK_INTERVAL:
            return self._cached_session_active

        self._last_session_check = now
        # `pgrep -x claude` doesn't reliably match the Claude CLI on macOS — read
        # the comm column from ps directly and look for an exact "claude" entry.
        active = False
        try:
            result = subprocess.run(
                ["ps", "-axo", "comm"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.strip() == "claude":
                        active = True
                        break
        except Exception:
            active = False

        if active and not self._session_blocked:
            self._session_blocked = True
            logger.info("Claude session active, pausing indexing")
        elif not active and self._session_blocked:
            self._session_blocked = False
            logger.info("No Claude sessions running, resuming indexing")

        self._cached_session_active = active
        return active

    def _heartbeat(self) -> None:
        """Bump the watchdog progress timestamp so we don't get killed mid-work."""
        self._progress_ts = time.monotonic()

    def _watchdog_loop(self) -> None:
        """Force-exit if a job makes no progress for WATCHDOG_TIMEOUT seconds.

        Python can't reliably interrupt a blocked C extension call (MPS / sqlite
        / native libs), so the only sure recovery is to terminate the process
        and let launchd respawn us. recover_stale() will requeue the wedged job
        on the next startup; queue retry/backoff limits the loop length.
        """
        while self._running:
            time.sleep(WATCHDOG_POLL)
            if not self._running:
                return
            jid = self._current_job_id
            if jid is None:
                continue
            stalled = time.monotonic() - self._progress_ts
            if stalled <= WATCHDOG_TIMEOUT:
                continue
            logger.error(
                "Watchdog: job %d stalled for %.0fs (limit %ds), exiting for restart",
                jid, stalled, WATCHDOG_TIMEOUT,
            )
            try:
                self.queue.fail(jid, f"watchdog timeout after {int(stalled)}s")
            except Exception:
                logger.exception("Watchdog: failed to mark job %d as failed", jid)
            os._exit(2)

    def process_job(self, job: Any) -> None:
        """Process a single conversation job: parse and embed turns."""
        path = Path(job.file_path)
        logger.info("Processing %s", path)
        self._current_job_id = job.id
        self._heartbeat()

        try:
            if job.job_type == JobType.WIKI.value:
                self._process_wiki_page(path)
            else:
                self._process_conversation(path)
            self.queue.complete(job.id, job.file_hash)
            logger.info("Completed %s", path)
        except Exception as e:
            logger.exception("Failed to process %s", path)
            error_msg = f"{type(e).__name__}: {str(e)[:200]}"
            self.queue.fail(job.id, error_msg)
            self._current_job_id = None
            return

        self._current_job_id = None
        self._processed_count += 1
        self._last_job_time = time.monotonic()
        self._run_maintenance()

    def _run_maintenance(self) -> None:
        """Periodic housekeeping. Each task is isolated so one failure doesn't block the rest."""
        if self._processed_count % RSS_LOG_INTERVAL == 0:
            try:
                rss_mb = _get_rss_mb()
                logger.info(
                    "Jobs processed: %d, RSS: %.0f MB",
                    self._processed_count, rss_mb,
                )
            except Exception:
                logger.exception("RSS logging failed")

        if self._processed_count % CLEANUP_INTERVAL == 0:
            try:
                removed = self.queue.clear_completed(older_than_hours=24)
                if removed:
                    logger.info("Cleaned %d old completed jobs", removed)
            except Exception:
                logger.exception("Queue cleanup failed")

        if self._processed_count % CLIENT_REFRESH_INTERVAL == 0:
            try:
                logger.info("Refreshing ChromaDB client to flush HNSW caches")
                self.store.reset_client()
                gc.collect()
            except Exception:
                logger.exception("ChromaDB client refresh failed")

    def _process_conversation(self, path: Path) -> None:
        """Index conversation turns from a JSONL file."""
        turns = parse_conversation(path)
        if not turns:
            logger.info("No turns extracted from %s", path)
            return

        identifiers = []
        documents = []
        metadatas = []

        for turn in turns:
            text = turn["text"]
            if not text or not text.strip():
                continue
            if len(text) > MAX_EMBED_CHARS:
                text = text[:MAX_EMBED_CHARS]
            identifiers.append(turn["identifier"])
            documents.append(text)
            metadatas.append(turn["metadata"])

        total = len(documents)
        batches = (total + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
        if batches > BATCH_LOG_INTERVAL:
            logger.info("Embedding %d turns in %d batches for %s", total, batches, path.name)
        t_start = time.monotonic()
        for bi, i in enumerate(range(0, total, EMBED_BATCH_SIZE)):
            t0 = time.monotonic()
            self.store.upsert_batch(
                collection_name="conversations",
                identifiers=identifiers[i:i + EMBED_BATCH_SIZE],
                documents=documents[i:i + EMBED_BATCH_SIZE],
                metadatas=metadatas[i:i + EMBED_BATCH_SIZE],
            )
            self._heartbeat()
            dt = time.monotonic() - t0
            if dt > 30:
                # A single embed batch shouldn't take 30s. Log the offender so
                # we can spot pathological turns before the watchdog fires.
                sizes = [len(d) for d in documents[i:i + EMBED_BATCH_SIZE]]
                logger.warning(
                    "Slow batch %d/%d in %s: %.1fs, char sizes=%s",
                    bi + 1, batches, path.name, dt, sizes,
                )
            if batches > BATCH_LOG_INTERVAL and (bi + 1) % BATCH_LOG_INTERVAL == 0:
                elapsed = time.monotonic() - t_start
                logger.info(
                    "Progress %s: batch %d/%d (%.0f%%) elapsed=%.1fs",
                    path.name, bi + 1, batches, 100.0 * (bi + 1) / batches, elapsed,
                )

    def _process_wiki_page(self, path: Path) -> None:
        """Index a single wiki markdown page into the wiki collection.

        Used for the session summaries the sweep enqueues, so a new page becomes
        searchable through the one shared embedder rather than the sweep loading
        its own. upsert_batch feeds both Chroma and the FTS keyword index.
        """
        from .parsers.markdown import parse_wiki_page

        wiki_root = Path(os.environ.get("RAG_WIKI_ROOT") or (Path.home() / ".wiki"))
        try:
            chunks = parse_wiki_page(path, wiki_root)
        except ValueError:
            logger.warning("Wiki page %s is outside %s; skipping", path, wiki_root)
            return
        if not chunks:
            logger.info("No chunks from wiki page %s", path)
            return

        self.store.upsert_batch(
            collection_name="wiki",
            identifiers=[c["identifier"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
        self._heartbeat()
        logger.info("Indexed wiki page %s (%d chunks)", path.name, len(chunks))

    def run(self) -> None:
        """Run the worker loop. Blocks until SIGINT/SIGTERM."""
        self._running = True

        def _stop(signum: int, frame: Any) -> None:
            logger.info("Received signal %d, stopping...", signum)
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        self.queue.recover_stale()
        if not self._watchdog_started:
            t = threading.Thread(target=self._watchdog_loop, name="indexer-watchdog", daemon=True)
            t.start()
            self._watchdog_started = True
        logger.info(
            "Indexer started, polling queue (watchdog=%ds, batch_log_every=%d batches)",
            WATCHDOG_TIMEOUT, BATCH_LOG_INTERVAL,
        )

        while self._running:
            idle = self._should_pause() or self._session_active()

            # Idle-unload runs regardless of *why* we're idle — battery pause,
            # active Claude session, or just an empty queue. Previously this
            # check sat below the pause/session gate, so the model stayed
            # pinned in GPU memory whenever either gate was held.
            if (
                not self._idle_unloaded
                and time.monotonic() - self._last_job_time > IDLE_UNLOAD_SECONDS
            ):
                logger.info(
                    "Idle for %ds, unloading model to free memory",
                    IDLE_UNLOAD_SECONDS,
                )
                self.store.unload()
                gc.collect()
                self._idle_unloaded = True

            if idle:
                time.sleep(POLL_INTERVAL)
                continue

            try:
                jobs = self.queue.dequeue(batch_size=BATCH_SIZE)
            except Exception:
                logger.exception("Failed to dequeue jobs, retrying in %ds", POLL_INTERVAL)
                time.sleep(POLL_INTERVAL)
                continue

            if not jobs:
                time.sleep(POLL_INTERVAL)
                continue

            if self._idle_unloaded:
                logger.info("New jobs arrived, model will reload on next embed")
                self._idle_unloaded = False

            self._last_job_time = time.monotonic()
            for job in jobs:
                if not self._running:
                    break
                if self._should_pause() or self._session_active():
                    break
                self.process_job(job)
                gc.collect()
                if self._job_delay > 0:
                    time.sleep(self._job_delay)
                if self._should_throttle():
                    time.sleep(self._throttle_delay)

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
