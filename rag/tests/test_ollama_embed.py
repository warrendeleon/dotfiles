"""Tests for the Ollama embedding function: per-item, chunk+mean-pool, retry."""
import urllib.error

import pytest

from src.store import OllamaEmbeddingFunction, _chunk_text


def test_chunk_short_is_single():
    assert _chunk_text("hello") == ["hello"]


def test_chunk_long_splits_with_overlap():
    text = "".join(chr(65 + i % 26) for i in range(4000))
    chunks = _chunk_text(text, size=1800, overlap=200)
    assert len(chunks) >= 2
    assert all(len(c) <= 1800 for c in chunks)
    # second chunk starts 1600 in (size - overlap), so it overlaps the first by 200
    assert chunks[1][:200] == text[1600:1800]


def _norm(v):
    return sum(x * x for x in v) ** 0.5


def test_single_chunk_one_call(monkeypatch):
    ef = OllamaEmbeddingFunction(model="test")
    calls = []
    monkeypatch.setattr(ef, "_embed_chunk", lambda t: calls.append(t) or [3.0, 0.0, 0.0])
    out = ef(["short text"])
    assert len(out) == 1
    assert len(calls) == 1            # one chunk -> one embed call
    assert abs(_norm(out[0]) - 1.0) < 1e-5  # normalised


def test_long_input_mean_pooled(monkeypatch):
    ef = OllamaEmbeddingFunction(model="test")
    monkeypatch.setattr(ef, "_embed_chunk", lambda t: [1.0, 0.0])  # identical per chunk
    out = ef(["y" * 4000])            # several chunks
    assert len(out) == 1
    assert abs(out[0][0] - 1.0) < 1e-5  # mean of identical vectors, normalised


def test_one_vector_per_input(monkeypatch):
    ef = OllamaEmbeddingFunction(model="test")
    monkeypatch.setattr(ef, "_embed_chunk", lambda t: [1.0, 1.0])
    assert len(ef(["a", "b", "c"])) == 3


def test_all_chunks_fail_raises(monkeypatch):
    ef = OllamaEmbeddingFunction(model="test")
    monkeypatch.setattr(ef, "_embed_chunk", lambda t: None)
    with pytest.raises(RuntimeError):
        ef(["text"])


def test_retry_then_success(monkeypatch):
    ef = OllamaEmbeddingFunction(model="test")
    calls = {"n": 0}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"embeddings":[[0.5,0.5]]}'

    def fake_urlopen(req, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError("EOF")  # runner crashed
        return FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert ef._embed_chunk("hi") == [0.5, 0.5]
    assert calls["n"] == 2  # failed once, respawned, succeeded
