"""Tests for the server's display helpers (pure, no store or model)."""

from __future__ import annotations

from src import server


def test_estimate_tokens() -> None:
    assert server._estimate_tokens("x" * 40) == 10
    assert server._estimate_tokens("") == 1  # floor


def test_snippet_collapses_and_caps() -> None:
    s = server._snippet("word  \n  word " * 50, limit=20)
    assert len(s) <= 23
    assert s.endswith("...")
    assert "\n" not in s


def test_snippet_short_no_ellipsis() -> None:
    assert server._snippet("short text") == "short text"


def test_format_index_is_compact() -> None:
    results = [{
        "id": "abc123", "collection": "conversations", "distance": 0.1,
        "document": "x" * 400, "metadata": {"session_id": "s1", "project": "-Users-w-Developer"},
    }]
    out = server.format_index(results)
    assert "[1] (conversation)" in out
    assert "id: abc123" in out
    assert "~100 tokens" in out
    assert "session: s1" in out
    assert "x" * 400 not in out  # snippet only, not the full doc


def test_format_index_wiki_meta() -> None:
    results = [{
        "id": "w1", "collection": "wiki", "distance": 0.2,
        "document": "some wiki text", "metadata": {"title": "My Page", "section": "Detail"},
    }]
    out = server.format_index(results)
    assert "(wiki)" in out
    assert "page: My Page" in out
    assert "section: Detail" in out


def test_format_full_shows_document() -> None:
    results = [{
        "id": "abc", "collection": "wiki", "distance": 0.2,
        "document": "FULL DOCUMENT TEXT HERE", "metadata": {"title": "T"},
    }]
    out = server.format_full(results, with_relevance=True)
    assert "FULL DOCUMENT TEXT HERE" in out
    assert "page: T" in out
    assert "relevance:" in out


def test_format_index_keyword_only_shows_match_not_low() -> None:
    # A fused/keyword-only hit has no distance; it must not read "relevance: low".
    results = [{
        "id": "k1", "collection": "conversations", "rrf_score": 0.016,
        "document": "the SEC-E7 routing decisions", "metadata": {"session_id": "s9"},
    }]
    out = server.format_index(results)
    assert "match: keyword" in out
    assert "relevance:" not in out


def test_format_full_without_relevance() -> None:
    results = [{
        "id": "abc", "collection": "conversations", "distance": 1.0,
        "document": "doc", "metadata": {},
    }]
    out = server.format_full(results, with_relevance=False)
    assert "relevance:" not in out
