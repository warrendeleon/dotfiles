<div align="center">

# ~/.dotfiles

**One script. Fresh Mac to fully configured dev machine.**

![macOS](https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Shell Script](https://img.shields.io/badge/Shell-121011?style=for-the-badge&logo=gnubash&logoColor=white)
![React Native](https://img.shields.io/badge/React_Native-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
![GitHub last commit](https://img.shields.io/github/last-commit/warrendeleon/dotfiles?style=flat-square)

</div>

---

## Quick Start

```bash
git clone https://github.com/warrendeleon/dotfiles.git ~/Developer/dotfiles
cd ~/Developer/dotfiles
./setup.sh
```

The script runs **30 steps** with a live progress widget pinned to the bottom of the terminal. Each step can be skipped individually.

## What's Inside

<div align="center">

![Homebrew](https://img.shields.io/badge/Homebrew-FBB040?style=flat-square&logo=homebrew&logoColor=black)
![Zsh](https://img.shields.io/badge/Zsh-F15A24?style=flat-square&logo=zsh&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-5FA04E?style=flat-square&logo=nodedotjs&logoColor=white)
![Ruby](https://img.shields.io/badge/Ruby-CC342D?style=flat-square&logo=ruby&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)
![Git](https://img.shields.io/badge/Git-F05033?style=flat-square&logo=git&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white)
![Android](https://img.shields.io/badge/Android-34A853?style=flat-square&logo=android&logoColor=white)
![Xcode](https://img.shields.io/badge/Xcode-147EFB?style=flat-square&logo=xcode&logoColor=white)
![Bitwarden](https://img.shields.io/badge/Bitwarden-175DDC?style=flat-square&logo=bitwarden&logoColor=white)
![1Password](https://img.shields.io/badge/1Password-0094F5?style=flat-square&logo=1password&logoColor=white)
![iTerm2](https://img.shields.io/badge/iTerm2-000000?style=flat-square&logo=iterm2&logoColor=white)
![Tailscale](https://img.shields.io/badge/Tailscale-242424?style=flat-square&logo=tailscale&logoColor=white)

</div>

### Setup Steps

| # | Step | Description |
|--:|------|-------------|
| 1 | **Xcode CLI Tools** | Command-line tools; full Xcode installed interactively via `xcodes` (Step 3, prompts for Apple ID) |
| 2 | **Homebrew** | Package manager for macOS |
| 3 | **Brewfile** | Packages, casks, and Mac App Store apps |
| 4 | **Password Manager** | Bitwarden + 1Password (legacy) setup and CLI authentication |
| 5 | **Oh My Zsh + Powerlevel10k** | Shell framework, theme, and plugins |
| 6 | **Dotfiles** | Symlinks for shell, git, and SSH configs |
| 7 | **Secrets** | Licence key template (`.secrets.env`) |
| 8 | **Fonts** | MesloLGS NF, JetBrains Mono + Font Awesome |
| 9 | **Node.js** | Node 24 via nvm, Corepack enabled |
| 10 | **Ruby** | Latest Ruby via rbenv |
| 11 | **npm Packages** | Claude Code, gitmoji-cli, and global tools |
| 12 | **SSH Key** | Restores private key from `secrets/id_rsa` or iCloud Drive (`iCloud Drive/ssh/id_rsa`), adds to `ssh-agent` with `--apple-use-keychain` so the passphrase lives in the login keychain. Runs before clones so SSH auth works first pass. See `CLAUDE.md` for the full mechanism. |
| 13 | **Clone Repos** | Project repositories |
| 14 | **Android SDK** | SDK command-line tools + licence acceptance |
| 15 | **iOS Development** | Verifies CocoaPods availability (installed via rbenv gem in Step 10) |
| 16 | **GitHub CLI** | Authentication + SSH protocol + editor config |
| 17 | **iTerm2** | Profile and preferences |
| 18 | **macOS Defaults** | System preferences (Dock, Finder, keyboard, etc.) |
| 19 | **Docker** | Colima (lightweight Docker runtime) + daemon startup |
| 20 | **Tailscale SSH** | Mesh VPN (App Store) + macOS Remote Login + iMessage sync registration |
| 21 | **Fork** | Git client preferences |
| 22 | **WebStorm** | JetBrains IDE settings |
| 23 | **Touch ID for sudo** | Fingerprint authentication for `sudo` |
| 24 | **Firewall & FileVault** | macOS firewall + disk encryption |
| 25 | **Finder Sidebar** | Sidebar favourites configuration |
| 26 | **Login Items** | Accessibility permissions + startup apps |
| 27 | **Amphetamine** | Power Protect helper for closed-lid mode |
| 28 | **RAG System** | Local semantic search for Claude Code |
| 29 | **LLM Wiki** | AI-maintained markdown knowledge base (clones `~/.wiki` + sync timer) |
| 30 | **NAS Auto-mount** | Synology SMB auto-mount on login + network change (LAN first, Tailscale fallback) |

### Brewfile Highlights

| Category | Packages |
|----------|----------|
| **CLI** | git, ripgrep, wget, mas, jq, tree, bat, eza, fd, fzf, tlrc, htop, trash, zoxide, git-delta, ncdu, lazygit, fswatch, gnupg |
| **Languages** | nvm, bun, rbenv, python |
| **Mobile** | watchman, detox, applesimutils, ccache |
| **AI/ML** | ollama, mlx |
| **Docker** | colima, docker, kubernetes-cli |
| **Apps** | iTerm2, Fork, WebStorm, VS Code, Android Studio |
| **Productivity** | Bitwarden, 1Password, Raycast, Rocket, Notion |
| **Communication** | Slack, Teams, Zoom, Mattermost |

---

## Directory Structure

```
dotfiles/
├── setup.sh                     # Main setup script (28 steps + progress widget)
├── Brewfile                     # Homebrew packages, casks, and MAS apps
│
├── shell/
│   ├── .zshrc                   # Zsh configuration
│   ├── .zprofile                # Login shell profile
│   ├── .p10k.zsh                # Powerlevel10k theme
│   └── .secrets.env.template    # Licence keys template
│
├── git/
│   ├── .gitconfig               # Git configuration + aliases
│   └── .gitignore_global        # Global gitignore rules
│
├── ssh/
│   └── config                   # SSH client configuration
│
├── iterm2/
│   └── Default.json             # iTerm2 profile
│
├── macos/
│   └── defaults.sh              # macOS system preferences
│
├── fonts/                       # MesloLGS NF, JetBrains Mono + Font Awesome
│
├── vscode/
│   ├── settings.json            # VS Code editor settings
│   └── extensions.txt           # VS Code extensions list
│
├── webstorm/
│   ├── editor-font.xml          # JetBrains Mono 13pt with ligatures
│   ├── console-font.xml         # MesloLGS NF 13pt for terminal
│   └── Raycast Compatible.xml   # Keymap (removes Ctrl+Option+Arrow conflicts)
│
├── singlebox/
│   └── Settings                 # Multi-account browser workspaces
│
├── .editorconfig                # Editor defaults (indent, charset, newlines)
│
├── claude/
│   ├── CLAUDE.md                # Global Claude Code instructions
│   ├── commands/                # Global skills (audit, debug, recall, voice-review, etc.)
│   ├── output-styles/           # Per-person voice profiles (warren.md = Warren's; copy & rename for your own)
│   └── docs/                    # Shell reference, knowledge-system explainer, output-style guide
│
└── rag/                         # Local RAG system (see rag/README.md)
    ├── src/
    │   ├── server.py            # FastMCP server (7 tools)
    │   ├── store.py             # ChromaDB wrapper (conversations collection)
    │   ├── queue_db.py          # SQLite job queue (retry + backoff)
    │   ├── audit.py             # Append-only audit log
    │   ├── indexer.py           # Queue worker
    │   ├── watcher.py           # fswatch file monitor
    │   ├── dashboard.py         # Local web dashboard
    │   └── parsers/jsonl.py     # Claude Code JSONL parser
    ├── scripts/
    │   ├── bulk_index.py        # First-run indexer (resumable)
    │   ├── sync.sh              # Multi-machine rsync (optional, personal)
    │   └── health_check.py      # Diagnostics
    └── launchd/                 # Background service plists (indexer, watcher, sync)
```

---

## RAG System

<div align="center">

![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6446?style=flat-square)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-7C3AED?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)

</div>

A local semantic search system that gives Claude Code persistent memory across sessions. Indexes Claude Code conversation history (the JSONLs under `~/.claude/projects/`) and serves it back via MCP.

Full architecture in [`rag/README.md`](rag/README.md). Companion explainer on RAG vs the wiki in [`claude/docs/knowledge-system.md`](claude/docs/knowledge-system.md).

```
Claude Code ──► MCP Server (stdio) ──► ChromaDB + local embeddings
                     │
              ┌──────┴────────────────┐
              │  7 Tools              │
              │  search               │
              │  get_context          │
              │  log_action           │
              │  index_file           │
              │  get_indexing_status  │
              │  get_failed_jobs      │
              │  get_audit_log        │
              └───────────────────────┘

fswatch ──► SQLite Queue ──► Indexer ──► Embed ──► ChromaDB
```

| Component | Detail |
|-----------|--------|
| **Embeddings** | Auto-detects: `Qwen/Qwen3-Embedding-4B` (Apple Silicon ≥32GB), `mxbai-embed-large-v1` otherwise. Runs via sentence-transformers + MPS. |
| **Vector store** | ChromaDB, single `conversations` collection. |
| **Queue** | SQLite with retry, exponential backoff, deduplication. |
| **File watching** | fswatch monitors `~/.claude/projects/`. |
| **Background** | Three launchd services: watcher, indexer, and (optional) multi-machine sync. |

Installed automatically as Step 28 of `setup.sh`. Runtime data lives in `~/.rag/`.

---

## Security

Sensitive data is **never committed**. The `.gitignore` blocks:

- `.secrets.env` and `.env*` files
- SSH private keys (`id_rsa*`, `id_ed25519*`, `*.pem`, `*.key`)
- OS metadata (`.DS_Store`)

On a fresh machine, `setup.sh` copies `.secrets.env.template` to `~/.secrets.env` and prompts you to fill in licence keys. The shell sources it on startup.

---

## Prerequisites

| Requirement | Why |
|-------------|-----|
| **macOS** (Sequoia or later) | Shell scripts + macOS defaults |
| **Internet connection** | Homebrew, npm, Ollama model downloads |
| **Bitwarden account** | Password manager |
| **1Password account** | SSH key retrieval via CLI (legacy) |
| **Apple ID** | Mac App Store apps (Amphetamine, Gifski, Xcode) |

---

## Licence

MIT
</content>
</invoke>