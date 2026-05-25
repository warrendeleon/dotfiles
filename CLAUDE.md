# dotfiles: assistant-facing overview

You're reading this because someone pointed an AI assistant at this repo and asked you to make sense of it. This file is the orientation map. Read it first; then read what you need.

## What this repo is

A single-shot Mac bootstrap. Clone, run `./setup.sh`, end up with a fully configured developer laptop. The script is idempotent; rerunning skips work that's already done. Each of the 30 steps can be skipped individually at the prompt.

The owner is a senior mobile engineer (React Native + Swift, currently on Hargreaves Lansdown's mobile platform) running macOS on Apple Silicon. The dotfiles are tuned for that workload: heavy mobile tooling, AI-augmented terminal workflow, multi-machine setup, paid productivity apps.

## Repo layout

```
dotfiles/
├── setup.sh             Main bootstrap. 30 steps, interactive picker, live progress widget.
├── bootstrap.sh         Tiny shim: clones the repo on a brand-new machine, then calls setup.sh.
├── Brewfile             Homebrew packages, casks, and Mac App Store apps.
├── CLAUDE.md            (you are here) Repo-level orientation for AI assistants.
├── README.md            Human-readable overview.
│
├── shell/               zsh, p10k, secrets template
├── git/                 .gitconfig, .gitignore_global
├── ssh/                 SSH client config
├── iterm2/              Terminal profile
├── macos/               System Preferences via `defaults write` (defaults.sh)
├── fonts/               MesloLGS NF, JetBrains Mono, Font Awesome
├── vscode/              settings.json + extensions list
├── webstorm/            JetBrains editor/console fonts + keymap
├── singlebox/           Multi-account browser workspaces
├── nas/                 Synology auto-mount script + launchd plist
│
├── claude/              Claude Code config (global, applies to every project)
│   ├── CLAUDE.md        Global instructions Claude reads at every session start
│   ├── commands/        Custom skills (audit, debug, recall, voice-review, ...)
│   ├── output-styles/   Output presets (warren.md)
│   └── docs/            Shell reference + RAG/wiki explainer
│
├── rag/                 Local semantic-search system for Claude Code
│   ├── README.md        Full architecture
│   ├── src/             Python: MCP server, indexer, watcher, store, parsers
│   ├── scripts/         bulk_index, sync (multi-machine), health_check
│   └── launchd/         Background service plists (indexer, watcher, sync)
│
└── scripts/             One-off helpers
```

Runtime state lives outside the repo:
- `~/.rag/`: vector DB, queue, logs, venv (RAG)
- `~/.wiki/`: separate git repo cloned by setup step 29 (LLM Wiki)
- `~/.claude/`: symlinks into `claude/` here; the rest is Claude Code's own state

## The pieces worth understanding

Most of this repo is plumbing. Four pieces carry real architectural weight:

### 1. `setup.sh`: the bootstrap

A ~2,000-line bash script with a top-of-file step list (`STEP_NAMES` array, line ~58). Each step is gated by an `ask` prompt, can be skipped, and is idempotent. The first half is straightforward (Brew, fonts, languages); the back half configures system preferences (`macos/defaults.sh`), background services (launchd), and the knowledge system. Read `STEP_NAMES` first to see the order.

Two installer-style patterns to recognise:
- **Symlinks** for live-edited configs (`shell/.zshrc`, `git/.gitconfig`, `claude/CLAUDE.md`, etc.) so edits flow back to the repo.
- **`defaults import`** for app preference plists (Fork, Singlebox) so settings restore on a fresh machine.

### 2. `claude/`: the AI workflow

The dotfiles assume Claude Code is the primary AI tool. Three artefacts:
- `claude/CLAUDE.md`: global instructions Claude reads every session. Tone, voice, banned phrases, RAG/wiki lookup order, security/testing principles. Long but well-organised.
- `claude/settings.json`: Claude Code's global config. Symlinked to `~/.claude/settings.json` by setup. Carries the Stop hook (osascript notification), `outputStyle: "Warren"`, `effortLevel: "high"`, `advisorModel: "opus"`, voice config, and enabled plugins.
- `claude/commands/*.md`: custom skills callable as `/audit`, `/debug`, `/recall`, `/scan-secrets`, `/check-dep`, `/sanitise-config`, `/voice-review`. Each is a markdown prompt with frontmatter.
- `claude/output-styles/warren.md`: Warren's personal voice profile, referenced by `settings.json` as `"outputStyle": "Warren"`. **If you're not Warren, copy this file to `<yourname>.md`, edit the content to your own voice, and change `settings.json` to point at it.** Otherwise Claude will write everything in Warren's voice. Full guide at `claude/docs/output-styles.md`.

**Enabled plugins** (declared in `settings.json`):
- `swift-lsp@claude-plugins-official`: Swift language server support
- `frontend-design@claude-plugins-official`: design tools for UI work
- `understand-anything@understand-anything`: codebase knowledge-graph builder (custom marketplace at `Lum1104/Understand-Anything`)

On first launch, Claude Code reads the marketplaces from `extraKnownMarketplaces` and pulls each plugin. If a plugin fails to auto-install, run `/plugins` in Claude Code and install manually.

### 3. SSH key recovery and passwordless usage

A small mechanism worth calling out because it's the reason setup.sh can clone private repos and push to GitHub from minute one of a fresh machine.

**Where the key comes from** (step 12, `SSH Key`):

```
secrets/id_rsa                                 (dotfiles, gitignored)
  ↓ falls back to
~/Library/Mobile Documents/com~apple~CloudDocs/ssh/id_rsa   (iCloud Drive)
  ↓ falls back to
prompt: generate a new RSA key here and now
```

The key is copied to `~/.ssh/id_rsa`, permissions set to 600, public key derived with `ssh-keygen -y`, and the result added to `ssh-agent` with `ssh-add --apple-use-keychain`. This step runs **before** the "Clone Repos" step so SSH auth works on the first pass.

**Why you never type the passphrase**: `ssh/config` has

```
Host *
    AddKeysToAgent yes
    UseKeychain yes
    IdentityFile ~/.ssh/id_rsa
```

`UseKeychain yes` tells the macOS SSH client to read/write the passphrase from the **login keychain**. `AddKeysToAgent yes` makes sure the key is loaded into `ssh-agent` on first use. Combined with the `ssh-add --apple-use-keychain` from step 12, the passphrase is stored once (on first unlock) and never asked again. Every `ssh`, `git push`, `git pull`, `rsync` over SSH after that is silent.

This is **per-machine, per-user**. The keychain entry doesn't travel; on a fresh laptop step 12 re-adds the key and macOS prompts once for the passphrase, then never again.

If you're an AI assistant working in this repo and need to ssh somewhere on the owner's behalf: it should just work. If it doesn't, the keychain entry probably didn't get re-added after a key rotation. Tell the user to run `ssh-add --apple-use-keychain ~/.ssh/id_rsa`.

### 4. `rag/` + `~/.wiki`: the knowledge system

Two complementary memory layers for Claude. Full explainer in `claude/docs/knowledge-system.md`. The short version:

- **RAG** is the journal. A Python service watches Claude Code's conversation JSONLs, embeds each turn locally (sentence-transformers on MPS or Ollama), stores vectors in ChromaDB. An MCP server exposes 7 tools to Claude (`search`, `get_context`, `log_action`, etc.). Indexing is automatic and background. Read `rag/README.md` for the full diagram.
- **Wiki** is the textbook. A separate private git repo at `~/.wiki` containing AI-written, human-curated markdown pages. Browsable in Obsidian. Each page is sourced and committed individually. Sync via `~/.wiki/sync.sh` on a launchd timer (pushes through GitHub, no extra infrastructure).

The wiki repo is **not in this dotfiles repo**. It's cloned separately by setup step 29. A new user without access to the owner's wiki should set `WIKI_REPO=git@github.com:youruser/wiki.git` and read `claude/docs/knowledge-system.md` for bootstrap instructions.

## How a new user should approach this

If your task is to help someone understand or adapt these dotfiles:

1. **Confirm the platform.** Apple Silicon Mac, recent macOS. Linux/Windows users want a different repo.
2. **Read `setup.sh` top-down**, at least the `STEP_NAMES` array and the section banners (`# Step N:`). That's the spine.
3. **Read `Brewfile`.** Most of what the laptop "is" comes from here.
4. **Read `claude/CLAUDE.md`.** That's the AI workflow philosophy. It governs how Claude behaves across every project.
5. **Read `rag/README.md` and `claude/docs/knowledge-system.md`** if the user cares about the knowledge system. Skip if not.

If your task is to **modify** the dotfiles:

- **Edits to live configs** (zshrc, gitconfig, claude commands) go in this repo and are reflected immediately via symlink. No reinstall needed.
- **New apps** go in `Brewfile`. Use the `[pick]` comment marker so they appear in the interactive picker.
- **New setup steps** go in `setup.sh`. Add to `STEP_NAMES`, increment the step count in `README.md`, write the step body following the existing `section "name"` / `ask "..."` pattern.
- **New skills or output styles** go in `claude/commands/` or `claude/output-styles/`. `setup.sh` already symlinks `*.md` from these dirs.

## Personal vs portable

Parts of this repo are personal to the owner and won't work for someone else without changes:

| Personal | Why | What to do |
|---|---|---|
| `WIKI_REPO` in setup.sh | Points at owner's private wiki | Override `WIKI_REPO` env var; see `claude/docs/knowledge-system.md` |
| `rag/scripts/sync.sh` | Multi-machine rsync to owner's Ubuntu mini PC | Don't load `rag-sync.plist`; comment block at top of the script explains |
| `nas/mount-nas.sh` | Hardcoded NAS IPs + Tailscale hostname | Edit `ADDRESSES`, `USER_NAME`, `SHARES` for your own NAS, or skip step 30 |
| `ssh/config` | Owner's SSH hosts | Replace with your own entries before running setup |
| `git/.gitconfig` | Owner's name + email | `.gitconfig.local` overrides if you symlink one in (ignored by git) |
| `claude/CLAUDE.md` | Owner's writing voice, RAG/wiki conventions, banned phrases | Edit or replace. This is opinionated by design. |

Everything else (Brewfile, macOS defaults, iTerm2 profile, fonts, language toolchains, the structure of setup.sh) is portable as-is.

## What's deliberately not here

- **No public keys, no secrets, no licence keys.** `.gitignore` blocks the obvious patterns. Secrets are sourced from `~/.secrets.env` (template at `shell/.secrets.env.template`).
- **No employer code or work-specific config.** Anything HL-specific lives in the private wiki repo, not here.
- **No content of the wiki itself.** Dotfiles ship the wiring; you bring your own knowledge.

## When in doubt

- "How does X get installed?" → search `setup.sh` for the step.
- "What does Claude know about my preferences?" → `claude/CLAUDE.md` is the canonical source.
- "How does the RAG memory work?" → `rag/README.md`.
- "What's the difference between RAG and the wiki?" → `claude/docs/knowledge-system.md`.
- "Why is X configured this way?" → check git log on the relevant file; commit messages are written in the imperative and explain the why.

The repo is small enough to read end-to-end in an hour. If you're an AI assistant scanning it to brief a new user, do that scan; don't summarise from this CLAUDE.md alone.
