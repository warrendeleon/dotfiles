# Brewfile — Mac Setup
# Install with: brew bundle --file=Brewfile

# ============================================================================
# Taps
# ============================================================================
tap "homebrew/bundle"
tap "oven-sh/bun"
tap "wix/brew"

# ============================================================================
# Core CLI Tools
# ============================================================================
brew "git"
brew "git-filter-repo"
brew "wget"
brew "ripgrep"
brew "gh"                        # GitHub CLI
brew "mas"                       # Mac App Store CLI
brew "duti"                      # Set default apps per file type
brew "aria2"                     # Parallel downloader (used by xcodes)
brew "xcodes"                    # Fast Xcode installer (parallel downloads via aria2)
brew "jq"                        # JSON processor
brew "tree"                      # Directory structure viewer
brew "bat"                       # Cat with syntax highlighting
brew "eza"                       # Modern ls with icons and colours
brew "fd"                        # Modern find (faster, simpler)
brew "fzf"                       # Fuzzy finder (history, file search)
brew "tlrc"                      # Simplified man pages (tldr client)
brew "htop"                      # Interactive process viewer
brew "trash"                     # Move to Trash instead of rm
brew "zoxide"                    # Smarter cd (remembers directories)
brew "git-delta"                 # Better git diff (syntax highlighting)
brew "ncdu"                      # Interactive disk usage analyser
brew "lazygit"                   # Terminal UI for git

# ============================================================================
# Shell
# ============================================================================
# Oh My Zsh + Powerlevel10k installed separately in setup.sh

# ============================================================================
# Languages & Runtimes
# ============================================================================
brew "nvm"                       # Node version manager
brew "bun"                       # Fast JS runtime
# Yarn Berry managed via corepack (bundled with Node.js)
brew "rbenv"                     # Ruby version manager
brew "ruby-build"                # rbenv plugin for building Ruby
brew "ruby"                      # System Ruby (for CocoaPods bootstrap)
brew "python@3.13"               # Python
brew "pipx"                      # Python CLI tool installer

# Java (Temurin 17 — required for React Native / Android)
cask "temurin@17"

# ============================================================================
# React Native / Mobile Development
# ============================================================================
brew "watchman"                  # File watcher (required by Metro)
brew "fswatch"                   # File watcher (RAG indexing pipeline)
# CocoaPods installed via rbenv gem (avoids conflicts with Homebrew Ruby)
brew "applesimutils"             # iOS simulator utilities (Detox)
brew "detox"                     # E2E testing framework
brew "ccache"                    # Compiler cache for faster native builds

# ============================================================================
# Docker & Cloud
# ============================================================================
brew "colima"                    # Docker runtime for macOS (no Docker Desktop)
brew "docker"                    # Docker CLI
brew "docker-completion"         # Docker shell completions
brew "kubernetes-cli"            # kubectl

# ============================================================================
# Security & Networking
# ============================================================================
brew "gnupg"                     # GPG encryption
brew "openssl@3"                 # TLS/SSL toolkit

# ============================================================================
# Media & Image Processing
# ============================================================================
brew "ffmpeg"                    # Video/audio processing
brew "imagemagick"               # Image manipulation
brew "tesseract"                 # OCR engine

# ============================================================================
# AI / ML (Apple Silicon)
# ============================================================================
brew "ollama"                    # Local LLM runner
brew "mlx"                       # Apple Silicon ML framework

# ============================================================================
# Database
# ============================================================================
brew "mysql-client"              # MySQL CLI tools
brew "sqlite"                    # SQLite

# ============================================================================
# GUI Applications (Casks)
# ============================================================================

# Development
cask "android-studio"            # Android IDE + SDK
cask "visual-studio-code"        # Code editor
cask "webstorm"                  # JetBrains IDE
cask "iterm2"                    # Terminal emulator
cask "fork"                      # Git GUI
cask "reactotron"                # Redux debugging
cask "sim-genie"                 # iOS Simulator management
cask "db-browser-for-sqlite"     # SQLite GUI
cask "sublime-text"              # Text editor

# AI
cask "claude"                    # Claude Desktop app
cask "chatgpt"                   # ChatGPT Desktop app

# Communication
cask "slack"                     # Team chat
cask "microsoft-teams"           # Video calls
cask "zoom"                      # Video calls
cask "mattermost"                # Team messaging
cask "singlebox"                 # Multi-account browser

# Productivity
cask "bitwarden"                 # Password manager
brew "bitwarden-cli"             # Bitwarden CLI (bw)
cask "1password"                 # Password manager (legacy)
cask "1password-cli"             # 1Password CLI (op)
cask "rocket"                    # Emoji picker
cask "google-drive"              # Cloud storage
cask "raycast"                   # Spotlight replacement (launcher, clipboard, window management)
cask "the-unarchiver"            # Archive extraction (zip, rar, 7z, etc.)
cask "notion"                    # Notes and project management

# Media & Streaming
cask "iina"                      # Video player (replaces VLC)
cask "spotify"                   # Music
cask "ecamm-live"                # Live streaming & recording
# gifski installed via Mac App Store (not available as brew cask)

# Browsers
cask "google-chrome"             # Web browser

# Networking & Security
cask "nordvpn"                   # VPN
# Tailscale installed via Mac App Store (network extension required for MagicDNS)

# Hardware & Display
cask "elgato-control-center"     # Elgato lights
cask "logi-options+"              # Logitech mouse configuration
cask "betterdisplay"             # Monitor management
cask "displaylink"               # DisplayLink Manager (deprecated: unsigned, still installable)

# Cloud SDKs
cask "google-cloud-sdk"          # gcloud CLI

# ============================================================================
# Mac App Store Apps (requires `mas` + App Store sign-in)
# ============================================================================
mas "Amphetamine", id: 937984704      # Keep Mac awake
mas "Gifski", id: 1351639930          # GIF encoder
mas "Tailscale", id: 1475387142       # Mesh VPN (App Store for MagicDNS + network extension)
# Xcode installed separately in setup.sh (background download, ~12GB)
