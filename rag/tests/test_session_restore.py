"""Tests for the SessionStart hook: page helpers and the summariser health line."""

from __future__ import annotations

from pathlib import Path

import datetime as dt
import time

import pytest

from src import session_restore as sr


def _page(title: str, date: str, project: str, status: str = "auto",
          next_steps: list[str] | None = None, type_: str = "session") -> str:
    steps = next_steps or ["(none recorded)"]
    return (
        "---\n"
        f'title: "{title}"\n'
        "description: \"d\"\n"
        "tags:\n  - session\n"
        f"date: {date}\n"
        f"status: {status}\n"
        f"type: {type_}\n"
        "session_id: sid\n"
        f"project: {project}\n"
        "source_model: sonnet\n"
        "---\n\n"
        f"# {title}\n\n## Next steps\n\n"
        + "\n".join(f"- {s}" for s in steps)
        + "\n\n## Source\n\n- x\n"
    )


def _seed(tmp_path: Path, domain: str, name: str, content: str) -> None:
    d = tmp_path / domain / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(content, encoding="utf-8")


# --- read_page_meta ---------------------------------------------------------

def test_read_page_meta_valid(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text(_page("My session", "2026-06-07", "-Users-w-Developer"))
    meta = sr.read_page_meta(p)
    assert meta is not None
    assert meta["title"] == "My session"
    assert meta["date"] == "2026-06-07"
    assert meta["project"] == "-Users-w-Developer"


def test_read_page_meta_non_session_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text(_page("Not a session", "2026-06-07", "p", type_="convention"))
    assert sr.read_page_meta(p) is None


def test_read_page_meta_no_frontmatter_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("# Just a heading\n\nno frontmatter")
    assert sr.read_page_meta(p) is None


# --- extract_next_steps -----------------------------------------------------

def test_extract_next_steps(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text(_page("S", "2026-06-07", "p", next_steps=["do A", "do B"]))
    assert sr.extract_next_steps(p) == ["do A", "do B"]


def test_extract_next_steps_ignores_placeholder(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text(_page("S", "2026-06-07", "p"))  # default "(none recorded)"
    assert sr.extract_next_steps(p) == []


def test_extract_next_steps_stops_at_next_section(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text(
        "---\ntype: session\n---\n\n## Next steps\n\n- only this\n\n## Source\n\n- not this\n"
    )
    assert sr.extract_next_steps(p) == ["only this"]


# --- is_fresh ---------------------------------------------------------------

@pytest.mark.parametrize("date_str, expected", [
    ("2026-10-10", True),   # today
    ("2026-10-03", True),   # exactly max age
    ("2026-10-02", False),  # one day past
    ("2026-10-11", False),  # future: clock skew, not fresh
    ("not a date", False),
    ("", False),
])
def test_is_fresh(date_str: str, expected: bool) -> None:
    today = dt.date(2026, 10, 10)
    assert sr.is_fresh(date_str, today=today, max_age_days=7) is expected


# --- health_line ------------------------------------------------------------

class _Ledger:
    def __init__(self, failing: int, last_ok: float | None,
                 last_err: float | None = 1e12) -> None:
        self.failing, self.last_ok, self.last_err = failing, last_ok, last_err
        self.since_arg: float | None = None

    def failures_since(self, since: float) -> int:
        self.since_arg = since
        return self.failing

    def last_success_at(self) -> float | None:
        return self.last_ok

    def last_error_at(self) -> float | None:
        return self.last_err


def test_health_line_none_when_healthy() -> None:
    assert sr.health_line(ledger=_Ledger(0, time.time())) is None


def test_health_line_reports_failures_and_last_success() -> None:
    now = 1_800_000_000.0
    last_ok = now - 50 * 24 * 3600
    led = _Ledger(5, last_ok)
    line = sr.health_line(ledger=led, now=now, window_s=24 * 3600)
    assert line is not None
    assert "5 session(s) errored" in line
    assert dt.datetime.fromtimestamp(last_ok).strftime("%Y-%m-%d") in line
    assert "claude auth login" in line
    assert led.since_arg == now - 24 * 3600


def test_health_line_never_succeeded() -> None:
    line = sr.health_line(ledger=_Ledger(1, None), now=1.0)
    assert line is not None
    assert "last page written never" in line


def test_build_context_is_health_only(monkeypatch) -> None:
    monkeypatch.setattr(sr, "health_line", lambda: "[failing]")
    assert sr.build_context() == "[failing]"
    monkeypatch.setattr(sr, "health_line", lambda: None)
    assert sr.build_context() is None


def test_health_line_none_when_backlog_is_being_retried() -> None:
    # Errors inside the window, but a page was written after the newest error:
    # the loop recovered and is working through the retries. Not an outage.
    now = 1_800_000_000.0
    led = _Ledger(18, last_ok=now - 60, last_err=now - 3600)
    assert sr.health_line(ledger=led, now=now) is None


def test_health_line_reports_when_newest_outcome_is_error() -> None:
    now = 1_800_000_000.0
    led = _Ledger(3, last_ok=now - 3600, last_err=now - 60)
    assert sr.health_line(ledger=led, now=now) is not None
