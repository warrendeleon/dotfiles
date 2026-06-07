"""SQLite FTS5 keyword index, the keyword leg of hybrid search.

Vector search recalls by meaning but misses exact strings: an identifier like
SEC-E7, an error message, a file path. This mirrors every indexed chunk into an
FTS5 table so a keyword leg can catch those, and the two legs are fused by
reciprocal-rank fusion in the Store.

Kept deliberately separate from the embedding path: writes are best-effort and
isolated, so a keyword-index failure never breaks a Chroma upsert, and if FTS5
is unavailable the whole thing disables itself and search falls back to vectors.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable

logger = logging.getLogger(__name__)

DEFAULT_FTS_PATH = Path.home() / ".rag" / "fts.db"

_TOKEN_RE = re.compile(r"\w+")


def _fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 query: OR of quoted word tokens.

    Quoting each token sidesteps FTS5 query-syntax errors on punctuation, and OR
    favours recall (bm25 ranking then sorts); the hyphen in SEC-E7 tokenises to
    SEC and E7, both of which the indexed document also carries, so it matches.
    """
    tokens = _TOKEN_RE.findall(text.lower())
    return " OR ".join(f'"{t}"' for t in tokens)


def rrf_fuse(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    n_results: int,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse two ranked lists by reciprocal-rank fusion, keyed on doc id.

    A doc's score is the sum over each list it appears in of 1 / (k + rank). The
    vector hit's dict is preferred when present (it carries the distance), so a
    fused result still renders a relevance figure.
    """
    scores: dict[str, float] = {}
    info: dict[str, dict[str, Any]] = {}
    for ranked in (vector_results, keyword_results):
        for rank, r in enumerate(ranked, 1):
            rid = r.get("id")
            if not rid:
                continue
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (k + rank)
            info.setdefault(rid, r)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    fused: list[dict[str, Any]] = []
    for rid, score in ordered[:n_results]:
        merged = dict(info[rid])
        merged["rrf_score"] = score
        fused.append(merged)
    return fused


class FtsIndex:
    """A keyword mirror of the indexed chunks. Disables itself if FTS5 is absent."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or DEFAULT_FTS_PATH)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.enabled = True
        try:
            self._init_db()
        except sqlite3.OperationalError:
            logger.warning("FTS5 unavailable; keyword search disabled, vectors only")
            self.enabled = False

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
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks "
                "USING fts5(doc_id UNINDEXED, collection UNINDEXED, document, metadata UNINDEXED)"
            )

    def upsert_many(
        self,
        rows: Iterable[tuple[str, str, str, dict[str, Any]]],
        replace: bool = True,
    ) -> None:
        """Insert (doc_id, collection, document, metadata) rows.

        FTS5 has no key upsert, so each doc_id is deleted then inserted. The
        delete scans (doc_id is unindexed), so a bulk rebuild after clear() passes
        replace=False to skip it and avoid O(n^2) over a freshly empty table.
        """
        if not self.enabled:
            return
        rows = list(rows)
        if not rows:
            return
        with self._conn() as conn:
            for doc_id, collection, document, metadata in rows:
                if replace:
                    conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
                conn.execute(
                    "INSERT INTO chunks(doc_id, collection, document, metadata) VALUES (?, ?, ?, ?)",
                    (doc_id, collection, document, json.dumps(metadata or {})),
                )

    def search(
        self,
        query: str,
        n_results: int = 10,
        collections: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Keyword hits ranked by bm25, in the Store's result shape."""
        if not self.enabled:
            return []
        match = _fts_query(query)
        if not match:
            return []
        sql = "SELECT doc_id, collection, document, metadata, rank FROM chunks WHERE chunks MATCH ?"
        params: list[Any] = [match]
        if collections:
            placeholders = ",".join("?" for _ in collections)
            sql += f" AND collection IN ({placeholders})"
            params.extend(collections)
        sql += " ORDER BY rank LIMIT ?"
        params.append(max(1, n_results))

        try:
            with self._conn() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            logger.exception("FTS query failed for %r", match)
            return []

        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
            except (ValueError, TypeError):
                meta = {}
            results.append({
                "id": row["doc_id"],
                "collection": row["collection"],
                "document": row["document"],
                "metadata": meta,
                "bm25": row["rank"],
            })
        return results

    def count(self) -> int:
        if not self.enabled:
            return 0
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def clear(self) -> None:
        if not self.enabled:
            return
        with self._conn() as conn:
            conn.execute("DELETE FROM chunks")
