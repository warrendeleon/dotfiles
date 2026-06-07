#!/usr/bin/env python3
"""Index the curated wiki into the RAG `wiki` collection.

Standalone and synchronous: it does not use the conversation job queue or the
background indexer, so it never touches the conversations indexing path. Run it
on demand, or wire it into the wiki sync timer.

Each wiki page is split into section-level chunks (see parsers/markdown.py) so
semantic search returns the relevant section of a curated page, the conclusion,
not just a 500-char transcript preview.

Usage:
    python -m scripts.index_wiki                 # full clean reindex of the wiki
    python -m scripts.index_wiki --no-clear      # upsert without clearing first
    python -m scripts.index_wiki --paths a.md b.md   # index only these files (testing)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.store import Store
from src.parsers.markdown import parse_wiki_page

logger = logging.getLogger(__name__)

DEFAULT_WIKI_ROOT = Path.home() / ".wiki" / "wiki"
UPSERT_BATCH = 8  # small batch to bound GPU memory, matching the conversation indexer


def _collect_pages(wiki_root: Path, explicit: list[str] | None) -> list[Path]:
    if explicit:
        return [Path(p).resolve() for p in explicit]
    return sorted(wiki_root.rglob("*.md"))


def index_wiki(wiki_root: Path, paths: list[str] | None, clear: bool) -> tuple[int, int]:
    """Index pages into the wiki collection. Returns (pages, chunks)."""
    store = Store()

    if clear and not paths:
        logger.info("Clearing the wiki collection for a clean reindex")
        store.clear_collection("wiki")

    pages = _collect_pages(wiki_root, paths)
    logger.info("Indexing %d wiki pages from %s", len(pages), wiki_root)

    identifiers: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    page_count = 0
    chunk_count = 0

    def _flush() -> None:
        nonlocal identifiers, documents, metadatas
        if not documents:
            return
        store.upsert_batch(
            collection_name="wiki",
            identifiers=identifiers,
            documents=documents,
            metadatas=metadatas,
        )
        identifiers, documents, metadatas = [], [], []

    for page in pages:
        chunks = parse_wiki_page(page, wiki_root)
        if not chunks:
            continue
        page_count += 1
        for c in chunks:
            identifiers.append(c["identifier"])
            documents.append(c["text"])
            metadatas.append(c["metadata"])
            chunk_count += 1
            if len(documents) >= UPSERT_BATCH:
                _flush()

    _flush()
    return page_count, chunk_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Index the wiki into the RAG wiki collection")
    parser.add_argument("--wiki-root", type=str, default=str(DEFAULT_WIKI_ROOT), help="Wiki root (default ~/.wiki/wiki)")
    parser.add_argument("--paths", nargs="*", default=None, help="Index only these files (skips clearing)")
    parser.add_argument("--no-clear", action="store_true", help="Upsert without clearing the collection first")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    wiki_root = Path(args.wiki_root).expanduser().resolve()
    if not wiki_root.exists():
        logger.error("Wiki root not found: %s", wiki_root)
        sys.exit(1)

    pages, chunks = index_wiki(wiki_root, paths=args.paths, clear=not args.no_clear)
    logger.info("Indexed %d pages into %d chunks in the wiki collection", pages, chunks)


if __name__ == "__main__":
    main()
