"""Append-only audit log for tracking actions taken by Claude Code."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

DEFAULT_AUDIT_PATH = Path.home() / ".rag" / "audit.db"


class AuditLog:
    """SQLite-backed append-only audit log."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DEFAULT_AUDIT_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._init_db()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
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
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    description TEXT NOT NULL,
                    files_affected TEXT,
                    project_path TEXT,
                    session_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log (timestamp)
            """)

    def log(
        self,
        description: str,
        files_affected: list[str] | None = None,
        project_path: str | None = None,
        session_id: str | None = None,
    ) -> int | None:
        """Record an action. Returns the entry ID, or None on failure."""
        files_json = json.dumps(files_affected) if files_affected else None

        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO audit_log (timestamp, description, files_affected, project_path, session_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (time.time(), description, files_json, project_path, session_id),
            )
            return cursor.lastrowid

    def get_entries(
        self,
        since: float | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Retrieve recent audit entries."""
        limit = max(1, limit)
        with self._conn() as conn:
            if since is not None:
                rows = conn.execute(
                    """SELECT * FROM audit_log
                       WHERE timestamp >= ?
                       ORDER BY timestamp DESC
                       LIMIT ?""",
                    (since, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        entries = []
        for row in rows:
            entry = dict(row)
            if entry.get("files_affected"):
                entry["files_affected"] = json.loads(entry["files_affected"])
            entries.append(entry)

        return entries
