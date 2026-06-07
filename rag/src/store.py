"""ChromaDB wrapper with typed collections and local embeddings."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import chromadb
import yaml
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

logger = logging.getLogger(__name__)

COLLECTIONS = ("conversations", "wiki")
DEFAULT_DB_PATH = Path.home() / ".rag" / "chromadb"
DEFAULT_CONFIG_PATH = Path.home() / ".rag" / "config.yaml"
DEFAULT_OLLAMA_MODEL = "mxbai-embed-large"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_KEEP_ALIVE = "5m"


def _detect_embedding_model() -> str:
    """Pick the best embedding model based on system specs.

    Returns a HuggingFace model path (contains '/') for sentence-transformers,
    or a bare Ollama model name otherwise.

    Apple Silicon (unified GPU memory = RAM):
      32GB+: Qwen/Qwen3-Embedding-4B  (sentence-transformers + MPS)
      <32GB: mixedbread-ai/mxbai-embed-large-v1  (sentence-transformers + MPS)
    Linux/CPU-only:
      mixedbread-ai/mxbai-embed-large-v1  (sentence-transformers on CPU)
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
        return "Qwen/Qwen3-Embedding-4B"

    return "mixedbread-ai/mxbai-embed-large-v1"


def _load_config() -> dict:
    """Read ~/.rag/config.yaml, returning an empty dict on failure."""
    try:
        if DEFAULT_CONFIG_PATH.exists():
            with open(DEFAULT_CONFIG_PATH) as f:
                return yaml.safe_load(f) or {}
    except Exception:
        logger.debug("Failed to read config")
    return {}


def _load_embedding_model() -> str:
    """Read embedding_model from config.yaml, or auto-detect from machine specs."""
    config = _load_config()
    model = config.get("embedding_model")
    if model and model != "auto":
        return str(model)

    model = _detect_embedding_model()
    logger.info("Auto-detected embedding model: %s (based on system RAM)", model)
    return model


def _load_embedding_device() -> str | None:
    """Read embedding_device from config.yaml (cpu, mps, cuda, or auto-detect)."""
    config = _load_config()
    device = config.get("embedding_device")
    if device and device != "auto":
        return str(device)
    return None


class SentenceTransformersEmbeddingFunction(EmbeddingFunction[Documents]):
    """Embed text via a local sentence-transformers model.

    Auto-selects MPS (Apple Silicon), CUDA (NVIDIA), or CPU. Model is
    lazy-loaded on first call so startup stays fast.
    """

    def __init__(self, model: str | None = None, device: str | None = None) -> None:
        self.model_name = model or _load_embedding_model()

        if device is None:
            import torch
            if torch.backends.mps.is_available():
                device = "mps"
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(
                "Loading sentence-transformers model: %s (device=%s)",
                self.model_name, self.device,
            )
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                trust_remote_code=True,
            )

    def unload(self) -> None:
        """Release model weights from memory. Reloads lazily on next embed call."""
        if self._model is None:
            return
        import gc
        import torch
        del self._model
        self._model = None
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        logger.info("Unloaded embedding model %s", self.model_name)

    def __call__(self, input: Documents) -> Embeddings:
        import torch

        self._ensure_loaded()
        assert self._model is not None
        with torch.no_grad():
            embeddings = self._model.encode(
                list(input),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        result = embeddings.tolist()
        del embeddings
        # MUST call empty_cache() per batch on MPS. Without it the Metal
        # allocator pool grows unbounded across batches — observed 123 GB
        # graphics footprint in <1h on Qwen3-Embedding-8B. The sync cost is
        # real but tolerable; the leak is not.
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        return result


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
    """Thin wrapper around ChromaDB with typed collections."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        embedding_fn: EmbeddingFunction | None = None,
    ) -> None:
        db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        db_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        db_path.chmod(0o700)

        self._db_path = db_path
        self._client = chromadb.PersistentClient(
            path=str(db_path),
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        if embedding_fn is None:
            model_name = _load_embedding_model()
            # HuggingFace paths (e.g. "Qwen/Qwen3-Embedding-4B") use
            # sentence-transformers. Bare names (e.g. "mxbai-embed-large")
            # fall back to the legacy Ollama backend.
            if "/" in model_name:
                device = _load_embedding_device()
                embedding_fn = SentenceTransformersEmbeddingFunction(model=model_name, device=device)
            else:
                embedding_fn = OllamaEmbeddingFunction(model=model_name)
        self._embed_fn = embedding_fn
        self._collections: dict[str, chromadb.Collection] = {}

        for name in COLLECTIONS:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )

    def _ensure_client(self) -> None:
        """Rebuild the ChromaDB client and collections if they were unloaded."""
        if self._client is not None:
            return
        self._client = chromadb.PersistentClient(
            path=str(self._db_path),
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        for name in COLLECTIONS:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
        logger.info("ChromaDB client reloaded")

    def reset_client(self) -> None:
        """Drop and rebuild the ChromaDB client to flush cached HNSW indexes."""
        import gc

        old_client = self._client
        old_collections = dict(self._collections)

        try:
            new_client = chromadb.PersistentClient(
                path=str(self._db_path),
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            new_collections: dict[str, chromadb.Collection] = {}
            for name in COLLECTIONS:
                new_collections[name] = new_client.get_or_create_collection(
                    name=name,
                    embedding_function=self._embed_fn,
                    metadata={"hnsw:space": "cosine"},
                )
        except Exception:
            logger.exception("Failed to create new ChromaDB client, keeping old one")
            return

        self._client = new_client
        self._collections = new_collections
        del old_client
        old_collections.clear()
        gc.collect()

    def unload(self) -> None:
        """Release embedding model and ChromaDB client to free memory."""
        import gc

        if hasattr(self._embed_fn, 'unload'):
            self._embed_fn.unload()

        self._collections.clear()
        if self._client is not None:
            del self._client
            self._client = None

        gc.collect()
        logger.info("Store unloaded, memory released")

    def collection(self, name: str) -> chromadb.Collection:
        if name not in COLLECTIONS:
            raise ValueError(f"Unknown collection: {name}. Use one of {COLLECTIONS}")
        self._ensure_client()
        return self._collections[name]

    def upsert(
        self,
        collection_name: str,
        identifier: str,
        document: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Add or update a single document. Returns the document ID, or None if skipped."""
        if not document or not document.strip():
            logger.debug("Skipping empty document for %s", identifier)
            return None

        doc_id = _doc_id(collection_name, identifier)
        meta = metadata or {}
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

    def upsert_batch(
        self,
        collection_name: str,
        identifiers: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add or update multiple documents in a single embedding call."""
        if not documents:
            return

        ids = [_doc_id(collection_name, ident) for ident in identifiers]
        clean_metas = [
            {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool))}
            for meta in metadatas
        ]

        col = self.collection(collection_name)
        col.upsert(ids=ids, documents=documents, metadatas=clean_metas)

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
        self._ensure_client()

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

    def get_documents(self, ids: list[str]) -> list[dict[str, Any]]:
        """Fetch documents by their doc id, across all collections.

        Backs progressive disclosure: search returns ids and short snippets, and
        this returns the full text for the ids the caller chooses to open. Ids
        not present in any collection are silently skipped.
        """
        if not ids:
            return []
        self._ensure_client()
        found: list[dict[str, Any]] = []
        for name in COLLECTIONS:
            col = self._collections[name]
            try:
                res = col.get(ids=ids)
            except Exception:
                logger.exception("get failed on collection %s", name)
                continue
            got = res.get("ids") or []
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            for i, doc_id in enumerate(got):
                found.append({
                    "id": doc_id,
                    "collection": name,
                    "document": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                })
        return found

    def delete(self, collection_name: str, identifier: str) -> None:
        """Delete a document by its identifier."""
        doc_id = _doc_id(collection_name, identifier)
        col = self.collection(collection_name)
        col.delete(ids=[doc_id])

    def clear_collection(self, collection_name: str) -> None:
        """Drop and recreate a single collection. Used for a clean full reindex.

        Only touches the named collection, so reindexing the wiki never affects
        the conversations collection.
        """
        if collection_name not in COLLECTIONS:
            raise ValueError(f"Unknown collection: {collection_name}. Use one of {COLLECTIONS}")
        self._ensure_client()
        assert self._client is not None
        self._client.delete_collection(name=collection_name)
        self._collections[collection_name] = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def stats(self) -> dict[str, int]:
        """Return document counts per collection."""
        return {name: col.count() for name, col in self._collections.items()}
