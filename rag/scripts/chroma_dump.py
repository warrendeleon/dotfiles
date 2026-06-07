"""Dump a ChromaDB conversations collection to JSONL, one turn per line.

Standalone on purpose: no repo imports, so it runs on any machine that has the
rag venv (chromadb installed) without the rest of the codebase. Used to extract
indexed turns from a machine whose JSONL transcripts were deleted by Claude
Code's cleanup, so they can be rebuilt and summarised elsewhere.

Usage: python chroma_dump.py [out.jsonl] [chromadb_path]
"""
import json
import os
import sys

import chromadb


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/chroma_dump.jsonl"
    db = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/.rag/chromadb")
    client = chromadb.PersistentClient(db)
    col = client.get_collection("conversations")
    got = col.get(include=["documents", "metadatas"])
    docs = got["documents"] or []
    metas = got["metadatas"] or []
    n = 0
    with open(out, "w", encoding="utf-8") as fh:
        for doc, meta in zip(docs, metas):
            meta = meta or {}
            sid = meta.get("session_id")
            if not sid:
                continue
            fh.write(json.dumps({
                "session_id": sid,
                "turn": meta.get("turn_number", 0),
                "text": doc or "",
                "timestamp": meta.get("timestamp", ""),
                "project": meta.get("project", ""),
            }) + "\n")
            n += 1
    print(f"dumped {n} turns from {db} -> {out}")


if __name__ == "__main__":
    main()
