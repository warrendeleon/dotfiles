# Brewfile — Mac Setup
# Lines marked [pick] are shown in the interactive picker.
# Everything else installs automatically as a dependency.

# ============================================================================
# Taps
# ============================================================================
tap "oven-sh/bun"
tap "wix/brew"

# ============================================================================
# Core CLI Tools (always installed)
# ============================================================================
brew "git"
brew "git-filter-repo"
brew "wget"
brew "ripgrep"
brew "gh"
brew "jq"
brew "tree"
brew "bat"
brew "eza"
brew "fd"
brew "fzf"
brew "tlrc"
brew "htop"
brew "trash"
brew "zoxide"
brew "git-delta"
brew "ncdu"
brew "lazygit"
brew "gnupg"
brew "openssl@3"
brew "duti"

# ============================================================================
# Languages & Runtimes (always installed)
# ============================================================================
brew "nvm"
brew "oven-sh/bun/bun"
brew "rbenv"
brew "ruby-build"
brew "ruby"
brew "python@3.13"
brew "pipx"
cask "temurin@17"

# ============================================================================
# Apps (interactive picker)
# ============================================================================

# Development
cask "android-studio"            # Android IDE + SDK [pick]
cask "visual-studio-code"        # Code editor [pick]
cask "webstorm"                  # JetBrains IDE [pick]
cask "iterm2"                    # Terminal emulator [pick]
cask "fork"                      # Git GUI [pick]
cask "reactotron"                # Redux debugging [pick]
cask "sim-genie"                 # iOS Simulator management [pick]
cask "sublime-text"              # Text editor [pick]

# AI
cask "claude"                    # Claude Desktop app [pick]
cask "chatgpt"                   # ChatGPT Desktop app [pick]
brew "ollama"                    # Local LLM runner [pick]

# Communication
cask "slack"                     # Team chat [pick]
cask "zoom"                      # Video calls [pick]
cask "mattermost"                # Team messaging [pick]
cask "singlebox"                 # Multi-account browser [pick]

# Productivity
cask "bitwarden"                 # Password manager [pick]
brew "bitwarden-cli"             # Bitwarden CLI (installed with Bitwarden)
cask "1password"                 # Password manager (legacy) [pick]
cask "1password-cli"             # 1Password CLI (installed with 1Password)
cask "rocket"                    # Emoji picker [pick]
cask "google-drive"              # Cloud storage [pick]
cask "raycast"                   # Spotlight replacement [pick]
cask "the-unarchiver"            # Archive extraction [pick]
cask "notion"                    # Notes and project management [pick]
cask "localsend"                 # AirDrop alternative [pick]

# Media & Streaming
cask "iina"                      # Video player [pick]
cask "spotify"                   # Music [pick]
cask "ecamm-live"                # Live streaming & recording [pick]

# Browsers
cask "google-chrome"             # Web browser [pick]

# Networking & Security
cask "nordvpn"                   # VPN [pick]

# Mobile Development (dependencies auto-installed with Android Studio)
brew "watchman"                  # File watcher (Metro) [pick]
brew "fswatch"                   # File watcher (RAG pipeline) [pick]
brew "applesimutils"             # iOS simulator utilities [pick]
brew "ccache"                    # Compiler cache [pick]
brew "mas"                       # Mac App Store CLI [pick]
brew "aria2"                     # Parallel downloader [pick]
brew "xcodes"                    # Fast Xcode installer [pick]

# Docker & Cloud
brew "colima"                    # Docker runtime [pick]
brew "docker"                    # Docker CLI [pick]
brew "docker-completion"         # Docker shell completions [pick]
brew "kubernetes-cli"            # kubectl [pick]

# Hardware & Display
cask "elgato-control-center"     # Elgato lights [pick]
cask "logi-options+"             # Logitech mouse configuration [pick]
cask "betterdisplay"             # Monitor management [pick]
cask "aldente"                   # Battery charge limiter [pick]
cask "displaylink"               # DisplayLink Manager [pick]

# ============================================================================
# Mac App Store Apps (requires sign-in)
# ============================================================================
mas "Amphetamine", id: 937984704      # Keep Mac awake [pick]
mas "Gifski", id: 1351639930          # GIF encoder [pick]
mas "Tailscale", id: 1475387142       # Mesh VPN [pick]
# Xcode installed separately in setup.sh (background download, ~12GB)
