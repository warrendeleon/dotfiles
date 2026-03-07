# Brewfile — Warren de Leon's Mac Setup
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

# Communication
cask "slack"                     # Team chat
cask "microsoft-teams"           # Video calls
cask "zoom"                      # Video calls
cask "mattermost"                # Team messaging
cask "singlebox"                 # Multi-account browser

# Productivity
cask "1password"                 # Password manager
cask "1password-cli"             # 1Password CLI (op)
cask "numi"                      # Calculator
cask "rocket"                    # Emoji picker
cask "google-drive"              # Cloud storage
cask "rectangle"                 # Window management (keyboard shortcuts)

# Media & Streaming
cask "iina"                      # Video player (replaces VLC)
cask "spotify"                   # Music
cask "ecamm-live"                # Live streaming & recording
cask "gifski"                    # GIF encoder

# Browsers
cask "google-chrome"             # Web browser

# Networking & Security
cask "nordvpn"                   # VPN
brew "tailscale"                 # Mesh VPN (CLI version — supports Tailscale SSH)

# Hardware & Display
cask "elgato-control-center"     # Elgato lights
cask "betterdisplay"             # Monitor management
cask "displaylink"               # DisplayLink Manager (deprecated: unsigned, still installable)

# Cloud SDKs
cask "google-cloud-sdk"          # gcloud CLI

# ============================================================================
# Mac App Store Apps (requires `mas` + App Store sign-in)
# ============================================================================
mas "Amphetamine", id: 937984704      # Keep Mac awake
# Xcode installed separately in setup.sh (background download, ~12GB)
