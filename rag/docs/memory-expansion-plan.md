# RAG Memory Expansion Plan

> Adapting the useful ideas from claude-mem into the existing local RAG, so Claude can resume work in a fresh conversation. Local-first, additive, and shaped by what already broke once.

Status: Phase 1 built (2026-06-07). Phases 2-3 remain a separate retrieval-quality project off the critical path. The as-built design is recorded in section 14; it deviates from the original Phase 1 sketch in a few places, all for correctness, and those are called out there.

## 1. The goal

One feature drives this: **resume work in a new conversation.** Today a fresh session starts cold; the fix is a loop that (a) writes a compact summary at the end of a substantial session and (b) reads the right prior summaries back in at the start of the next one. Everything else (better retrieval) is secondary.

## 2. Constraints (the real ones, learned this session)

1. **Token budget, not privacy.** Warren already runs everything through Claude, so sending transcripts to Haiku is not a new exposure. The 20x Max limit is the constraint. The old summariser blew it by summarising the *entire backlog* with a network model, not because summarising is inherently expensive.
2. **Memory budget is tight.** The embedder (Qwen3-Embedding-8B on MPS) already sits at ~15GB idle and has hit ~30GB during heavy indexing. Unified memory is not all GPU-addressable. **Do not stack a large local model on top of the embedder.** This is what made the graphify hl build thrash.
3. **Anti-feedback-loop.** If the summariser uses `claude -p`, those calls write their own transcript JSONLs into `~/.claude/projects/`, which the watcher would then index, feeding the summariser's own I/O back into the RAG. This must be designed out (or sidestepped by using local ollama, which writes no transcript).
4. **HL GitLab is the one hard line.** Anthropic seeing content and personal GitHub are both fine. Nothing tool-generated may reach HL's GitLab (not a concern for summaries, which never go there).
5. **Additive and stable.** The indexer is stable after a long bug-fixing history (see section 9). Do not destabilise it. New work is a separate layer, not a rewrite.
6. **Keep native auto-memory ON.** claude-mem disables it because it *replaces* it. We are not replacing the memory files (the behavioural core); we are adding a resume layer beside them. They hold different things and do not collide. (Verify the exact `CLAUDE_CODE_DISABLE_AUTO_MEMORY` load-vs-write behaviour before any toggle; recommendation is leave it on.)

## 3. Architecture: the layered memory model

Four layers, each with one job:

- **Memory files** (`~/.claude/projects/.../memory/`): soul and behaviour. Auto-loaded. Unchanged.
- **Wiki** (`~/.wiki`): curated long-term knowledge, plus session summaries under `sessions/`. Synced to personal GitHub.
- **RAG (ChromaDB)**: semantic search over conversations + wiki. Local embeddings.
- **NEW resume loop**: a Stop-hook summariser (writes) + a SessionStart-hook injector (reads), over the summaries.

## 4. Summariser backend decision

The summary is a small, simple, infrequent task (a five-field digest), unlike graphify's heavy nested-JSON extraction, so do not infer from the 7B's graphify failure that summarising needs a big model.

**Default: Haiku via `claude -p`.** Zero local memory footprint (decisive given the 30GB embedder), reliable at small structured output, and cheap when used sensibly. Sensible means: only substantial sessions, one call per session, truncated input, never the backlog.

**Alternative: a small local model (7-14B) via the ollama service**, gated by the Phase-0 spike. No token cost and no transcript feedback, but it competes with the embedder for memory and must be measured. Never a large local model alongside the embedder.

**Optional enrichment: in-session Opus.** When Claude is already in the conversation, it can write a higher-quality summary directly. This is enrichment, not the primary path (the hook is primary, because depending on the agent remembering has been the recurring failure).

**Producer rule: one automated producer.** The Stop hook is the single producer feeding the corpus. If an in-session summary already exists for a session, the hook detects it (a marker / frontmatter) and skips, so there are no duplicates or gaps.

## 5. Anti-feedback-loop design

- If Haiku: run the summariser's `claude -p` in a dedicated working directory whose `~/.claude/projects/` mapping is added to the watcher's exclusion list, so the summariser's own transcripts are never indexed. Belt-and-braces: the JSONL parser skips any transcript carrying a summariser sentinel.
- If local ollama: no transcript is written, so no exclusion needed (a point in its favour).
- Either way: the summary *output* is indexed deliberately (as a wiki `sessions/` page), but the intermediate generation is not.

## 6. Where summaries live

**Recommendation: `~/.wiki/wiki/<domain>/sessions/`**, the area already created this session, with frontmatter `status: auto | curated`.

- Already RAG-indexed (the `wiki` collection), so searchable for free.
- Recency-sortable by filename date, which is what SessionStart needs.
- Reuses existing infra; no new store.
- The `status` flag keeps machine-written summaries distinct from curated ones; the user promotes good ones to `curated`.

Alternative if auto-content in the wiki feels wrong: a separate local `journal` store (markdown dir + a `journal` Chroma collection). More isolation, more new infra. Not recommended given personal GitHub is acceptable.

## 7. SessionStart restore: recency + project, not semantic

At session start there is no query, so semantic search is the wrong tool. Restore is: **the last N summaries for THIS project, newest first.**

- A SessionStart hook (matcher `startup|resume|clear|compact`) runs a small script that reads the newest N `sessions/` pages for the current project (derived from cwd), and injects a **compact index** plus the latest `next_steps`.
- Discipline copied from claude-mem (the reason their injection is usable): inject pointers and one-liners, not bodies; cap hard (about 5 lines); a footer pointing to `mcp__rag__search` for detail; fail silent on any error; label it "verify before relying".
- The hook queries Chroma in-process (MCP is not available at hook time), or reads the markdown directly and sorts by date. Filter by project metadata; order by recency.

## 8. Phase plan

### Phase 0: spikes and decisions (half a day, no production code)
- **Model-capability + memory spike.** Pull a candidate local model, summarise three real transcripts, measure wall-clock and *peak memory with the embedder also loaded*. Go/no-go on local vs Haiku from data, not assumption.
- **Verify** `CLAUDE_CODE_DISABLE_AUTO_MEMORY` behaviour (load vs write). Confirm: leave on.
- **Confirm the transcript-exclusion mechanism** works (a dedicated workdir is excluded from the watcher).

### Phase 1: the resume loop (ships alone, 1-2 days)
- Local summariser module: the five-field schema (`request / investigated / learned / completed / next_steps`) + taxonomy tags (reuse claude-mem's near-verbatim), a skip rule for trivial sessions, output validation + hollow-response rejection, input truncation with an elision marker, `noTools`.
- **Stop hook**: on session end, if the session is substantial and has no fresh in-session summary, summarise (Haiku by default) and write a `status: auto` page to `wiki/<domain>/sessions/`. Background/detached so Stop returns instantly. Fail silent.
- **SessionStart hook**: inject the compact recency+project index (section 7).
- Tests: hook stdout/JSON contract for both events, summariser parse + skip + hollow paths, injection size cap, fail-silent on every error path.

### Phase 2: retrieval quality (separate project, off the critical path)
- **Progressive disclosure** (no re-embed): `search` returns a compact index (id + title + snippet + token cost); add `get_chunks(ids)` for full text; a small workflow tool that teaches "filter before fetch".
- **Field-level embedding** (needs a full re-embed): split turns into user/assistant/fact docs sharing a `source_id`, dedup on read. Improves recall.
- **Hybrid FTS5 + RRF** (net-new, claude-mem's "hybrid" is a stub): a SQLite FTS5 keyword leg fused with the vector leg by reciprocal-rank, so exact identifiers and error strings are not missed.

## 9. Re-processing the JSONL

- Resume loop (Phase 1): **no re-process.** Summaries are new artefacts written going forward.
- Progressive disclosure: **no re-embed.** Retrieval-layer change over existing vectors.
- Field-level embedding: **yes, a full re-embed** of the `conversations` collection (clear + rebuild). The only part that needs it. A multi-hour background job via the watcher; free; bundles with adding FTS.
- Optional: gradual *local* backfill of historical summaries. Never a network-model backfill of the backlog.

## 10. Lessons from the RAG bug history (design guardrails)

From the wiki postmortem and the git log, the indexer earned its stability the hard way. The expansion must not regress any of it:
- MPS cache leak (48GB) fixed with `torch.mps.empty_cache()` per batch; idle model unload (18GB retention) after 120s; ChromaDB HNSW native-cache leak handled by client refresh every 200 jobs (create-before-swap); `gc.collect()` per job; maintenance isolated from job status so a maintenance failure cannot fail a completed job.
- JSONL parser: handle null content blocks; stream raw-turn fetch rather than parsing whole files.
- Old summariser sins to design out: indiscriminate (summarised trivial runs), ran over the whole backlog, used `claude -p` whose transcripts got re-ingested, carried mini-PC cruft.

Implication: the new summariser runs **outside** the indexer process (via the ollama service or `claude -p`), so it never adds a model to the leak-prone indexer; it is gated to substantial new sessions only; and its transcripts are excluded from indexing.

## 11. Testing

- Hook contracts: SessionStart and Stop produce valid JSON; fail-silent on every error; injection within the size cap.
- Summariser: valid five-field output on real transcripts; skip on trivial; hollow-rejection; truncation correctness.
- Anti-feedback: confirm the summariser's transcripts are not indexed (search the RAG for a sentinel after a summary run; expect zero hits).
- Memory: peak RSS / MPS footprint with embedder + summariser path active stays within budget.
- Regression: the existing raw-turn indexing and search are unchanged.

## 12. Out of scope (what NOT to copy from claude-mem)

The Bun worker + Express service on port 37777, BullMQ/Redis/Postgres server-beta, teams/auth, endless mode (experimental, in-session), knowledge-agents (ships a corpus to the cloud), the file-read-gate (needs host-hook interception), smart-explore (that is graphify/understand-anything territory), export/import (single-user). And never reintroduce network-model summarisation of the backlog.

## 13. Decisions (signed off 2026-06-07)

1. **Summariser backend: Haiku** for going-forward, per-substantial-session summaries (memory-safe, zero local footprint, sensible token use). Local-small remains a spike-gated option but is not the default.
2. **Summary home: a dedicated subfolder under the wiki**, domain-split (`wiki/<domain>/sessions/`), `status: auto | curated`. Naming still to confirm: the existing `sessions/` (neutral, already built) vs a renamed `ai-sessions/` (Warren's suggestion; note it duplicates `sessions/` and trips the no-AI-reference rule).
3. **Scope: Phase 1 only**, then reassess. Phases 2-3 deferred.
4. **Backfill: yes, with Sonnet (validated 2026-06-07 by a Haiku-vs-Sonnet side-by-side).** Earlier caution was "backfill must be local"; the data overturned it. Only ~83 conversation files (~70 substantial), and the RAG parser already strips tool/result/thinking, so a "717KB" session reduces to ~700 input tokens. The whole backfill is roughly 50k input + 30k output tokens, negligible. Sonnet beat Haiku on the same session (named exact paths, the read-before-edit step, the logging tool, the audit-not-migration framing, the reboot blast radius), and since the backfill is a one-time pass producing a durable asset, optimise for quality when cost is near-zero. A separate "Sonnet only" weekly bucket sits at 0%, so it likely will not touch the "All models" line. The old blowout was per-turn, continuous, over everything, a different mechanism.
   - **The summariser model is a config setting** (the old summariser's bug was hardcoding `haiku`). Backfill: Sonnet. Going-forward: Haiku or Sonnet (both cheap at a few/day), swappable. In-session Opus stays the top-tier enrichment.
   - Guardrails for the real run: head+tail truncation for the few huge transcripts (146MB), throttle so it does not burst the 5h window, resumable/idempotent (skip already-summarised), strip ```json fences and reject hollow output, and exclude the summariser's own `claude -p` transcripts from indexing. Local ollama remains a fallback, not the default.

## 14. Phase 1 as built (2026-06-07)

Built and committed to dotfiles `main` (`eae7f9b`, local). Files: `rag/src/summariser.py`, `rag/src/summary_ledger.py`, `rag/src/summarise_sweep.py`, `rag/src/session_restore.py`, the watcher exclusion, `claude/hooks/session-end-summarise.sh`, `rag/launchd/com.dotfiles.rag-summariser.plist`, the two `claude/settings.json` hooks, and 79 tests under `rag/tests/`.

What changed from the sketch above, and why:

- **Trigger: not a Stop hook.** Stop fires after every turn, so a Stop-hook summariser would summarise mid-session, every turn, which is the indiscriminate behaviour that blew the budget before. The as-built spine is a **launchd timer** (`com.dotfiles.rag-summariser`, every 30 min, `--limit 5`, model from config) that sweeps finished sessions. A **SessionEnd hook** summarises the just-closed session at once for immediacy. **SessionStart** does the restore injection. The done-ledger dedups across all three.
- **The summariser uses `claude -p --tools ""`.** Verified empirically: removing tools drops the per-call system overhead from ~23.5k to ~6.3k tokens and is the strongest no-side-effects guarantee (the model has no tools to call at all). JSON output via `--output-format json`; fences stripped; hollow output rejected.
- **Session date comes from the last in-transcript timestamp, not mtime.** mtime drifts up to a day and sessions can span weeks; the transcript timestamp is exact, which matters because restore orders by date.
- **A linter, not a scrubber.** The model emits em-dashes and filler words whatever the prompt says, so output is linted and a violating page is marked `status: needs-review` rather than silently rewritten. Most pages flag; that is expected and they are reviewed before promotion.
- **Done-ledger** is `~/.rag/summaries.db` (queue_db pattern). Gates on mtime vs last write, so unchanged transcripts are skipped without rehashing a huge file. A non-blocking `fcntl` lock stops a manual backfill and a timer tick double-spending.
- **Domain routing** errs toward `hl`: a dedicated HL dir or HL markers in the text routes to `wiki/hl/sessions/`, keeping HL references out of `personal/` per the wiki separation rule.
- **Summary home decision:** straight to the synced wiki, `wiki/<domain>/sessions/`, both domains (Warren chose this, informed that ~29 HL summaries reach personal GitHub). `status: auto | needs-review` (the `curated` flag from section 6 is the human-promotion target). Folder name kept as `sessions/`, not `ai-sessions/` (no-AI-reference rule).
- **Backfill:** `rag-summarise --model sonnet` (no `--backfill` flag; it was redundant and risked summarising the live session, so it was removed). The wiki sync is paused during the run so nothing reaches GitHub before review.

Deferred (unchanged): Phases 2-3 (progressive disclosure, field-level embedding, FTS5+RRF). RAG-indexing of the new summary pages rides the existing wiki indexer; the restore hook reads markdown directly, so it does not depend on that.
