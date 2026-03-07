"""SQLite job queue with retry, backoff, and deduplication."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_PATH = Path.home() / ".rag" / "queue.db"
MAX_ATTEMPTS = 4  # 1 initial + 3 retries with backoff: 30s, 120s, 480s
BACKOFF_BASE = 30


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, Enum):
    CONVERSATION = "conversation"
    CODE = "code"
    MARKDOWN = "markdown"
    CONFIG = "config"


class Job:
    """A single indexing job."""

    def __init__(
        self,
        id: int,
        file_path: str,
        job_type: str,
        status: str,
        priority: int,
        attempts: int,
        max_attempts: int,
        next_retry: float,
        error: str | None,
        created_at: float,
        file_hash: str | None,
    ) -> None:
        self.id = id
        self.file_path = file_path
        self.job_type = job_type
        self.status = status
        self.priority = priority
        self.attempts = attempts
        self.max_attempts = max_attempts
        self.next_retry = next_retry
        self.error = error
        self.created_at = created_at
        self.file_hash = file_hash


def _file_hash(path: str) -> str | None:
    """SHA-256 of file contents, or None if unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return None


class JobQueue:
    """SQLite-backed job queue with retry and deduplication."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DEFAULT_QUEUE_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 4,
                    next_retry REAL NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at REAL NOT NULL,
                    file_hash TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status_retry
                ON jobs (status, next_retry)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_file_path
                ON jobs (file_path, status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_status_created
                ON jobs (status, created_at)
            """)

    def enqueue(
        self,
        file_path: str,
        job_type: str | JobType,
        priority: int = 0,
    ) -> int | None:
        """Add a job. Returns job ID, or None if deduplicated."""
        jtype = job_type.value if isinstance(job_type, JobType) else job_type
        fhash = _file_hash(file_path)

        with self._conn() as conn:
            # Deduplicate: skip if pending/processing job exists for same path
            row = conn.execute(
                """SELECT id, file_hash FROM jobs
                   WHERE file_path = ? AND status IN ('pending', 'processing')
                   LIMIT 1""",
                (file_path,),
            ).fetchone()

            if row:
                # If hash matches an existing pending job, skip entirely
                if row["file_hash"] and fhash and row["file_hash"] == fhash:
                    return None
                # If hash differs, update the existing job (file changed again)
                conn.execute(
                    "UPDATE jobs SET file_hash = ?, priority = MAX(priority, ?) WHERE id = ?",
                    (fhash, priority, row["id"]),
                )
                return row["id"]

            # Also skip if most recent completed job has same hash
            completed = conn.execute(
                """SELECT file_hash FROM jobs
                   WHERE file_path = ? AND status = 'completed'
                   ORDER BY id DESC LIMIT 1""",
                (file_path,),
            ).fetchone()

            if completed and completed["file_hash"] and fhash and completed["file_hash"] == fhash:
                return None

            cursor = conn.execute(
                """INSERT INTO jobs (file_path, job_type, status, priority,
                                     attempts, max_attempts, next_retry, created_at, file_hash)
                   VALUES (?, ?, 'pending', ?, 0, ?, 0, ?, ?)""",
                (file_path, jtype, priority, MAX_ATTEMPTS, time.time(), fhash),
            )
            return cursor.lastrowid

    def dequeue(self, batch_size: int = 1) -> list[Job]:
        """Claim up to batch_size ready jobs. Returns claimed jobs."""
        now = time.time()
        jobs: list[Job] = []

        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM jobs
                   WHERE status = 'pending' AND next_retry <= ?
                   ORDER BY priority DESC, created_at ASC
                   LIMIT ?""",
                (now, batch_size),
            ).fetchall()

            for row in rows:
                conn.execute(
                    "UPDATE jobs SET status = 'processing', attempts = attempts + 1 WHERE id = ?",
                    (row["id"],),
                )
                job = Job(**dict(row))
                job.status = JobStatus.PROCESSING.value
                job.attempts += 1
                jobs.append(job)

        return jobs

    def complete(self, job_id: int, file_hash: str | None = None) -> None:
        """Mark a job as completed."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'completed', file_hash = COALESCE(?, file_hash) WHERE id = ?",
                (file_hash, job_id),
            )

    def fail(self, job_id: int, error: str) -> None:
        """Mark a job as failed with exponential backoff retry."""
        now = time.time()

        with self._conn() as conn:
            row = conn.execute("SELECT attempts, max_attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return

            if row["attempts"] >= row["max_attempts"]:
                conn.execute(
                    "UPDATE jobs SET status = 'failed', error = ? WHERE id = ?",
                    (error, job_id),
                )
            else:
                # Exponential backoff: 30s, 120s, 480s
                exponent = max(0, row["attempts"] - 1)
                delay = BACKOFF_BASE * (4 ** exponent)
                conn.execute(
                    "UPDATE jobs SET status = 'pending', error = ?, next_retry = ? WHERE id = ?",
                    (error, now + delay, job_id),
                )

    def stats(self) -> dict[str, int]:
        """Return counts by status."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
            ).fetchall()
            return {row["status"]: row["cnt"] for row in rows}

    def pending_count(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM jobs WHERE status = 'pending'"
            ).fetchone()
            return row["cnt"] if row else 0

    def recover_stale(self) -> int:
        """Reset all jobs stuck in 'processing' (e.g. after a crash).

        On startup, any job still in 'processing' means the previous
        process died mid-work. Reset them all to 'pending' for retry.
        """
        with self._conn() as conn:
            cursor = conn.execute(
                """UPDATE jobs SET status = 'pending', error = 'recovered after stale processing'
                   WHERE status = 'processing'""",
            )
            count = cursor.rowcount
            if count:
                logger.info("Recovered %d stale processing jobs", count)
            return count

    def clear_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed jobs older than N hours."""
        if older_than_hours < 1:
            older_than_hours = 1
        cutoff = time.time() - (older_than_hours * 3600)
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM jobs WHERE status = 'completed' AND created_at < ?",
                (cutoff,),
            )
            return cursor.rowcount
