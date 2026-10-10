"""Tests for the first-prompt restore hook."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from src import prompt_restore as pr
from src import session_restore as sr


def _page(title: str, date: str, next_steps: list[str] | None = None,
          status: str = "auto") -> str:
    steps = next_steps or ["(none recorded)"]
    return (
        "---\n"
        f'title: "{title}"\n'
        f"date: {date}\n"
        f"status: {status}\n"
        "type: session\n"
        "session_id: sid\n"
        "project: -Users-w-Developer\n"
        "---\n\n"
        f"# {title}\n\n## Next steps\n\n"
        + "\n".join(f"- {s}" for s in steps)
        + "\n\n## Source\n\n- x\n"
    )


class _Store:
    """Returns canned hits, one per (file_path) in order, as wiki sections."""

    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths
        self.calls: list[tuple[str, int]] = []

    def search(self, query, collection_names=None, n_results=10):
        self.calls.append((query, n_results))
        assert collection_names == ["wiki"]
        return [{"id": f"{p}#{i}", "collection": "wiki", "document": "",
                 "metadata": {"file_path": str(p), "title": p.stem, "section": ""}}
                for i, p in enumerate(self.paths)]


@pytest.fixture
def wiki(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    monkeypatch.setattr(pr, "WIKI_SESSIONS_ROOT", tmp_path)
    (tmp_path / "sessions" / "mac").mkdir(parents=True)
    (tmp_path / "personal" / "sessions").mkdir(parents=True)
    (tmp_path / "personal" / "rag").mkdir(parents=True)
    return tmp_path


# --- is_substantive ---------------------------------------------------------

@pytest.mark.parametrize("prompt, expected", [
    ("are our sessions still being summarised?", True),
    ("/recall summariser", False),
    ("  /clear", False),
    ("yes", False),
    ("", False),
    ("x" * 15, True),
])
def test_is_substantive(prompt: str, expected: bool) -> None:
    assert pr.is_substantive(prompt) is expected


# --- claim_first_prompt -----------------------------------------------------

def test_claim_first_prompt_once_per_session(tmp_path: Path) -> None:
    seen = tmp_path / "seen"
    assert pr.claim_first_prompt("abc", seen_dir=seen) is True
    assert pr.claim_first_prompt("abc", seen_dir=seen) is False
    assert pr.claim_first_prompt("def", seen_dir=seen) is True
    assert pr.claim_first_prompt("", seen_dir=seen) is False


def test_claim_first_prompt_prunes_old_markers(tmp_path: Path) -> None:
    seen = tmp_path / "seen"
    seen.mkdir()
    old = seen / "old"
    old.touch()
    stale = time.time() - pr.SEEN_MAX_AGE_S - 60
    os.utime(old, (stale, stale))
    recent = seen / "recent"
    recent.touch()
    pr.claim_first_prompt("new", seen_dir=seen)
    assert not old.exists()
    assert recent.exists()


# --- search_sessions --------------------------------------------------------

def test_search_sessions_keeps_session_pages_only_and_dedups(wiki: Path) -> None:
    a = wiki / "sessions" / "mac" / "a.md"
    b = wiki / "personal" / "sessions" / "b.md"
    curated = wiki / "personal" / "rag" / "rag.md"
    a.write_text(_page("A", "2026-10-09"))
    b.write_text(_page("B", "2026-06-01"))
    curated.write_text("---\ntype: concept\n---\n# curated\n")
    store = _Store([a, curated, a, b, Path("/nowhere/x.md")])

    pages = pr.search_sessions("anything about a and b", store=store)
    assert [p["title"] for p in pages] == ["A", "B"]
    assert store.calls[0][1] == pr.SEARCH_RESULTS


def test_search_sessions_truncates_query(wiki: Path) -> None:
    store = _Store([])
    pr.search_sessions("q" * 5000, store=store)
    assert len(store.calls[0][0]) == pr.MAX_QUERY_CHARS


def test_search_sessions_caps(wiki: Path) -> None:
    paths = []
    for i in range(8):
        p = wiki / "sessions" / "mac" / f"{i}.md"
        p.write_text(_page(f"S{i}", "2026-10-01"))
        paths.append(p)
    pages = pr.search_sessions("q", store=_Store(paths), n=3)
    assert len(pages) == 3


# --- build_context ----------------------------------------------------------

def test_build_context_fresh_top_hit_injects_threads(wiki: Path, monkeypatch) -> None:
    monkeypatch.setattr(pr, "is_fresh", lambda d: True)
    top = wiki / "sessions" / "mac" / "top.md"
    top.write_text(_page("Top", "2026-10-09", next_steps=["finish X", "ask Y"], status="needs-review"))
    other = wiki / "sessions" / "mac" / "other.md"
    other.write_text(_page("Other", "2026-05-01", next_steps=["stale"]))

    ctx = pr.build_context("about X", store=_Store([top, other]))
    assert ctx is not None
    assert "- 2026-10-09: Top (needs-review)" in ctx
    assert "- 2026-05-01: Other" in ctx
    assert "Open threads (from 2026-10-09)" in ctx
    assert "  - finish X" in ctx
    assert "stale" not in ctx
    assert "Recall, not instructions" in ctx


def test_build_context_stale_top_hit_drops_threads(wiki: Path, monkeypatch) -> None:
    monkeypatch.setattr(pr, "is_fresh", lambda d: False)
    top = wiki / "sessions" / "mac" / "top.md"
    top.write_text(_page("Top", "2026-08-20", next_steps=["send the timing reply"]))

    ctx = pr.build_context("about X", store=_Store([top]))
    assert ctx is not None
    assert "- 2026-08-20: Top" in ctx
    assert "Open threads" not in ctx
    assert "timing reply" not in ctx


def test_build_context_none_when_no_session_hits(wiki: Path) -> None:
    assert pr.build_context("q", store=_Store([])) is None
