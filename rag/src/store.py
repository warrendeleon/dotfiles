"""ChromaDB wrapper with 3 collections and Ollama embeddings."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

logger = logging.getLogger(__name__)

COLLECTIONS = ("conversations", "code", "docs")
DEFAULT_DB_PATH = Path.home() / ".rag" / "chromadb"
OLLAMA_MODEL = "mxbai-embed-large"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_KEEP_ALIVE = "5m"


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Embed text via a local Ollama instance (mxbai-embed-large)."""

    def __init__(
        self,
        model: str = OLLAMA_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        keep_alive: str = OLLAMA_KEEP_ALIVE,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.keep_alive = keep_alive

    def __call__(self, input: Documents) -> Embeddings:
        import urllib.request
        import urllib.error
        import json

        embeddings: Embeddings = []
        url = f"{self.base_url}/api/embed"

        payload = json.dumps({
            "model": self.model,
            "input": input,
            "keep_alive": self.keep_alive,
        }).encode()

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                if "embeddings" not in data:
                    raise KeyError(
                        f"Ollama response missing 'embeddings' key. "
                        f"Keys present: {list(data.keys())}"
                    )
                embeddings = data["embeddings"]
        except (urllib.error.URLError, OSError) as e:
            logger.error("Ollama embedding request failed: %s", e)
            raise
        except KeyError:
            logger.error("Unexpected Ollama response format")
            raise

        return embeddings


def _doc_id(collection_name: str, identifier: str) -> str:
    """Deterministic document ID from collection name + identifier."""
    raw = f"{collection_name}:{identifier}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class Store:
    """Thin wrapper around ChromaDB with 3 typed collections."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        embedding_fn: EmbeddingFunction | None = None,
    ) -> None:
        db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        db_path.mkdir(parents=True, exist_ok=True, mode=0o700)

        self._client = chromadb.PersistentClient(path=str(db_path))
        self._embed_fn = embedding_fn or OllamaEmbeddingFunction()
        self._collections: dict[str, chromadb.Collection] = {}

        for name in COLLECTIONS:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )

    def collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            raise ValueError(f"Unknown collection: {name}. Use one of {COLLECTIONS}")
        return self._collections[name]

    def upsert(
        self,
        collection_name: str,
        identifier: str,
        document: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Add or update a document. Returns the document ID, or None if skipped."""
        if not document or not document.strip():
            logger.debug("Skipping empty document for %s", identifier)
            return None

        doc_id = _doc_id(collection_name, identifier)
        meta = metadata or {}
        # ChromaDB metadata values must be str, int, float, or bool
        clean_meta = {
            k: v for k, v in meta.items()
            if isinstance(v, (str, int, float, bool))
        }

        col = self.collection(collection_name)
        col.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[clean_meta],
        )
        return doc_id

    def search(
        self,
        query: str,
        collection_names: list[str] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search across one or more collections. Returns merged, ranked results."""
        n_results = max(1, n_results)
        targets = collection_names or list(COLLECTIONS)
        all_results: list[dict[str, Any]] = []

        per_collection = n_results

        for name in targets:
            if name not in self._collections:
                continue

            col = self._collections[name]

            try:
                count = col.count()
                if count == 0:
                    continue

                kwargs: dict[str, Any] = {
                    "query_texts": [query],
                    "n_results": min(per_collection, count),
                }
                if where:
                    kwargs["where"] = where

                results = col.query(**kwargs)
            except Exception:
                logger.exception("Search failed on collection %s", name)
                continue

            if not results or not results["ids"] or not results["ids"][0]:
                continue

            ids = results["ids"][0]
            docs = results["documents"][0] if results["documents"] else [""] * len(ids)
            metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
            dists = results["distances"][0] if results["distances"] else [1.0] * len(ids)

            for i, doc_id in enumerate(ids):
                all_results.append({
                    "id": doc_id,
                    "collection": name,
                    "document": docs[i],
                    "metadata": metas[i],
                    "distance": dists[i],
                })

        # Sort by distance (lower = better for cosine)
        all_results.sort(key=lambda r: r["distance"])
        return all_results[:n_results]

    def delete(self, collection_name: str, identifier: str) -> None:
        """Delete a document by its identifier."""
        doc_id = _doc_id(collection_name, identifier)
        col = self.collection(collection_name)
        col.delete(ids=[doc_id])

    def stats(self) -> dict[str, int]:
        """Return document counts per collection."""
        return {name: col.count() for name, col in self._collections.items()}
