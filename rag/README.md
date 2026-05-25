# RAG

Local semantic search over Claude Code conversations, exposed to Claude Code itself via an MCP server. Runs entirely on the laptop. No cloud calls, no telemetry.

The point is to let Claude search past sessions for context ("we discussed X", "remember when") instead of fabricating answers. Embeddings stay on-device; the MCP server is the only thing Claude Code talks to.

## What's in the box

```
rag/
├── src/
│   ├── server.py        FastMCP server. The thing Claude Code calls.
│   ├── indexer.py       Worker loop: pulls jobs off the queue, embeds, writes to ChromaDB.
│   ├── watcher.py       fswatch wrapper. Watches ~/.claude/projects, enqueues changed JSONLs.
│   ├── store.py         ChromaDB wrapper + embedding model detection.
│   ├── queue_db.py      SQLite job queue (queue.db).
│   ├── audit.py         SQLite audit log (audit.db).
│   ├── dashboard.py     Local web dashboard for queue/audit inspection.
│   └── parsers/jsonl.py Claude Code JSONL parser (turns → embeddable chunks).
├── scripts/
│   ├── bulk_index.py    Enqueue a backlog of files (used on first install).
│   ├── sync.sh          Multi-machine sync via rsync to a hub over SSH.
│   └── health_check.py  Smoke test.
├── launchd/
│   ├── com.dotfiles.rag-indexer.plist   KeepAlive worker.
│   ├── com.dotfiles.rag-watcher.plist   KeepAlive fswatch.
│   └── com.dotfiles.rag-sync.plist      Every 5 minutes.
├── config.yaml.template Copied to ~/.rag/config.yaml on first install.
├── pyproject.toml
└── requirements.txt
```

Runtime state lives in `~/.rag/`, not in the repo:

```
~/.rag/
├── config.yaml      User-editable. Embedding model, watch paths, throttling.
├── chromadb/        Vector store.
├── queue.db         Pending and in-flight indexing jobs.
├── audit.db         Action log (log_action tool writes here).
├── sync/            rsync state + manifests for multi-machine sync.
├── logs/            stdout/stderr from the launchd jobs.
├── machine-id       Hostname tag for sync.
├── tags.txt         Topic tags accumulated across runs.
├── venv/            Python 3.13 virtualenv (chromadb won't build on 3.14+).
└── start-server.sh  Wrapper Claude Code's MCP config calls.
```

## Data flow

```
Claude Code writes a turn
        ↓
~/.claude/projects/<project>/<session>.jsonl  (changed)
        ↓
fswatch (rag-watcher launchd job)
        ↓
queue.db                                       (job enqueued)
        ↓
indexer worker (rag-indexer launchd job)
        ↓
parsers/jsonl.py                              (extract turns, chunk)
        ↓
embeddings via sentence-transformers/Ollama
        ↓
ChromaDB collection "conversations"
        ↓
search() / get_context() served back to Claude Code over MCP
```

Sync is orthogonal: `rag-sync` rsyncs `~/.claude/projects/` to a hub (currently a mini PC, reached on LAN or Tailscale). Other machines pull from the same hub and their watchers pick up the new JSONLs.

## MCP tools

Registered in `~/.claude.json` under `mcpServers.rag`, served by `src/server.py`.

| Tool | Purpose |
|---|---|
| `search(query, n_results=10)` | Semantic search across indexed conversations. |
| `get_context(topic, n_results=5)` | Lighter version of search for quick topic context. |
| `log_action(description, files_affected?)` | Append to the audit log. Claude calls this proactively after meaningful work. |
| `index_file(path)` | Manually enqueue a JSONL (debugging / one-offs). |
| `get_indexing_status()` | Queue depth + idle/working state. |
| `get_failed_jobs(limit=20)` | Jobs that errored, with stack info. |
| `get_audit_log(since?, limit=20)` | Read back what was logged. |

All seven are surfaced to Claude via the global `CLAUDE.md` so it knows when to reach for them.

## Embedding model selection

`store.py:_detect_embedding_model()` picks automatically when `embedding_model: auto` is set:

| Hardware | Model |
|---|---|
| Apple Silicon, ≥32GB RAM | `Qwen/Qwen3-Embedding-4B` via sentence-transformers + MPS |
| Apple Silicon, <32GB | `mixedbread-ai/mxbai-embed-large-v1` via sentence-transformers + MPS |
| Linux / CPU | `mixedbread-ai/mxbai-embed-large-v1` on CPU |

Override by setting `embedding_model` explicitly in `~/.rag/config.yaml`. This laptop currently overrides to `Qwen/Qwen3-Embedding-8B` on MPS to dodge an Ollama 0.21 Metal bug on M5 Max. See `~/.wiki/wiki/personal/ollama-m5-max-metal-incompatibility.md`.

## Power throttling

The indexer reads two knobs from `config.yaml`:

- `job_delay_seconds`: fixed sleep after every embed. Set to 0 on Low Power energy mode (GPU clock capped, no thermal headroom needed); raise on High Power so a 100W charger can keep up.
- `throttle_delay_seconds`: extra sleep applied reactively when AC is connected but the battery is still discharging.

The worker also pauses below 15% battery and resumes above 20%.

## Setup

`setup.sh` step 28 ("RAG System") handles everything. What it does:

1. Creates `~/.rag/`, copies `config.yaml.template` → `~/.rag/config.yaml` if missing.
2. Builds a Python 3.13 venv at `~/.rag/venv` (pinned because chromadb won't build on 3.14+).
3. `pip install -r requirements.txt` and `pip install -e .` for the rag package.
4. Auto-detects the embedding model and prefetches it (Ollama pull or HF download).
5. Installs all three launchd plists, substituting `__HOME__` with the real home path.
6. Writes `~/.rag/start-server.sh` (Claude Code MCP `cwd` is unreliable, so the wrapper does `cd` itself).
7. Registers the MCP server in `~/.claude.json`.
8. Optionally enqueues the last 30 days of conversations via `scripts/bulk_index.py`.

## Operations

Service control:

```bash
launchctl list | grep com.dotfiles.rag
launchctl unload ~/Library/LaunchAgents/com.dotfiles.rag-indexer.plist
launchctl load   ~/Library/LaunchAgents/com.dotfiles.rag-indexer.plist
```

Logs:

```bash
tail -f ~/.rag/logs/indexer.log
tail -f ~/.rag/logs/watcher.log
tail -f ~/.rag/logs/sync.log
```

Queue and DB inspection:

```bash
sqlite3 ~/.rag/queue.db 'SELECT status, COUNT(*) FROM jobs GROUP BY status;'
sqlite3 ~/.rag/audit.db 'SELECT * FROM actions ORDER BY ts DESC LIMIT 20;'
```

Dashboard:

```bash
~/.rag/venv/bin/python -m src.dashboard   # then open the printed URL
```

Manual reindex:

```bash
cd ~/Developer/dotfiles/rag
~/.rag/venv/bin/python scripts/bulk_index.py --recent-days 7
```

Smoke test:

```bash
~/.rag/venv/bin/python scripts/health_check.py
```

## Multi-machine sync

`rag-sync` runs every 5 minutes. It rsyncs `~/.claude/projects/` to one of two SSH hosts (`minipc-lan`, `minipc-tailscale`) under `claude-sync/<machine-id>/`, then pulls down every other machine's tree. The watcher on the receiving side picks up the new JSONLs and indexes them.

A foreign-files manifest at `~/.rag/sync/foreign-files.txt` tracks which JSONLs originated elsewhere so cleanup doesn't nuke local sessions.

## Why not just use a hosted vector DB

- Conversation transcripts contain unredacted secrets, half-formed thoughts, employer code. They don't leave the machine.
- Latency: search is in-process. No network.
- Cost: zero ongoing.
- The whole thing is replaceable. ChromaDB → swap for FAISS or sqlite-vec. MCP is the only interface Claude Code depends on.

## Gotchas

- chromadb fails to build on Python 3.14+. The venv pins 3.13 deliberately.
- Ollama 0.21 has a Metal shader bug on M5 Max that segfaults on embed calls. The local override uses sentence-transformers + MPS to bypass the shader path entirely. Revert to `embedding_model: auto` once Ollama fixes it.
- fswatch must be installed (`brew install fswatch`); the watcher subprocess will exit immediately otherwise.
- The MCP server is registered as a stdio server. Claude Code spawns it, so do not run a long-lived `src.server` process yourself.
- `~/.claude/projects/-Users-warrendeleon-Developer-dotfiles-rag` is excluded from both watcher and sync to avoid self-indexing loops when working in this directory.
