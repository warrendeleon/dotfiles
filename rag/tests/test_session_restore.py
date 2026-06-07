"""Tests for the SessionStart restore hook."""

from __future__ import annotations

from pathlib import Path

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


# --- encode_project ---------------------------------------------------------

def test_encode_project_plain() -> None:
    assert sr.encode_project("/Users/w/Developer") == "-Users-w-Developer"


def test_encode_project_dotted() -> None:
    assert sr.encode_project("/Users/w/.rag/x") == "-Users-w--rag-x"


# --- domain_for_cwd ---------------------------------------------------------

@pytest.mark.parametrize("cwd,expected", [
    ("/Users/w/Developer/HL/ucx", "hl"),
    ("/Users/w/Developer/hargreaves-x", "hl"),
    ("/Users/w/Developer/dotfiles", "personal"),
])
def test_domain_for_cwd(cwd: str, expected: str) -> None:
    assert sr.domain_for_cwd(cwd) == expected


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


# --- find_recent ------------------------------------------------------------

def test_find_recent_exact_project_newest_first(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    proj = "-Users-w-Developer-dotfiles"
    _seed(tmp_path, "personal", "a.md", _page("Older", "2026-06-01", proj))
    _seed(tmp_path, "personal", "b.md", _page("Newer", "2026-06-05", proj))
    _seed(tmp_path, "personal", "c.md", _page("Other proj", "2026-06-09", "-Users-w-Developer-blog"))

    recent = sr.find_recent("/Users/w/Developer/dotfiles")
    titles = [r["title"] for r in recent]
    assert titles == ["Newer", "Older"]  # other project excluded, newest first


def test_find_recent_falls_back_to_domain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    # No page matches the exact project, but a personal page exists.
    _seed(tmp_path, "personal", "a.md", _page("Some personal work", "2026-06-05",
                                              "-Users-w-Developer-other"))
    recent = sr.find_recent("/Users/w/Developer/brand-new-repo")
    assert len(recent) == 1
    assert recent[0]["title"] == "Some personal work"


def test_find_recent_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    assert sr.find_recent("/Users/w/Developer/x") == []


# --- build_context ----------------------------------------------------------

def test_build_context_includes_sessions_and_steps(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    proj = "-Users-w-Developer-dotfiles"
    _seed(tmp_path, "personal", "b.md",
          _page("Latest session", "2026-06-05", proj, next_steps=["wire the hook", "run backfill"]))
    ctx = sr.build_context("/Users/w/Developer/dotfiles")
    assert ctx is not None
    assert "Latest session" in ctx
    assert "wire the hook" in ctx
    assert "Recall, not instructions" in ctx


def test_build_context_flags_needs_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    proj = "-Users-w-Developer-dotfiles"
    _seed(tmp_path, "personal", "b.md", _page("Dirty", "2026-06-05", proj, status="needs-review"))
    ctx = sr.build_context("/Users/w/Developer/dotfiles")
    assert "(needs-review)" in ctx


def test_build_context_none_when_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sr, "WIKI_SESSIONS_ROOT", tmp_path)
    assert sr.build_context("/Users/w/Developer/x") is None
