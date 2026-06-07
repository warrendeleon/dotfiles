"""The indexer can index a wiki page (WIKI job), reusing the one embedder."""

from __future__ import annotations

from pathlib import Path

from src.indexer import Indexer
from src.queue_db import JobQueue


def test_indexer_processes_wiki_page(fake_store, tmp_path: Path, monkeypatch) -> None:
    wiki_root = tmp_path / "wiki"
    (wiki_root / "personal" / "sessions").mkdir(parents=True)
    page = wiki_root / "personal" / "sessions" / "2026-06-07-note.md"
    page.write_text(
        "---\ntitle: Test note\ntype: session\nsession_id: abc\n---\n\n"
        "## Summary\n\nwork on the caching eviction path\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("RAG_WIKI_ROOT", str(wiki_root))

    idx = Indexer(store=fake_store, queue=JobQueue(db_path=tmp_path / "q.db"))
    idx._process_wiki_page(page)

    # The page's chunks are now in the wiki collection and the keyword index.
    assert fake_store.collection("wiki").count() >= 1
    assert fake_store._fts.search("caching")


def test_indexer_skips_wiki_page_outside_root(fake_store, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAG_WIKI_ROOT", str(tmp_path / "wiki"))
    stray = tmp_path / "elsewhere" / "note.md"
    stray.parent.mkdir(parents=True)
    stray.write_text("---\ntitle: X\n---\n\n## S\n\ntext\n", encoding="utf-8")

    idx = Indexer(store=fake_store, queue=JobQueue(db_path=tmp_path / "q.db"))
    idx._process_wiki_page(stray)  # must not raise

    assert fake_store.collection("wiki").count() == 0
