"""Re-embed the corpus onto Ollama's quantised qwen3-embedding:8b, merging the
M5 Max and Air Chroma DBs.

Safeguards (the data is irreplaceable; backed up first to the NAS):
- Source is the stored Chroma DOCUMENTS, never source files (deleted sessions
  have no source JSONL).
- Merges the M5 `conversations` with the Air dump, deduped by
  (session_id, turn_number), keeping the LONGER text on a collision.
- Prints raw-vs-deduped counts before embedding.
- Embeds into NEW collections (`conversations_ollama`, `wiki_ollama`); the live
  collections are untouched until an explicit, gated `--swap`.
- Resumable: skips ids already present in the target.
- `--swap` renames old -> `*_pre_ollama`, new -> live, only after the gate checks
  pass (known recovered sessions present, session count not regressed).

Usage:
  python -m scripts.reembed_ollama                 # build + validate, no swap
  python -m scripts.reembed_ollama --limit 200     # small validation run
  python -m scripts.reembed_ollama --swap          # swap live collections (gated)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb

from src.store import OllamaEmbeddingFunction, DEFAULT_DB_PATH

OLLAMA_MODEL = "qwen3-embedding:8b"
AIR_DUMP = Path.home() / ".rag" / "merge-sources" / "dump_air_2026-06-07.jsonl"
ADD_BATCH = 64
# Known recovered sessions: must survive the migration. (session_id, expected turns)
RECOVERED_CANARIES = {
    "2fb8d63a-329a-43d0-bc48-ef86b170461b": 27,
    "594557e4-9f94-4c2a-b7e5-f59b98dd03a5": 1,
    "26d7fa5f-bc3a-4d54-b931-1aece0ae0fa2": 186,
}


def _key(sid, turn):
    return f"{sid}:{turn}"


def build_merged_conversations(client):
    """Union of the M5 conversations collection and the Air dump, deduped by
    (session_id, turn_number), keeping the longer text. Returns id->record."""
    merged: dict[str, dict] = {}

    def absorb(text, meta, source):
        sid = (meta or {}).get("session_id")
        turn = (meta or {}).get("turn_number")
        if sid is None or turn is None:
            return
        k = _key(sid, turn)
        prev = merged.get(k)
        if prev is None or len(text or "") > len(prev["document"]):
            merged[k] = {"document": text or "", "metadata": {
                "session_id": sid, "turn_number": turn,
                "timestamp": (meta or {}).get("timestamp", ""),
                "project": (meta or {}).get("project", ""),
            }}

    # M5 (local Chroma)
    col = client.get_collection("conversations")
    g = col.get(include=["documents", "metadatas"])
    m5 = len(g["documents"])
    for doc, meta in zip(g["documents"], g["metadatas"]):
        absorb(doc, meta, "m5")

    # Air (dump)
    air = 0
    if AIR_DUMP.exists():
        with open(AIR_DUMP) as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                air += 1
                absorb(r.get("text", ""), {
                    "session_id": r.get("session_id"),
                    "turn_number": r.get("turn"),
                    "timestamp": r.get("timestamp", ""),
                    "project": r.get("project", ""),
                }, "air")

    print(f"conversations: M5 {m5} + Air {air} = {m5 + air} raw -> {len(merged)} unique turns "
          f"(deduped by session_id+turn, longer text kept)")
    sids = {v["metadata"]["session_id"] for v in merged.values()}
    print(f"  distinct sessions: {len(sids)}")
    return merged


def build_wiki(client):
    col = client.get_collection("wiki")
    g = col.get(include=["documents", "metadatas"])
    out = {}
    for i, (doc, meta) in enumerate(zip(g["documents"], g["metadatas"])):
        ident = (meta or {}).get("identifier") or f"wiki:{i}"
        out[ident] = {"document": doc or "", "metadata": meta or {}}
    print(f"wiki: {len(out)} chunks")
    return out


def embed_into(client, name, records, ef, limit=0):
    """Embed records into collection `name`, skipping ids already present."""
    col = client.get_or_create_collection(
        name=name, embedding_function=ef, metadata={"hnsw:space": "cosine"})
    items = list(records.items())
    if limit:
        items = items[:limit]
    existing = set(col.get(include=[])["ids"]) if col.count() else set()
    print(f"  {name}: {len(existing)} already present; up to {len(items)} to do")

    bid, bdoc, bmeta, bemb = [], [], [], []
    stats = {"embedded": 0, "fails": 0, "skipped": 0}

    def flush():
        if bid:
            col.add(ids=bid, documents=bdoc, metadatas=bmeta, embeddings=bemb)
            stats["embedded"] += len(bid)
            bid.clear(); bdoc.clear(); bmeta.clear(); bemb.clear()

    for ident, rec in items:
        if ident in existing:
            stats["skipped"] += 1
            continue
        try:
            vec = ef([rec["document"]])[0]
        except RuntimeError:
            stats["fails"] += 1
            continue
        bid.append(ident); bdoc.append(rec["document"])
        bmeta.append(rec["metadata"]); bemb.append(vec)
        if len(bid) >= ADD_BATCH:
            flush()
            if stats["embedded"] % (ADD_BATCH * 10) == 0:
                print(f"    {name}: {stats['embedded']} embedded, {stats['fails']} failed", flush=True)
    flush()
    print(f"  {name}: DONE embedded {stats['embedded']}, failed {stats['fails']}, "
          f"skipped(existing) {stats['skipped']}, total {col.count()}")
    return col


def gate(client, new_conv_name):
    """Return True only if the new collection is safe to make live."""
    old = client.get_collection("conversations")
    new = client.get_collection(new_conv_name)
    old_sids = {m["session_id"] for m in old.get(include=["metadatas"])["metadatas"] if m.get("session_id")}
    new_sids = {m["session_id"] for m in new.get(include=["metadatas"])["metadatas"] if m.get("session_id")}
    ok = True
    print(f"\n=== gate ===")
    print(f"  sessions: old {len(old_sids)} -> new {len(new_sids)} "
          f"({'OK' if len(new_sids) >= len(old_sids) else 'REGRESSED'})")
    if len(new_sids) < len(old_sids):
        ok = False
    for sid, expected in RECOVERED_CANARIES.items():
        got = len(new.get(where={"session_id": sid}, include=[])["ids"])
        mark = "OK" if got >= expected else "MISSING"
        if got < expected:
            ok = False
        print(f"  recovered {sid[:8]}: {got}/{expected} turns  {mark}")
    print(f"  verdict: {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="embed at most N (validation)")
    ap.add_argument("--swap", action="store_true", help="rename new collections live (gated)")
    args = ap.parse_args()

    client = chromadb.PersistentClient(path=str(DEFAULT_DB_PATH),
                                       settings=chromadb.Settings(anonymized_telemetry=False))
    ef = OllamaEmbeddingFunction(model=OLLAMA_MODEL)

    if args.swap:
        if not gate(client, "conversations_ollama"):
            print("gate FAILED, not swapping.")
            sys.exit(1)
        import datetime  # noqa: not used for time, just a fixed suffix
        suffix = "pre_ollama"
        for live, built in (("conversations", "conversations_ollama"), ("wiki", "wiki_ollama")):
            client.get_collection(live).modify(name=f"{live}_{suffix}")
            client.get_collection(built).modify(name=live)
            print(f"swapped: {built} -> {live}; old kept as {live}_{suffix}")
        print("done. Live collections now Ollama-embedded. Rebuild FTS next.")
        return

    conv = build_merged_conversations(client)
    wiki = build_wiki(client)
    embed_into(client, "conversations_ollama", conv, ef, limit=args.limit)
    embed_into(client, "wiki_ollama", wiki, ef, limit=args.limit)
    if not args.limit:
        gate(client, "conversations_ollama")
    print("\nbuild complete. Review the gate, then re-run with --swap to go live.")


if __name__ == "__main__":
    main()
