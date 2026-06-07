"""Tests for the FTS5 keyword index and reciprocal-rank fusion."""

from __future__ import annotations

from pathlib import Path

from src import fts


def _idx(tmp_path: Path) -> fts.FtsIndex:
    return fts.FtsIndex(db_path=tmp_path / "fts.db")


# --- _fts_query -------------------------------------------------------------

def test_fts_query_tokenises_and_ors() -> None:
    assert fts._fts_query("SEC-E7 cert") == '"sec" OR "e7" OR "cert"'


def test_fts_query_empty_for_punctuation() -> None:
    assert fts._fts_query("!!! ??? ---") == ""


# --- rrf_fuse ---------------------------------------------------------------

def test_rrf_fuse_ranks_docs_in_both_lists_highest() -> None:
    vector = [{"id": "a", "distance": 0.1}, {"id": "b", "distance": 0.2}]
    keyword = [{"id": "b", "bm25": -1.0}, {"id": "c", "bm25": -0.5}]
    out = fts.rrf_fuse(vector, keyword, n_results=3)
    ids = [r["id"] for r in out]
    assert ids[0] == "b"            # appears in both -> highest fused score
    assert set(ids) == {"a", "b", "c"}
    b = next(r for r in out if r["id"] == "b")
    assert b["distance"] == 0.2     # vector dict preferred (carries distance)
    assert "rrf_score" in b


def test_rrf_fuse_caps_at_n() -> None:
    vector = [{"id": str(i)} for i in range(10)]
    assert len(fts.rrf_fuse(vector, [], n_results=3)) == 3


def test_rrf_fuse_skips_idless() -> None:
    out = fts.rrf_fuse([{"no_id": 1}], [{"id": "a"}], n_results=5)
    assert [r["id"] for r in out] == ["a"]


# --- FtsIndex ---------------------------------------------------------------

def test_fts_upsert_and_search(tmp_path: Path) -> None:
    idx = _idx(tmp_path)
    idx.upsert_many([
        ("a", "conversations", "module federation re.pack setup", {"session_id": "s1"}),
        ("b", "wiki", "gluestack v2 migration playbook", {"title": "G"}),
    ])
    res = idx.search("module federation")
    assert res and res[0]["id"] == "a"
    assert res[0]["metadata"]["session_id"] == "s1"
    assert res[0]["collection"] == "conversations"


def test_fts_finds_exact_identifier(tmp_path: Path) -> None:
    idx = _idx(tmp_path)
    idx.upsert_many([
        ("a", "conversations", "fixed the SEC-E7 cert pinning story", {}),
        ("b", "conversations", "something about gardening", {}),
    ])
    assert [r["id"] for r in idx.search("SEC-E7")] == ["a"]


def test_fts_collection_filter(tmp_path: Path) -> None:
    idx = _idx(tmp_path)
    idx.upsert_many([
        ("a", "conversations", "caching bug fix", {}),
        ("b", "wiki", "caching strategy notes", {}),
    ])
    assert [r["id"] for r in idx.search("caching", collections=["wiki"])] == ["b"]


def test_fts_upsert_replaces_not_duplicates(tmp_path: Path) -> None:
    idx = _idx(tmp_path)
    idx.upsert_many([("a", "conversations", "old text apple", {})])
    idx.upsert_many([("a", "conversations", "new text banana", {})])
    assert idx.count() == 1
    assert idx.search("banana")
    assert not idx.search("apple")


def test_fts_clear(tmp_path: Path) -> None:
    idx = _idx(tmp_path)
    idx.upsert_many([("a", "conversations", "hello world", {})])
    idx.clear()
    assert idx.count() == 0


def test_fts_empty_query_returns_nothing(tmp_path: Path) -> None:
    idx = _idx(tmp_path)
    idx.upsert_many([("a", "conversations", "content here", {})])
    assert idx.search("!!!") == []
