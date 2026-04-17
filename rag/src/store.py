"""ChromaDB wrapper with 3 collections and Ollama embeddings."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import chromadb
import yaml
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

logger = logging.getLogger(__name__)

COLLECTIONS = ("conversations", "code", "docs")
DEFAULT_DB_PATH = Path.home() / ".rag" / "chromadb"
DEFAULT_CONFIG_PATH = Path.home() / ".rag" / "config.yaml"
DEFAULT_OLLAMA_MODEL = "mxbai-embed-large"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_KEEP_ALIVE = "5m"


def _detect_embedding_model() -> str:
    """Pick the best embedding model based on system specs.

    Apple Silicon (unified GPU memory = RAM):
      32GB+: qwen3-embedding:8b
      <32GB: mxbai-embed-large
    Linux/CPU-only:
      Always mxbai-embed-large (8B is too slow without GPU)
    """
    import platform
    import subprocess

    is_apple_silicon = False
    ram_gb = 0

    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                ram_gb = int(result.stdout.strip()) / (1024 ** 3)
            chip = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5,
            )
            if chip.returncode == 0 and "Apple" in chip.stdout:
                is_apple_silicon = True
        except Exception:
            pass
    else:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        ram_gb = int(line.split()[1]) / (1024 ** 2)
                        break
        except Exception:
            pass

    if is_apple_silicon and ram_gb >= 32:
        return "qwen3-embedding:8b"

    return "mxbai-embed-large"


def _load_embedding_model() -> str:
    """Read embedding_model from config.yaml, or auto-detect from machine specs."""
    try:
        if DEFAULT_CONFIG_PATH.exists():
            with open(DEFAULT_CONFIG_PATH) as f:
                config = yaml.safe_load(f) or {}
            model = config.get("embedding_model")
            if model and model != "auto":
                return str(model)
    except Exception:
        logger.debug("Failed to read config")

    model = _detect_embedding_model()
    logger.info("Auto-detected embedding model: %s (based on system RAM)", model)
    return model


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Embed text via a local Ollama instance."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str = OLLAMA_BASE_URL,
        keep_alive: str = OLLAMA_KEEP_ALIVE,
    ) -> None:
        model = model or _load_embedding_model()
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
