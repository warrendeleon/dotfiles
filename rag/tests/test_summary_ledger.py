"""Unit tests for the summary done-ledger."""

from __future__ import annotations

from pathlib import Path

from src.summary_ledger import SummaryLedger


def _ledger(tmp_path: Path) -> SummaryLedger:
    return SummaryLedger(db_path=tmp_path / "summaries.db")


def test_empty_ledger_is_not_done(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    assert led.is_done("sess", "hash1") is False


def test_record_then_done_for_same_hash(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("sess", "/x/sess.jsonl", "hash1", "/wiki/p.md", "written", "sonnet")
    assert led.is_done("sess", "hash1") is True


def test_changed_hash_is_not_done(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("sess", "/x/sess.jsonl", "hash1", "/wiki/p.md", "written", "haiku")
    # Session grew, new hash: must re-summarise.
    assert led.is_done("sess", "hash2") is False


def test_error_status_is_not_done(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("sess", "/x/sess.jsonl", "hash1", None, "error", "haiku")
    # A prior error must be retried.
    assert led.is_done("sess", "hash1") is False


def test_skipped_status_counts_as_done(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("sess", "/x/sess.jsonl", "hash1", None, "skipped", None)
    assert led.is_done("sess", "hash1") is True


def test_record_upserts(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("sess", "/x/sess.jsonl", "hash1", None, "error", "haiku")
    led.record("sess", "/x/sess.jsonl", "hash2", "/wiki/p.md", "written", "sonnet")
    row = led.get("sess")
    assert row is not None
    assert row["status"] == "written"
    assert row["file_hash"] == "hash2"
    assert row["model"] == "sonnet"
    # created_at is preserved across the upsert, updated_at moves forward.
    assert row["created_at"] <= row["updated_at"]


def test_stats(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("a", "/a", "h", "/p", "written", "haiku")
    led.record("b", "/b", "h", "/p", "written", "haiku")
    led.record("c", "/c", "h", None, "needs-review", "haiku")
    assert led.stats() == {"written": 2, "needs-review": 1}


def test_none_hash_treats_existing_as_done(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    led.record("sess", "/x/sess.jsonl", "hash1", "/wiki/p.md", "written", "haiku")
    # Unreadable file (hash None): don't loop forever re-summarising.
    assert led.is_done("sess", None) is True


def test_failures_since_counts_recent_errors_only(tmp_path: Path, monkeypatch) -> None:
    led = _ledger(tmp_path)
    led.record("old", "/x/old.jsonl", "h", None, "error", "haiku")
    led.record("ok", "/x/ok.jsonl", "h", "/w/ok.md", "written", "haiku")
    import time
    cut = time.time()
    time.sleep(0.01)
    led.record("new", "/x/new.jsonl", "h", None, "error", "haiku")
    assert led.failures_since(cut) == 1
    assert led.failures_since(0) == 2


def test_failures_since_retry_overwrites_not_accumulates(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    for _ in range(5):
        led.record("same", "/x/same.jsonl", "h", None, "error", "haiku")
    assert led.failures_since(0) == 1


def test_last_success_at(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    assert led.last_success_at() is None
    led.record("e", "/x/e.jsonl", "h", None, "error", "haiku")
    assert led.last_success_at() is None  # an error is not a success
    led.record("w", "/x/w.jsonl", "h", "/w/w.md", "written", "haiku")
    t1 = led.last_success_at()
    assert t1 is not None
    led.record("s", "/x/s.jsonl", "h", None, "skipped", "haiku")
    assert led.last_success_at() >= t1


def test_last_error_at(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    assert led.last_error_at() is None
    led.record("w", "/x/w.jsonl", "h", "/w/w.md", "written", "haiku")
    assert led.last_error_at() is None
    led.record("e", "/x/e.jsonl", "h", None, "error", "haiku")
    t = led.last_error_at()
    assert t is not None
    led.record("e", "/x/e.jsonl", "h", "/w/e.md", "written", "haiku")  # retry succeeded
    assert led.last_error_at() is None
