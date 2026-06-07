"""Store retrieval tests (fetch by id), using the model-free fake embedder."""

from __future__ import annotations


def test_get_documents_fetches_by_id(fake_store) -> None:
    id1 = fake_store.upsert("conversations", "s1:turn:1", "the cache eviction bug and its fix",
                            {"session_id": "s1"})
    id2 = fake_store.upsert("wiki", "page.md#1", "wiki content about caching strategy",
                            {"title": "Caching"})

    got = fake_store.get_documents([id1, id2])
    assert {g["id"] for g in got} == {id1, id2}
    by_id = {g["id"]: g for g in got}
    assert "cache eviction" in by_id[id1]["document"]
    assert by_id[id1]["collection"] == "conversations"
    assert by_id[id2]["collection"] == "wiki"


def test_get_documents_skips_missing(fake_store) -> None:
    id1 = fake_store.upsert("conversations", "s1:turn:1", "hello world content here",
                            {"session_id": "s1"})
    got = fake_store.get_documents([id1, "does-not-exist"])
    assert [g["id"] for g in got] == [id1]


def test_get_documents_empty(fake_store) -> None:
    assert fake_store.get_documents([]) == []


def test_search_returns_ids_for_progressive_disclosure(fake_store) -> None:
    fake_store.upsert("conversations", "s1:turn:1", "react native module federation setup",
                      {"session_id": "s1"})
    fake_store.upsert("wiki", "p.md#1", "the gluestack v2 migration playbook notes",
                      {"title": "Gluestack"})
    results = fake_store.search("module federation", n_results=5)
    assert results
    # Every result carries the fields progressive disclosure needs.
    for r in results:
        assert r["id"]
        assert "document" in r
        assert r["collection"] in ("conversations", "wiki")
