"""Make the ``src`` package importable when running pytest from anywhere."""

import sys
from pathlib import Path

import pytest

RAG_ROOT = Path(__file__).resolve().parent.parent
if str(RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(RAG_ROOT))


class FakeEmbed:
    """Deterministic, model-free embedding so Store tests need no GPU/model.

    Vector quality is irrelevant for the retrieval-plumbing tests (fetch by id,
    keyword search, fusion); only consistent dimensions and non-zero norm matter.
    """

    def __call__(self, input):  # noqa: A002 - chromadb's parameter name
        out = []
        for text in input:
            vec = [0.1] * 8
            for j, ch in enumerate(text[:64]):
                vec[j % 8] += (ord(ch) % 16) / 16.0
            out.append(vec)
        return out

    def name(self) -> str:  # chromadb persistence hook on some versions
        return "fake-embed"


@pytest.fixture
def fake_store(tmp_path):
    """A Store backed by ChromaDB on a tmp path with the fake embedder."""
    from src.store import Store
    return Store(db_path=tmp_path / "chroma", embedding_fn=FakeEmbed())
