"""SQLite ledger of which sessions have been summarised.

Keeps the sweep idempotent and decoupled from the wiki. A session is "done"
when its transcript hash is already recorded, so a sweep can run repeatedly,
resume after a crash, and re-summarise only sessions that grew since last time.
Grepping wiki frontmatter would not survive an unsynced wiki; a local table
does, which is why this lives next to queue.db rather than in the pages.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)

DEFAULT_LEDGER_PATH = Path.home() / ".rag" / "summaries.db"

# Statuses that count as "handled, do not redo for this hash".
_DONE_STATUSES = ("written", "needs-review", "skipped")


class SummaryLedger:
    """Records the summarisation outcome per session transcript."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DEFAULT_LEDGER_PATH)
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
                CREATE TABLE IF NOT EXISTS summaries (
                    session_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_hash TEXT,
                    page_path TEXT,
                    status TEXT NOT NULL,
                    model TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_status ON summaries (status)"
            )

    def is_done(self, session_id: str, file_hash: str | None) -> bool:
        """True if this exact transcript hash is already handled.

        A changed hash (the session continued) returns False so it is
        re-summarised. A prior 'error' returns False so it is retried.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT file_hash, status FROM summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return False
        if row["status"] not in _DONE_STATUSES:
            return False
        if file_hash is None:
            # Cannot compare; treat an existing handled row as done.
            return True
        return row["file_hash"] == file_hash

    def record(
        self,
        session_id: str,
        file_path: str,
        file_hash: str | None,
        page_path: str | None,
        status: str,
        model: str | None,
    ) -> None:
        """Insert or replace the outcome for a session."""
        now = time.time()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT created_at FROM summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            created = existing["created_at"] if existing else now
            conn.execute(
                """INSERT INTO summaries
                       (session_id, file_path, file_hash, page_path, status,
                        model, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                       file_path=excluded.file_path,
                       file_hash=excluded.file_hash,
                       page_path=excluded.page_path,
                       status=excluded.status,
                       model=excluded.model,
                       updated_at=excluded.updated_at""",
                (session_id, file_path, file_hash, page_path, status,
                 model, created, now),
            )

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM summaries WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None

    def stats(self) -> dict[str, int]:
        """Counts by status."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS cnt FROM summaries GROUP BY status"
            ).fetchall()
            return {row["status"]: row["cnt"] for row in rows}
