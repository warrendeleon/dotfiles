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

The script runs **28 steps** with a live progress widget pinned to the bottom of the terminal. Each step can be skipped individually.

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
![1Password](https://img.shields.io/badge/1Password-0094F5?style=flat-square&logo=1password&logoColor=white)
![iTerm2](https://img.shields.io/badge/iTerm2-000000?style=flat-square&logo=iterm2&logoColor=white)
![Tailscale](https://img.shields.io/badge/Tailscale-242424?style=flat-square&logo=tailscale&logoColor=white)

</div>

### Setup Steps

| # | Step | Description |
|--:|------|-------------|
| 1 | **Xcode CLI Tools** | Command-line tools + full Xcode download in background |
| 2 | **Homebrew** | Package manager for macOS |
| 3 | **Brewfile** | 65+ packages, casks, and Mac App Store apps |
| 4 | **1Password** | Password manager setup + CLI authentication |
| 5 | **Oh My Zsh + Powerlevel10k** | Shell framework, theme, and plugins |
| 6 | **Dotfiles** | Symlinks for shell, git, and SSH configs |
| 7 | **Secrets** | Licence key template (`.secrets.env`) |
| 8 | **Fonts** | MesloLGS NF + Font Awesome |
| 9 | **Node.js** | Node 24 via nvm, Corepack enabled |
| 10 | **Ruby** | Latest Ruby via rbenv |
| 11 | **npm Packages** | Claude Code, gitmoji-cli, and global tools |
| 12 | **Clone Repos** | Project repositories |
| 13 | **Android SDK** | SDK command-line tools + licence acceptance |
| 14 | **iOS Development** | Verifies CocoaPods availability (installed via rbenv gem in Step 10) |
| 15 | **SSH Key** | Pulled from 1Password CLI |
| 16 | **GitHub CLI** | Authentication + SSH protocol + editor config |
| 17 | **iTerm2** | Profile and preferences |
| 18 | **macOS Defaults** | System preferences (Dock, Finder, keyboard, etc.) |
| 19 | **Docker** | Colima (lightweight Docker runtime) + daemon startup |
| 20 | **Tailscale SSH** | Mesh VPN (App Store) + macOS Remote Login for SSH |
| 21 | **Fork** | Git client preferences |
| 22 | **WebStorm** | JetBrains IDE settings |
| 23 | **Touch ID for sudo** | Fingerprint authentication for `sudo` |
| 24 | **Firewall & FileVault** | macOS firewall + disk encryption |
| 25 | **Finder Sidebar** | Sidebar favourites configuration |
| 26 | **Login Items** | Accessibility permissions + startup apps |
| 27 | **Amphetamine** | Power Protect helper for closed-lid mode |
| 28 | **RAG System** | Local semantic search for Claude Code |

### Brewfile Highlights

| Category | Packages |
|----------|----------|
| **CLI** | git, ripgrep, wget, mas, fswatch, gnupg |
| **Languages** | nvm, bun, rbenv, python |
| **Mobile** | watchman, detox, applesimutils, ccache |
| **AI/ML** | ollama, mlx |
| **Docker** | colima, docker, kubernetes-cli |
| **Media** | ffmpeg, imagemagick, tesseract |
| **Apps** | iTerm2, Fork, WebStorm, VS Code, Android Studio |
| **Productivity** | 1Password, Rectangle, Numi, Rocket |
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
│   ├── .gitignore_global        # Global gitignore rules
│   └── .gitmessage              # Commit message template
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
├── fonts/                       # MesloLGS NF + Font Awesome
│
├── singlebox/
│   └── Settings                 # Multi-account browser workspaces
│
├── claude/
│   ├── CLAUDE.md                # Claude Code project instructions
│   └── commands/                # Global skills (audit, debug, recall, etc.)
│
└── rag/                         # Local RAG system
    ├── src/
    │   ├── server.py            # FastMCP server (5 tools)
    │   ├── store.py             # ChromaDB wrapper (3 collections)
    │   ├── queue_db.py          # SQLite job queue (retry + backoff)
    │   ├── audit.py             # Append-only audit log
    │   ├── summariser.py        # claude -p haiku with rate limiting
    │   ├── indexer.py           # Queue worker
    │   ├── watcher.py           # fswatch file monitor
    │   └── parsers/             # JSONL, code, markdown, config parsers
    ├── scripts/
    │   ├── bulk_index.py        # First-run indexer (resumable)
    │   └── health_check.py      # Diagnostics
    └── launchd/                 # Background service plists
```

---

## RAG System

<div align="center">

![ChromaDB](https://img.shields.io/badge/ChromaDB-FF6446?style=flat-square)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-7C3AED?style=flat-square)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)

</div>

A local semantic search system that gives Claude Code persistent memory across sessions. Indexes conversation history, source code, and documentation.

```
Claude Code ──► MCP Server (stdio) ──► ChromaDB + Ollama Embeddings
                     │
              ┌──────┴──────┐
              │  5 Tools     │
              │  search      │
              │  get_context │
              │  log_action  │
              │  index_file  │
              │  get_audit   │
              └──────────────┘

fswatch ──► SQLite Queue ──► Indexer ──► Summarise (haiku) ──► Embed ──► Store
```

| Component | Detail |
|-----------|--------|
| **Embeddings** | `mxbai-embed-large` via Ollama (auto-unloads after 5 min idle) |
| **Vector store** | ChromaDB with 3 collections: `conversations`, `code`, `docs` |
| **Summarisation** | `claude -p --model haiku` with sliding-window rate limiting |
| **Queue** | SQLite with retry, exponential backoff (30s, 120s, 480s), and deduplication |
| **File watching** | fswatch monitors `~/.claude/projects/` and `~/Developer/` |
| **Background** | Two launchd services: watcher + indexer |

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
| **1Password account** | SSH key retrieval via CLI |
| **Apple ID** | Mac App Store apps (Amphetamine, Xcode) |

---

## Licence

MIT
</content>
</invoke>