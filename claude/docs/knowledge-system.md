# Knowledge system: RAG vs Wiki

These dotfiles install two complementary "memory" systems for Claude Code. They look similar from the outside (both let Claude pull in context that's not in the current conversation) but they solve different problems.

## Quick comparison

| | **RAG** (`~/.rag`) | **Wiki** (`~/.wiki`) |
|---|---|---|
| **Author** | Indexer (automatic) | AI assistant, on request |
| **Source** | Conversation JSONLs, raw transcripts | Source material the human points the AI at |
| **Storage** | ChromaDB vectors + SQLite | Plain markdown in a git repo |
| **Granularity** | Conversation turns | Structured pages, one concept per page |
| **Query path** | MCP `search()` / `get_context()` (semantic) | File reads, grep, Obsidian graph |
| **Lifetime** | Append-only history of what happened | Curated, edited, the source of truth |
| **Best for** | "We discussed X, what was the conclusion?" | "What's the canonical answer about X?" |

Think of RAG as the **journal** and the wiki as the **textbook**. The journal records everything as it happens. The textbook is rewritten when the human understands something well enough to teach it back.

## When Claude reaches for which

The global `CLAUDE.md` sets a lookup order: **Wiki → RAG → codebase**.

- **Wiki first** for questions about settled knowledge: architecture decisions, project shape, conventions, personal context the human has already documented.
- **RAG next** when the wiki has no answer and the question references the past: "remember when we", "we talked about", "like last time".
- **Codebase last** as the ground truth that overrides both. Code is what's actually deployed; memory is what someone thought was true.

A wiki page can become stale. The fix is to re-ingest a source and let the AI update the page. A RAG entry is never edited. It's a record of a moment.

---

## RAG

Full architecture lives in `rag/README.md`. The short version: a launchd-managed Python worker watches `~/.claude/projects/` for changed JSONLs, parses each conversation turn, embeds it with a local model (sentence-transformers on MPS, or Ollama), and writes to ChromaDB. A FastMCP server exposes search to Claude Code as MCP tools.

Nothing leaves the machine. Embeddings are computed locally. Vectors stay in `~/.rag/chromadb`.

What Claude calls through MCP:

```
search(query, n_results)         # semantic search across past conversations
get_context(topic, n_results)    # lighter version of search
log_action(description, files?)  # append to the audit trail
get_audit_log(since?, limit)     # read back what was logged
get_indexing_status()            # queue health
get_failed_jobs(limit)           # debugging
index_file(path)                 # manual enqueue
```

Multi-machine sync is optional and personal. See the disclaimer at the top of `rag/scripts/sync.sh`. If you only use one machine, don't install the `rag-sync` plist and the rest still works.

---

## Wiki

A git repository at `~/.wiki` containing markdown pages organised into folders by domain. The vault is browsed in Obsidian for graph view and live preview, but the canonical store is plain markdown so it's editable from anywhere.

The repo lives separately from this dotfiles repo because the content is personal and not for public consumption. Dotfiles ship the *plumbing*: the clone step, the sync launchd job, and the convention. The *content* is yours.

### Conventions

The owner's wiki uses:
- One vault, multiple top-level domains under `wiki/`. The domains don't cross-link.
- Source material is **not** committed. The AI reads sources from wherever they live on the machine and writes wiki pages from them.
- Every claim on a wiki page carries a source attribution: `[Source: path/to/file]`.
- Each page edit is a separate commit for traceability.
- A `sync.sh` runs on a launchd timer to commit, pull, rebase, and push every 10 minutes, keeping all machines in sync.

These are conventions, not requirements. The wiki repo's own `CLAUDE.md` is what teaches the AI how to write pages. Different conventions → different `CLAUDE.md`.

### Why a separate repo instead of a folder in dotfiles

- **Privacy**: dotfiles are public. The wiki contains personal notes, employer context, work-in-progress thinking.
- **Independence**: the wiki repo travels even if dotfiles change. You can rebuild the dotfiles repo from scratch without touching the knowledge.
- **Different cadence**: dotfiles change rarely. The wiki gets multiple commits a day.

---

## Bootstrapping your own wiki

If you cloned these dotfiles and don't have access to the owner's wiki repo, you need to make your own. It's a five-minute job.

### 1. Create an empty git repo

Anywhere. GitHub, GitLab, a private bare repo on your own server. The dotfiles assume SSH access.

```bash
# Example: GitHub
gh repo create yourusername/wiki --private --clone=false
```

### 2. Point the setup at it

The wiki step in `setup.sh` reads the `WIKI_REPO` environment variable. Override the default when you run setup:

```bash
WIKI_REPO=git@github.com:yourusername/wiki.git ./setup.sh
```

Or just edit `setup.sh` and change the default to your repo URL.

### 3. Seed the wiki repo

Clone it locally and add a `CLAUDE.md` that tells the AI how you want pages structured. The owner's wiki uses something like this as a starting point. Copy and adapt:

```markdown
# LLM Wiki

This is a personal knowledge base maintained by AI. The AI reads source
material, extracts key concepts, and writes structured, interlinked
markdown pages. The human decides what goes in and what questions to ask.

## Folder Structure

wiki/
  personal/    # personal knowledge
  work/        # work knowledge
  ...add domains as needed

Source material is NOT stored in this repo. It lives on disk wherever
you keep it. The AI reads sources in place and writes wiki pages from
them. Only the wiki pages are committed.

## Page conventions

Every page starts with:

# Page Title

> One-sentence summary.

Source attributions go inline: [Source: path/to/file]
One concept per page. Link related pages with [[wiki-links]].

## Workflow

When asked to ingest a source:
1. Read the source at the given path.
2. Ask which domain it belongs to if unclear.
3. Extract concepts. For each:
   - Create or update a wiki page.
   - Commit immediately: git add <file> && git commit -m "wiki: <change>"
4. Add source attributions to every claim.
5. Update the domain index page.
```

Then commit and push.

### 4. Add a sync script

If you want the wiki to sync automatically across machines (recommended if you use more than one), commit a `sync.sh` at the root of **the wiki repo** (so each clone gets it). The dotfiles setup spots `~/.wiki/sync.sh` after the clone and installs a launchd job that runs it every 10 minutes on each laptop.

The script runs **locally on each machine**. It pushes through GitHub (or whatever git remote you used). There is **no hub server, no rsync, nothing extra to host**. Each machine commits its local changes, rebases on remote, pushes. Conflicts resolve themselves because the AI is the only writer most of the time.

A minimal version:

```bash
#!/bin/bash
# Wiki sync: commit local changes, pull remote, push.
set -uo pipefail
cd "$HOME/.wiki" || exit 1
git fetch origin main --quiet 2>/dev/null

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "wiki: auto-update from $(hostname -s)" --quiet
fi

git pull --rebase origin main --quiet && git push origin main --quiet
```

Adapt the branch name and conflict handling to taste.

### 5. Install Obsidian (optional)

It's already in the Brewfile (`cask "obsidian"`). Open `~/.wiki` as a vault. The graph view and backlinks are the reason most people use Obsidian; you don't need it to maintain the wiki, but it's nice for browsing.

### 6. Re-run setup

```bash
WIKI_REPO=git@github.com:yourusername/wiki.git ~/Developer/dotfiles/setup.sh
```

The wiki step will clone your repo, install the sync launchd plist, and tell you the setup succeeded.

---

## What you can throw away

If you cloned these dotfiles and want a leaner system:

- **Skip the wiki step entirely** if you don't want a wiki at all. The RAG system works without it.
- **Skip RAG sync** if you only use one machine. The `rag-sync.plist` is optional; see the comment block at the top of `rag/scripts/sync.sh`.
- **Skip the global CLAUDE.md references to the wiki**. The lookup-order rule won't apply if there's no wiki to look in. The wiki section in `claude/CLAUDE.md` is descriptive, not enforced.

The two systems are independent. You can run RAG without a wiki, a wiki without RAG, or neither.
