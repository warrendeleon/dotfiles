# Ollama Embedder Migration Plan

> Move RAG embedding from the in-process fp16 `Qwen3-Embedding-8B` (sentence-transformers on MPS) to Ollama's quantised `qwen3-embedding:8b`, add chunking, and re-embed. Goal: get the 16GB model out of the Python process while keeping retrieval quality acceptable. Drafted 2026-06-07.

## Why

Two pains drove this: RAM (the embedder sits at ~16GB inside the indexer process and needed hand-rolled MPS leak fixes) and a battery drain that looked like the model being too heavy. Investigation reshaped both.

- **The battery drain was AlDente, not the model.** AlDente's Heat Protection was set to `maxTemperature 35`, an absurdly low cutoff: the battery idles at 30-33°C and barely reached 33°C even with the super cores at 90°C. When cumulative warmth crossed 35°C, AlDente throttled the charger and the battery discharged on AC. The adapter itself is healthy: it negotiates **20V x 4990mA = 100W** (a real PD charger, not a thin 3A cable). Normal embedding draws ~20W and held at 0mA on AC. The historical April drain was the *old* fp16-8B **plus** generation models at ~95W, which embed-only does not reproduce.
  - **Fix:** keep AlDente Heat Protection OFF, or set `maxTemperature` to ~45. This alone removes the discharge. Power is no longer a reason to shrink the model.
- **RAM is the remaining reason**, plus the user's preference for Ollama (a managed runtime, model out of Python, `keep_alive` unload). Ollama's quantised 8B is 4.7GB vs the fp16 16GB.

## Model choice (measured 2026-06-07)

Retrieval agreement vs the current fp16-8B (whole-turn) reference, 446 real turns + 22 queries, ranking overlap (the two models live in different vector spaces, so compare which docs each ranks, not raw vectors):

| Model | RAM | top-1 agree | overlap@5 | overlap@10 | notes |
|---|---|---|---|---|---|
| fp16-8B (current) | ~16GB | reference | 1.00 | 1.00 | in Python, MPS |
| **8B-quant + chunking** | 4.7GB | 50% | 0.62 | 0.70 | **chosen**: 0 crashes, best quality of the Ollama options |
| 8B-quant, whole-turn | 4.7GB | 50% | 0.64 | 0.70 | 1-2 long-doc crashes per run |
| 4B | 2.5GB | 36% | 0.50 | 0.47 | lighter, weaker |
| 0.6B | 0.6GB | 23% | 0.42 | 0.41 | too weak |

All Ollama models lose exact-identifier matches in the vector leg (e.g. `INC0208348`), which the **FTS5 keyword leg already covers** in the live hybrid search. Semantic queries hold. Chunking eliminated the long-doc runner crashes (496 chunks from 446 turns, 0 failures) without changing quality, because ~90% of turns are already short enough to be one chunk.

**Decision: `qwen3-embedding:8b` via Ollama, with chunking.** Best available quality, out of the Python process, reliable once chunked.

## Architecture changes

1. **EmbeddingFunction backend becomes configurable.** Keep the sentence-transformers path; add an Ollama path. Select by config (`embedding_backend: ollama | sentence-transformers`). Default to Ollama on this machine.
2. **Ollama embedding client** (`src/store.py`): POST `/api/embed` **one input per request** (Ollama's `qwen3-embedding` runner 400s/EOFs on a batched input array), with:
   - **retry + respawn**: on EOF/HTTP error, sleep ~3s and retry up to 2x (the runner respawns on the next request); count and log failures, never crash the indexer.
   - **`keep_alive`** (e.g. `"60s"`): stays loaded across an indexing burst, then unloads to free RAM (the user's unload-when-done requirement).
   - normalise vectors (Ollama does not return normalised embeddings; the current code relies on normalised).
3. **Chunking** before embedding (`src/parsers` or the indexer): split any unit over ~1800 chars into ~1800-char chunks with ~200-char overlap, on whitespace boundaries. Most turns are one chunk. Each chunk is its own vector sharing the parent's metadata plus `chunk_index`; retrieval dedups to the parent turn (max-pool / best chunk). This both removes the crash risk and sharpens long turns.

## The re-embed (the careful part)

Switching the embedder invalidates every existing vector (quantised vs fp16 are not comparable), so a full re-embed is required. **Critically, re-embed from the documents already stored in ChromaDB, NOT from source files.** The recovered deleted-session turns exist only as stored docs in Chroma; they have no source JSONL on disk. Re-reading `~/.claude/projects` would lose them.

**Merge both machines' Chroma.** The M5 Max pulled and indexed most of the Air's sessions, but not all (~48 Air-only sessions exist), and the Air's Chroma is the only copy of its own deleted history. So the re-embed source is the **union** of: the M5 Max's `conversations` collection (local) and the Air's dump (`~/.rag/merge-sources/dump_air_2026-06-07.jsonl`, 15,782 turns), **deduped by (session_id, turn_number)**. Overlapping turns are identical text; keep one. The `wiki` collection has no Air counterpart, so re-embed it from the M5 Max alone.

Backups taken first (2026-06-07, on the NAS at `home/rag-backups/`): the M5 Max's full `chromadb` (1.0GB, byte-verified) and the Air dump. Rollback is a restore.

- Iterate the merged docs (M5 `conversations` + Air dump, deduped; M5 `wiki`), chunk, re-embed each chunk with Ollama, write to a fresh collection then swap.
- **Snapshot `~/.rag/chromadb` before starting** so rollback is a restore, not another multi-hour re-embed.
- Idempotent and resumable (checkpoint by source id), in case it is interrupted.
- Rough cost: ~37k turns -> ~40k chunks at ~160ms/chunk ≈ ~1.8 hours background, on AC.
- Rebuild FTS (`store.rebuild_fts()`) afterwards so the keyword leg matches.

## Model cleanup

- Remove test residue: `nomic-embed-text`, and `qwen3-embedding:0.6b` (too weak). Keep `qwen3-embedding:8b`; keep `qwen3-embedding:4b` only as a documented fallback or remove it.
- **Do not touch `qwen2.5-coder:7b` / `qwen2.5:0.5b`** without asking, they predate this work and something else pulled them.

## Risks and rollback

- **Quality drop**: ~half the semantic top-5 shifts vs the fp16 system. Cushioned by FTS for exact terms; acceptable for the RAM win, but real. A future lever to recover quality: Qwen3 embedders take a query instruction (we use none); adding it for both docs and queries could narrow the gap.
- **Ollama runner fragility**: mitigated by chunking (no long inputs) + retry/respawn. Monitor failure counts on the first full run.
- **The in-process leak machinery becomes obsolete** once Ollama owns the model lifecycle; `store.py`'s MPS unload/cache code can be simplified, but keep it behind the sentence-transformers backend for fallback.
- **Rollback**: restore the pre-migration `~/.rag/chromadb` snapshot and flip `embedding_backend` back. No re-embed needed.

## Verification

- Quality smoke test: run several real queries through the live hybrid search, confirm relevant hits return.
- Power: with Heat Protection off, run sustained embedding on AC and confirm the battery holds at 0mA (no discharge).
- Reliability: check the re-embed's failure count is near zero.
- RAM: confirm the indexer Python process stays light (model lives in Ollama, not Python).

## Open decision before building

Re-embed in place vs into a fresh collection then swap (swap is safer for rollback but doubles disk transiently). Recommend fresh-collection-then-swap given the recovered content must not be lost.
