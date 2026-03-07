#!/usr/bin/env bash
# ===========================================================================
# Mac Setup Script — Warren de Leon
# Fully configures a new Mac for React Native + iOS + Android development
#
# Usage:
#   git clone https://github.com/warrendeleon/dotfiles.git ~/Developer/dotfiles && cd ~/Developer/dotfiles && ./setup.sh
# ===========================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m' # No colour

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Guard: must be run from a cloned repo, not via pipe
if [[ -z "${BASH_SOURCE[0]:-}" ]] || [[ ! -f "${DOTFILES_DIR}/Brewfile" ]]; then
  echo "Error: Run this script from the cloned dotfiles repo, not via pipe."
  echo "  git clone https://github.com/warrendeleon/dotfiles.git ~/Developer/dotfiles && cd ~/Developer/dotfiles && ./setup.sh"
  exit 1
fi

STEP=0

# ---------------------------------------------------------------------------
# Progress widget (pinned to bottom of terminal)
# ---------------------------------------------------------------------------
STEP_NAMES=(
  "Xcode CLI Tools"
  "Homebrew"
  "Brewfile"
  "1Password"
  "Oh My Zsh + Powerlevel10k"
  "Dotfiles"
  "Secrets"
  "Fonts"
  "Node.js"
  "Ruby"
  "npm Packages"
  "Clone Repos"
  "Android SDK"
  "iOS Development"
  "SSH Key"
  "GitHub CLI"
  "iTerm2"
  "macOS Defaults"
  "Docker"
  "Tailscale SSH"
  "Fork Preferences"
  "WebStorm Settings"
  "Touch ID for sudo"
  "Firewall & FileVault"
  "Finder Sidebar"
  "Login Items"
  "Amphetamine Power Protect"
  "RAG System"
)
TOTAL_STEPS=${#STEP_NAMES[@]}

# Status for each step: "pending", "active", "done", "skipped"
declare -a STEP_STATUS
for ((i=0; i<TOTAL_STEPS; i++)); do
  STEP_STATUS[$i]="pending"
done

WIDGET_HEIGHT=$((TOTAL_STEPS + 6))  # top border + header + progress bar + separator + steps + bottom border

setup_scroll_region() {
  local rows
  rows=$(tput lines)
  if ((rows <= WIDGET_HEIGHT)); then
    return  # Terminal too small for widget
  fi
  # Reserve bottom rows for the widget
  printf '\033[%d;%dr' 1 $((rows - WIDGET_HEIGHT))
  # Move cursor to top of scroll region
  printf '\033[1;1H'
}

restore_scroll_region() {
  local rows
  rows=$(tput lines)
  printf '\033[;r'
  printf '\033[%d;1H' "$rows"
}

draw_widget() {
  local rows cols
  rows=$(tput lines)
  cols=$(tput cols)

  # Skip drawing if terminal is too small
  if ((rows <= WIDGET_HEIGHT || cols < 42)); then
    return
  fi

  # Save cursor position
  printf '\0337'

  # Calculate completed count
  local done_count=0
  for ((i=0; i<TOTAL_STEPS; i++)); do
    [[ "${STEP_STATUS[$i]}" == "done" ]] && done_count=$((done_count + 1))
  done

  # Widget width
  local w=40
  # Start position (bottom-right area)
  local start_row=$((rows - WIDGET_HEIGHT + 1))
  if ((start_row < 1)); then start_row=1; fi
  local start_col=$((cols - w - 2))
  if ((start_col < 1)); then start_col=1; fi

  # Draw each line of the widget
  local row=$start_row

  # Top border
  printf '\033[%d;%dH' "$row" "$start_col"
  printf "${DIM}┌──────────────────────────────────────┐${NC}"
  ((row++))

  # Header
  printf '\033[%d;%dH' "$row" "$start_col"
  printf "${DIM}│${NC} ${BOLD}Setup Progress${NC}  ${DIM}(%d/%d)${NC}" "$done_count" "$TOTAL_STEPS"
  # Pad to width
  local header_len=$((21 + ${#done_count} + ${#TOTAL_STEPS}))
  local pad=$((w - header_len - 1))
  printf '%*s' "$pad" ""
  printf "${DIM}│${NC}"
  ((row++))

  # Progress bar
  printf '\033[%d;%dH' "$row" "$start_col"
  local bar_width=36
  local filled=$((done_count * bar_width / TOTAL_STEPS))
  local empty=$((bar_width - filled))
  printf "${DIM}│${NC} ${GREEN}"
  for ((b=0; b<filled; b++)); do printf "█"; done
  printf "${DIM}"
  for ((b=0; b<empty; b++)); do printf "░"; done
  printf "${NC} ${DIM}│${NC}"
  ((row++))

  # Separator
  printf '\033[%d;%dH' "$row" "$start_col"
  printf "${DIM}├──────────────────────────────────────┤${NC}"
  ((row++))

  # Steps
  for ((i=0; i<TOTAL_STEPS; i++)); do
    printf '\033[%d;%dH' "$row" "$start_col"
    local icon name colour
    name="${STEP_NAMES[$i]}"
    case "${STEP_STATUS[$i]}" in
      done)    icon="✓"; colour="${GREEN}" ;;
      active)  icon="▸"; colour="${YELLOW}" ;;
      skipped) icon="–"; colour="${DIM}" ;;
      *)       icon="○"; colour="${DIM}" ;;
    esac
    printf "${DIM}│${NC} ${colour}%s  %-34s${NC}${DIM}│${NC}" "$icon" "$name"
    ((row++))
  done

  # Bottom border
  printf '\033[%d;%dH' "$row" "$start_col"
  printf "${DIM}└──────────────────────────────────────┘${NC}"

  # Restore cursor position
  printf '\0338'
}

# Call once at start to set up the scroll region and draw initial widget
init_widget() {
  clear
  setup_scroll_region
  draw_widget
}

# Clean up on exit
cleanup_widget() {
  # Kill background Xcode download if still running
  [[ -n "${XCODE_PID:-}" ]] && kill "$XCODE_PID" 2>/dev/null || true
  # Detach any mounted DMGs from this script
  hdiutil detach "/Volumes/Power Protect for Amphetamine" -quiet 2>/dev/null || true
  restore_scroll_region
  echo ""
}
trap cleanup_widget EXIT INT TERM

info()    { echo -e "${BLUE}ℹ${NC}  $1"; }
success() { echo -e "${GREEN}✓${NC}  $1"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $1"; }
error()   { echo -e "${RED}✗${NC}  $1"; }

section() {
  STEP=$((STEP + 1))

  # Mark previous step as done (if not first)
  if ((STEP > 1)); then
    STEP_STATUS[$((STEP - 2))]="done"
  fi
  # Mark current step as active
  STEP_STATUS[$((STEP - 1))]="active"

  draw_widget

  echo ""
  echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${CYAN}  Step ${STEP}/${TOTAL_STEPS}: $1${NC}"
  echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

# Mark the final step as done
finish_all() {
  STEP_STATUS[$((TOTAL_STEPS - 1))]="done"
  draw_widget
}

ask() {
  printf "${YELLOW}→${NC} %s ${BOLD}[y/N]${NC} " "$1"
  read -r response </dev/tty
  [[ "$response" =~ ^[Yy]$ ]]
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║                    Mac Setup Script                         ║${NC}"
echo -e "${BOLD}${CYAN}║                   Warren de Leon                            ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [[ "$(uname)" != "Darwin" ]]; then
  error "This script only runs on macOS."
  exit 1
fi

info "Running on $(sw_vers -productName) $(sw_vers -productVersion) ($(uname -m))"
info "Dotfiles directory: ${DOTFILES_DIR}"
echo ""
sleep 1

# Initialise the progress widget
init_widget
trap 'setup_scroll_region; draw_widget' WINCH

# ---------------------------------------------------------------------------
# Create essential directories
# ---------------------------------------------------------------------------
mkdir -p "$HOME/Developer"
success "~/Developer directory ready"

# ===========================================================================
# Step 1: Xcode Command Line Tools
# ===========================================================================
section "Xcode Command Line Tools"

if xcode-select -p &>/dev/null; then
  success "Already installed at $(xcode-select -p)"
else
  if ask "Install Xcode Command Line Tools?"; then
    info "Installing... (a system dialog will appear)"
    xcode-select --install
    echo ""
    warn "Press ENTER after the installation finishes."
    read -r </dev/tty
  fi
fi

# ===========================================================================
# Step 2: Homebrew
# ===========================================================================
section "Homebrew"

if command -v brew &>/dev/null; then
  success "Already installed at $(which brew)"
  if ask "Update Homebrew?"; then
    brew update
    success "Updated"
  fi
else
  if ask "Install Homebrew?"; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
    success "Installed"
  fi
fi

# ===========================================================================
# Step 3: Homebrew packages (Brewfile)
# ===========================================================================
section "Homebrew Packages (Brewfile)"

info "This will install:"
info "  - CLI tools: git, ripgrep, wget, watchman, ffmpeg, etc."
info "  - Languages: nvm, ruby, python, java (Temurin 17)"
info "  - Apps: Android Studio, WebStorm, iTerm2, Claude, IINA, etc."
info "  - Mac App Store: Amphetamine (requires App Store sign-in)"
echo ""
warn "Make sure you're signed in to the Mac App Store before continuing."
echo ""

if ask "Install all Homebrew packages from Brewfile?"; then
  brew bundle --file="${DOTFILES_DIR}/Brewfile" --verbose || {
    warn "Some packages failed to install (check output above)"
    warn "Re-run 'brew bundle --file=${DOTFILES_DIR}/Brewfile' after fixing"
  }
  success "Brewfile processing complete"
else
  warn "Skipped. Run 'brew bundle --file=${DOTFILES_DIR}/Brewfile' later."
fi

# Start Xcode download in the background (~12GB, takes a while)
XCODE_PID=""
if ! [[ -d "/Applications/Xcode.app" ]] && [[ -z "${XCODE_PID:-}" ]]; then
  if command -v mas &>/dev/null; then
    info "Starting Xcode download in the background (~12GB)..."
    mas install 497799835 &
    XCODE_PID=$!
    success "Xcode downloading (PID: ${XCODE_PID}) — continuing with other steps"
  else
    warn "mas not available. Install Xcode manually from the App Store."
  fi
else
  success "Xcode already installed"
fi

# ===========================================================================
# Step 4: 1Password Setup
# ===========================================================================
section "1Password"

if [[ -d "/Applications/1Password.app" ]]; then
  success "1Password app installed"
  info "Please sign in to 1Password now if you haven't already."
  info "The SSH key retrieval step later depends on 1Password being signed in."
  echo ""
  if ask "Open 1Password to sign in?"; then
    open -a "1Password" 2>/dev/null || warn "Could not open 1Password"
    warn "Press ENTER after you've signed in to 1Password."
    read -r </dev/tty
    success "1Password ready"
  fi

  # Set up 1Password CLI integration
  if command -v op &>/dev/null; then
    if op whoami &>/dev/null 2>&1; then
      success "1Password CLI already signed in"
    else
      info "Signing in to 1Password CLI..."
      eval "$(op signin)" 2>/dev/null || warn "Sign in manually later with: eval \"\$(op signin)\""
    fi
  fi
else
  warn "1Password not found. Install Homebrew packages first (Step 3)."
fi

# ===========================================================================
# Step 5: Oh My Zsh + Plugins + Theme
# ===========================================================================
section "Oh My Zsh + Powerlevel10k"

if [[ -d "$HOME/.oh-my-zsh" ]]; then
  success "Oh My Zsh already installed"
else
  if ask "Install Oh My Zsh?"; then
    RUNZSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
    success "Oh My Zsh installed"
  fi
fi

# zsh-autosuggestions plugin
ZSH_CUSTOM="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"
if [[ -d "${ZSH_CUSTOM}/plugins/zsh-autosuggestions" ]]; then
  success "zsh-autosuggestions already installed"
else
  info "Installing zsh-autosuggestions..."
  git clone https://github.com/zsh-users/zsh-autosuggestions "${ZSH_CUSTOM}/plugins/zsh-autosuggestions" || {
    warn "Failed to clone zsh-autosuggestions. Check network and retry."
  }
  [[ -d "${ZSH_CUSTOM}/plugins/zsh-autosuggestions" ]] && success "zsh-autosuggestions installed"
fi

# Powerlevel10k theme
if [[ -d "${ZSH_CUSTOM}/themes/powerlevel10k" ]]; then
  success "Powerlevel10k already installed"
else
  info "Installing Powerlevel10k..."
  git clone --depth=1 https://github.com/romkatv/powerlevel10k.git "${ZSH_CUSTOM}/themes/powerlevel10k" || {
    warn "Failed to clone Powerlevel10k. Check network and retry."
  }
  [[ -d "${ZSH_CUSTOM}/themes/powerlevel10k" ]] && success "Powerlevel10k installed"
fi

# ===========================================================================
# Step 6: Dotfiles (symlinks)
# ===========================================================================
section "Dotfiles (Symlinks)"

symlink() {
  local src="$1"
  local dest="$2"

  if [[ -L "$dest" ]]; then
    info "Already linked: $dest → $(readlink "$dest")"
    return
  fi

  if [[ -f "$dest" ]]; then
    local backup="${dest}.backup.$(date +%Y%m%d_%H%M%S)"
    warn "Backing up existing $dest → ${backup}"
    mv "$dest" "$backup"
  fi

  ln -sf "$src" "$dest"
  success "Linked: $dest → $src"
}

if ask "Symlink dotfiles? (existing files will be backed up)"; then
  symlink "${DOTFILES_DIR}/shell/.zprofile"     "$HOME/.zprofile"
  symlink "${DOTFILES_DIR}/shell/.zshrc"       "$HOME/.zshrc"
  symlink "${DOTFILES_DIR}/shell/.p10k.zsh"    "$HOME/.p10k.zsh"
  symlink "${DOTFILES_DIR}/git/.gitconfig"     "$HOME/.gitconfig"
  symlink "${DOTFILES_DIR}/git/.gitignore_global" "$HOME/.gitignore_global"
  symlink "${DOTFILES_DIR}/git/.gitmessage"    "$HOME/.gitmessage"

  # SSH config
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  symlink "${DOTFILES_DIR}/ssh/config"         "$HOME/.ssh/config"

  # Claude Code config
  mkdir -p "$HOME/.claude"
  CLAUDE_SETTINGS="$HOME/.claude/settings.json"
  if [[ -f "$CLAUDE_SETTINGS" ]]; then
    info "Claude Code settings already exist"
  else
    cat > "$CLAUDE_SETTINGS" << 'CLAUDEEOF'
{
  "includeCoAuthoredBy": false
}
CLAUDEEOF
    success "Claude Code settings created (co-authored-by disabled)"
  fi
  symlink "${DOTFILES_DIR}/claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
  # Symlink global skills (commands)
  if [[ -d "${DOTFILES_DIR}/claude/commands" ]]; then
    mkdir -p "$HOME/.claude/commands"
    for cmd in "${DOTFILES_DIR}/claude/commands/"*.md; do
      [[ -f "$cmd" ]] && symlink "$cmd" "$HOME/.claude/commands/$(basename "$cmd")"
    done
  fi

  success "All dotfiles linked"
else
  warn "Skipped dotfiles. Link manually later."
fi

# ===========================================================================
# Step 7: Secrets
# ===========================================================================
section "Secrets"

ICLOUD_SECRETS="$HOME/Library/Mobile Documents/com~apple~CloudDocs/.secrets.env"

if [[ -f "$HOME/.secrets.env" ]]; then
  success "~/.secrets.env already exists"
elif [[ -f "$ICLOUD_SECRETS" ]]; then
  info "Found secrets in iCloud Drive"
  cp "$ICLOUD_SECRETS" "$HOME/.secrets.env"
  chmod 600 "$HOME/.secrets.env"
  success "Copied ~/.secrets.env from iCloud Drive (permissions: 600)"
else
  if ask "Create ~/.secrets.env from template?"; then
    cp "${DOTFILES_DIR}/shell/.secrets.env.template" "$HOME/.secrets.env"
    chmod 600 "$HOME/.secrets.env"
    success "Created ~/.secrets.env (permissions: 600)"
    warn "Edit ~/.secrets.env to fill in your secret values"
  fi
fi

# Source secrets so licence keys are available for later steps
[[ -f "$HOME/.secrets.env" ]] && source "$HOME/.secrets.env"

# ===========================================================================
# Step 8: Fonts
# ===========================================================================
section "Fonts"

if ask "Install custom fonts (MesloLGS NF for Powerlevel10k, Font Awesome)?"; then
  FONT_DIR="$HOME/Library/Fonts"
  mkdir -p "$FONT_DIR"

  if [[ -d "${DOTFILES_DIR}/fonts" ]] && ls "${DOTFILES_DIR}/fonts/"*.{ttf,otf} &>/dev/null; then
    cp "${DOTFILES_DIR}/fonts/"*.{ttf,otf} "$FONT_DIR/" 2>/dev/null || true
    success "Fonts copied from dotfiles/fonts/"
  else
    info "Downloading MesloLGS NF fonts (Powerlevel10k recommended)..."
    for font in "MesloLGS%20NF%20Regular.ttf" "MesloLGS%20NF%20Bold.ttf" \
                "MesloLGS%20NF%20Italic.ttf" "MesloLGS%20NF%20Bold%20Italic.ttf"; do
      curl -fsSL "https://github.com/romkatv/powerlevel10k-media/raw/master/${font}" \
        -o "${FONT_DIR}/$(echo "$font" | sed 's/%20/ /g')" 2>/dev/null && \
        success "Downloaded $(echo "$font" | sed 's/%20/ /g')" || \
        warn "Failed to download ${font}"
    done
  fi
fi

# ===========================================================================
# Step 9: Node.js (nvm)
# ===========================================================================
section "Node.js (nvm)"

export NVM_DIR="$HOME/.nvm"
[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && . "/opt/homebrew/opt/nvm/nvm.sh"

if command -v nvm &>/dev/null; then
  success "nvm is available"

  NODE_VERSION="24"
  if ask "Install Node.js ${NODE_VERSION} and set as default?"; then
    nvm install "$NODE_VERSION" || {
      warn "Failed to install Node ${NODE_VERSION}. Check network and retry."
    }
    if command -v node &>/dev/null; then
      nvm alias default "$NODE_VERSION"
      success "Node $(node -v) installed and set as default"
    fi
  fi
else
  warn "nvm not found. Install Homebrew packages first (Step 3)."
fi

# ===========================================================================
# Step 10: Ruby (rbenv)
# ===========================================================================
section "Ruby (rbenv)"

if command -v rbenv &>/dev/null; then
  success "rbenv is available"

  if ask "Install latest stable Ruby via rbenv?"; then
    RUBY_LATEST=$(rbenv install -l 2>/dev/null | grep -E '^\s*[0-9]+\.[0-9]+\.[0-9]+$' | tail -1 | xargs || true)
    if [[ -z "$RUBY_LATEST" ]]; then
      warn "Could not determine latest Ruby version. Check rbenv install -l."
    else
    info "Latest stable Ruby: ${RUBY_LATEST}"
    rbenv install -s "$RUBY_LATEST" || {
      warn "Failed to install Ruby ${RUBY_LATEST}. Check rbenv and dependencies."
    }
    if rbenv versions 2>/dev/null | grep -q "$RUBY_LATEST"; then
      rbenv global "$RUBY_LATEST"
      success "Ruby ${RUBY_LATEST} installed and set as global"

      # Install essential gems for the new Ruby version
      info "Installing CocoaPods gem..."
      gem install cocoapods || warn "Failed to install CocoaPods gem."
      command -v pod &>/dev/null && success "CocoaPods gem installed for Ruby ${RUBY_LATEST}"
    fi
    fi
  fi
else
  warn "rbenv not found. Install Homebrew packages first (Step 3)."
fi

# ===========================================================================
# Step 11: Global npm packages
# ===========================================================================
section "Global npm Packages"

if command -v npm &>/dev/null; then
  # Enable corepack for Yarn Berry (project uses Yarn 3.6.4)
  info "Enabling corepack (for Yarn Berry)..."
  corepack enable || warn "corepack enable failed. Run manually if needed."
  success "Corepack enabled"

  if ask "Install global npm packages (claude-code, gitmoji-cli)?"; then
    npm install -g @anthropic-ai/claude-code gitmoji-cli
    success "Global npm packages installed"
  fi
else
  warn "npm not found. Install Node.js first (Step 9)."
fi

# ===========================================================================
# Step 12: Clone Repositories
# ===========================================================================
section "Clone Repositories"

REPO_DIR="$HOME/Developer/rn-warrendeleon"

if [[ -d "$REPO_DIR" ]]; then
  success "rn-warrendeleon already cloned at ${REPO_DIR}"
else
  if ask "Clone rn-warrendeleon to ~/Developer/rn-warrendeleon?"; then
    # Use HTTPS (SSH key is set up later in Step 15)
    git clone https://github.com/warrendeleon/rn-warrendeleon.git "$REPO_DIR"
    success "Cloned to ${REPO_DIR}"

    (cd "$REPO_DIR" && yarn install) && success "Dependencies installed" \
      || warn "yarn install failed. Run manually in $REPO_DIR."

    # iOS pods
    if [[ -d "$REPO_DIR/ios" ]] && command -v pod &>/dev/null; then
      info "Installing CocoaPods dependencies..."
      (cd "$REPO_DIR/ios" && pod install) && success "Pods installed" \
        || warn "pod install failed. Run manually in $REPO_DIR/ios."
    elif [[ -d "$REPO_DIR/ios" ]]; then
      warn "CocoaPods not found. Run 'pod install' in $REPO_DIR/ios after installing CocoaPods."
    fi
  fi
fi

# ===========================================================================
# Step 13: Android SDK Setup
# ===========================================================================
section "Android SDK Setup"

ANDROID_SDK="$HOME/Library/Android/sdk"
SDKMANAGER=""

# Check for existing sdkmanager
if [[ -f "$ANDROID_SDK/cmdline-tools/latest/bin/sdkmanager" ]]; then
  SDKMANAGER="$ANDROID_SDK/cmdline-tools/latest/bin/sdkmanager"
elif command -v sdkmanager &>/dev/null; then
  SDKMANAGER="sdkmanager"
fi

# If no SDK at all, download command-line tools directly (no need to open Android Studio)
if [[ -z "$SDKMANAGER" ]]; then
  if ask "Android SDK not found. Download and install command-line tools?"; then
    mkdir -p "$ANDROID_SDK/cmdline-tools"
    info "Downloading Android command-line tools..."
    CMDLINE_URL="https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip"
    CMDLINE_TMPDIR=$(mktemp -d)
    if curl -fsSL "$CMDLINE_URL" -o "$CMDLINE_TMPDIR/cmdline-tools.zip" && \
       unzip -qo "$CMDLINE_TMPDIR/cmdline-tools.zip" -d "$CMDLINE_TMPDIR"; then
      rm -rf "$ANDROID_SDK/cmdline-tools/latest"
      mv "$CMDLINE_TMPDIR/cmdline-tools" "$ANDROID_SDK/cmdline-tools/latest"
      SDKMANAGER="$ANDROID_SDK/cmdline-tools/latest/bin/sdkmanager"
      success "Command-line tools installed"
    else
      warn "Failed to download or extract Android command-line tools."
    fi
    rm -rf "$CMDLINE_TMPDIR"
  fi
fi

if [[ -n "$SDKMANAGER" ]]; then
  info "Accepting licences..."
  yes | "$SDKMANAGER" --licenses 2>/dev/null || true

  info "Installing SDK components..."
  "$SDKMANAGER" \
    "platform-tools" \
    "build-tools;35.0.0" \
    "platforms;android-35" \
    "emulator" \
    "system-images;android-35;google_apis;arm64-v8a" \
    "sources;android-35" \
    "ndk;27.0.12077973" || {
    warn "Some Android SDK components failed to install. Run sdkmanager manually to retry."
  }
  success "Android SDK components installed"

  if ask "Create an Android emulator (Pixel 8, API 35)?"; then
    "$ANDROID_SDK/cmdline-tools/latest/bin/avdmanager" create avd \
      --name "Pixel_8_API_35" \
      --package "system-images;android-35;google_apis;arm64-v8a" \
      --device "pixel_8" \
      --force || warn "Failed to create emulator. Create it manually in Android Studio."
    [[ -d "$HOME/.android/avd/Pixel_8_API_35.avd" ]] && success "Emulator 'Pixel_8_API_35' created"
  fi
else
  warn "Skipped Android SDK setup."
fi

# ===========================================================================
# Step 14: iOS Development Setup
# ===========================================================================
section "iOS Development (Xcode + CocoaPods)"

# Wait for background Xcode download if still running
if [[ -n "${XCODE_PID:-}" ]] && kill -0 "$XCODE_PID" 2>/dev/null; then
  info "Waiting for Xcode download to finish (PID: ${XCODE_PID})..."
  wait "$XCODE_PID" && success "Xcode download complete" || warn "Xcode download may have failed"
fi

if xcode-select -p &>/dev/null; then
  success "Xcode CLI tools installed"
fi

if [[ -d "/Applications/Xcode.app" ]]; then
  success "Xcode.app found"

  if ask "Accept Xcode licence and install additional components?"; then
    sudo xcodebuild -license accept 2>/dev/null || warn "Run 'sudo xcodebuild -license accept' manually"
    sudo xcodebuild -runFirstLaunch 2>/dev/null || true
    success "Xcode licence accepted and components installed"
  fi
else
  warn "Xcode.app not found. Install from the App Store (or 'mas install 497799835')."
  warn "After installing, re-run this step."
fi

# Check CocoaPods availability (installed via rbenv gem in Step 10)
if command -v pod &>/dev/null; then
  success "CocoaPods $(pod --version) installed"
else
  warn "CocoaPods not found. Install Ruby via rbenv (Step 10) and run: gem install cocoapods"
fi

# iOS Simulator runtime
if command -v xcrun &>/dev/null && [[ -d "/Applications/Xcode.app" ]]; then
  INSTALLED_RUNTIMES=$(xcrun simctl list runtimes 2>/dev/null | grep -c "iOS" || true)
  if [[ "$INSTALLED_RUNTIMES" -eq 0 ]]; then
    info "No iOS Simulator runtime found. Downloading latest..."
    xcodebuild -downloadPlatform iOS 2>/dev/null || {
      warn "Auto-download failed. Install manually: Xcode → Settings → Platforms → iOS"
    }
  else
    success "iOS Simulator runtime(s) already installed (${INSTALLED_RUNTIMES} found)"
  fi
fi

# ===========================================================================
# Step 15: SSH Key (from 1Password)
# ===========================================================================
section "SSH Key"

SSH_KEY="$HOME/.ssh/id_rsa"

if [[ -f "$SSH_KEY" ]]; then
  success "SSH key already exists (${SSH_KEY})"
else
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"

  if command -v op &>/dev/null; then
    if ask "Retrieve SSH key from 1Password?"; then
      info "Signing in to 1Password CLI..."
      eval "$(op signin)" 2>/dev/null || {
        warn "Sign in with: eval \"\$(op signin)\""
        warn "Then re-run this step."
      }

      if op whoami &>/dev/null; then
        info "Downloading private key from 1Password (Personal/id_rsa)..."
        op read "op://Personal/id_rsa/private key" --out-file "$SSH_KEY" 2>/dev/null \
          || op item get "id_rsa" --vault Personal --fields "notesPlain" > "$SSH_KEY" 2>/dev/null \
          || {
            warn "Could not auto-retrieve. Trying document download..."
            op document get "id_rsa" --vault Personal --out-file "$SSH_KEY" 2>/dev/null || {
              error "Could not retrieve SSH key automatically."
              info "Open 1Password → Personal vault → 'id_rsa' → copy private key manually"
              info "Then paste into: ${SSH_KEY}"
              read -rp "Press ENTER after you've saved the key..." </dev/tty
            }
          }

        if [[ -f "$SSH_KEY" ]]; then
          chmod 600 "$SSH_KEY"
          # Derive public key from private key
          ssh-keygen -y -f "$SSH_KEY" > "${SSH_KEY}.pub"
          chmod 644 "${SSH_KEY}.pub"

          # Add to macOS keychain
          eval "$(ssh-agent -s)"
          ssh-add --apple-use-keychain "$SSH_KEY"

          success "SSH key restored from 1Password and added to keychain"
          echo ""
          info "Public key:"
          cat "${SSH_KEY}.pub"
        fi
      fi
    fi
  else
    warn "1Password CLI (op) not found. Install Homebrew packages first (Step 3)."
    echo ""
    if ask "Generate a new RSA SSH key instead?"; then
      ssh-keygen -t rsa -b 4096 -C "hi@warrendeleon.com" -f "$SSH_KEY"
      eval "$(ssh-agent -s)"
      ssh-add --apple-use-keychain "$SSH_KEY"
      success "SSH key generated and added to keychain"
      echo ""
      info "Add this public key to GitHub:"
      cat "${SSH_KEY}.pub"
      echo ""
      info "https://github.com/settings/ssh/new"
    fi
  fi
fi

# ===========================================================================
# Step 16: GitHub CLI
# ===========================================================================
section "GitHub CLI"

if command -v gh &>/dev/null; then
  if gh auth status &>/dev/null 2>&1; then
    success "GitHub CLI already authenticated"
  else
    if ask "Authenticate GitHub CLI?"; then
      info "Opening browser for GitHub authentication..."
      gh auth login --hostname github.com --git-protocol ssh --web || {
        warn "Browser auth failed. Try manually: gh auth login"
      }

      if gh auth status &>/dev/null 2>&1; then
        success "GitHub CLI authenticated"
      fi
    fi
  fi

  # Set preferred defaults
  if gh auth status &>/dev/null 2>&1; then
    gh config set git_protocol ssh --host github.com 2>/dev/null
    gh config set editor "webstorm --wait" 2>/dev/null
    gh config set pager "less" 2>/dev/null
    success "GitHub CLI configured (SSH protocol, WebStorm editor)"
  fi
else
  warn "GitHub CLI (gh) not found. Install Homebrew packages first (Step 3)."
fi

# ===========================================================================
# Step 17: iTerm2 Configuration
# ===========================================================================
section "iTerm2 Configuration"

ITERM_PROFILES_DIR="$HOME/Library/Application Support/iTerm2/DynamicProfiles"

if ask "Configure iTerm2 (font, scrollback, colours)?"; then
  mkdir -p "$ITERM_PROFILES_DIR"
  # Back up existing profile if present
  if [[ -f "$ITERM_PROFILES_DIR/Default.json" ]]; then
    cp "$ITERM_PROFILES_DIR/Default.json" "$ITERM_PROFILES_DIR/Default.json.backup.$(date +%Y%m%d_%H%M%S)"
  fi
  cp "${DOTFILES_DIR}/iterm2/Default.json" "$ITERM_PROFILES_DIR/Default.json"
  success "Dynamic profile installed"

  # Set iTerm2 preferences via defaults
  defaults write com.googlecode.iterm2 "Default Bookmark Guid" -string "warrendeleon-default-profile"

  # Appearance: compact tabs
  defaults write com.googlecode.iterm2 TabViewType -int 1
  defaults write com.googlecode.iterm2 HideTab -bool false
  defaults write com.googlecode.iterm2 AlternateMouseScroll -bool true

  # No annoying prompts on quit
  defaults write com.googlecode.iterm2 PromptOnQuit -bool false
  defaults write com.googlecode.iterm2 OnlyWhenMoreTabs -bool false

  success "iTerm2 preferences set"
  info "Verify font is 'MesloLGS NF' in: Preferences → Profiles → Text"
  info "For Solarized Dark: Preferences → Profiles → Colors → Color Presets → Solarized Dark"
fi

# ===========================================================================
# Step 18: macOS Defaults
# ===========================================================================
section "macOS System Preferences"

info "This will set:"
info "  - Finder: show extensions, hidden files, path bar, list view, folders on top"
info "  - Screenshots: PNG to ~/Downloads"
info "  - Safari: Develop menu enabled"
info "  - Locale: British English"
echo ""

if ask "Apply macOS preferences?"; then
  bash "${DOTFILES_DIR}/macos/defaults.sh"
  success "Preferences applied"
fi

# ===========================================================================
# Step 19: Colima (Docker)
# ===========================================================================
section "Docker (Colima)"

if command -v colima &>/dev/null; then
  if colima status &>/dev/null; then
    success "Colima already running"
  elif ask "Start Colima (Docker runtime)?"; then
    colima start --cpu 4 --memory 8 --disk 60
    success "Colima started"
  fi
else
  warn "Colima not found. Install Homebrew packages first (Step 3)."
fi

# ===========================================================================
# Step 20: Tailscale + Remote Login (SSH)
# ===========================================================================
section "Tailscale SSH"

# Tailscale (App Store) — open it so user can log in
TAILSCALE_CLI="/Applications/Tailscale.app/Contents/MacOS/tailscale"

if [[ -d "/Applications/Tailscale.app" ]]; then
  # Wrapper script for CLI (symlink breaks — App Store binary checks bundle path)
  if [[ ! -x /usr/local/bin/tailscale ]]; then
    printf '#!/bin/sh\nexec "%s" "$@"\n' "$TAILSCALE_CLI" | sudo tee /usr/local/bin/tailscale > /dev/null
    sudo chmod +x /usr/local/bin/tailscale
    success "Tailscale CLI wrapper installed at /usr/local/bin/tailscale"
  fi

  if ! pgrep -q Tailscale; then
    info "Opening Tailscale..."
    open -a Tailscale
    sleep 3
  fi

  if "$TAILSCALE_CLI" status &>/dev/null 2>&1; then
    success "Tailscale connected"
  else
    info "Sign in to Tailscale via the menu bar icon."
    read -rp "Press ENTER after you've signed in..." </dev/tty
    if "$TAILSCALE_CLI" status &>/dev/null 2>&1; then
      success "Tailscale connected"
    else
      warn "Tailscale not connected. Sign in later via the menu bar icon."
    fi
  fi

  # Set custom hostname on the tailnet
  if "$TAILSCALE_CLI" status &>/dev/null 2>&1; then
    CURRENT_TS_HOST=$("$TAILSCALE_CLI" status --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('Self',{}).get('DNSName','').split('.')[0])" 2>/dev/null)
    info "Current Tailscale hostname: ${CURRENT_TS_HOST}"
    read -rp "Enter new hostname (or press ENTER to keep '${CURRENT_TS_HOST}'): " TS_HOSTNAME </dev/tty
    if [[ -n "$TS_HOSTNAME" ]]; then
      "$TAILSCALE_CLI" set --hostname="$TS_HOSTNAME" || warn "Could not set hostname."
      success "Tailscale hostname set to: ${TS_HOSTNAME}"
    fi
  fi
else
  warn "Tailscale not found. Install from the Mac App Store (Step 3)."
fi

# Enable macOS Remote Login (SSH) — works over Tailscale's private network
if ask "Enable macOS Remote Login (SSH) for access over Tailscale?"; then
  sudo systemsetup -setremotelogin on 2>/dev/null || warn "Could not enable Remote Login. Enable manually: System Settings → General → Sharing → Remote Login"
  if sudo systemsetup -getremotelogin 2>/dev/null | grep -q "On"; then
    success "Remote Login (SSH) enabled"
  fi
fi

info "To SSH into this Mac from another Tailscale device:"
info "  ssh $(whoami)@$(hostname -s)"
info "To SSH to your minipc: ssh warren@minipc"

# ===========================================================================
# Step 21: Fork Preferences + Singlebox
# ===========================================================================
section "Fork Preferences"

if [[ -d "/Applications/Fork.app" ]]; then
  if [[ -f "${DOTFILES_DIR}/com.DanPristupov.Fork.plist" ]]; then
    # Back up existing prefs if any
    FORK_PLIST="$HOME/Library/Preferences/com.DanPristupov.Fork.plist"
    if [[ -f "$FORK_PLIST" ]]; then
      cp "$FORK_PLIST" "${FORK_PLIST}.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    info "Restoring Fork preferences (diff font, stash/rebase settings, hooks)..."
    defaults import com.DanPristupov.Fork "${DOTFILES_DIR}/com.DanPristupov.Fork.plist"
    # Update paths for new machine
    defaults write com.DanPristupov.Fork defaultSourceFolder -string "$HOME/Developer"
    success "Fork preferences restored"
  else
    warn "Fork plist not found in dotfiles"
  fi
else
  warn "Fork not installed yet"
fi

# Restore Singlebox config (workspaces, licence, preferences)
SINGLEBOX_DIR="$HOME/Library/Application Support/Singlebox"
if [[ -d "/Applications/Singlebox.app" ]]; then
  if [[ -f "${DOTFILES_DIR}/singlebox/Settings" ]]; then
    info "Restoring Singlebox workspaces and preferences..."
    mkdir -p "$SINGLEBOX_DIR"
    # Back up existing config if present
    if [[ -f "$SINGLEBOX_DIR/Settings" ]]; then
      cp "$SINGLEBOX_DIR/Settings" "$SINGLEBOX_DIR/Settings.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    cp "${DOTFILES_DIR}/singlebox/Settings" "$SINGLEBOX_DIR/Settings"

    # Inject licence key from secrets
    if [[ -n "${SINGLEBOX_KEY:-}" ]]; then
      ESCAPED_SINGLEBOX_KEY=$(printf '%s\n' "$SINGLEBOX_KEY" | sed 's/[&/\]/\\&/g')
      sed -i '' "s/SINGLEBOX_KEY_PLACEHOLDER/${ESCAPED_SINGLEBOX_KEY}/" "$SINGLEBOX_DIR/Settings"
      success "Singlebox config restored (6 workspaces + licence activated)"
    else
      success "Singlebox config restored (6 workspaces)"
      warn "Licence key not found in ~/.secrets.env — add SINGLEBOX_KEY to activate"
    fi
    warn "You'll need to re-sign in to each service on first open."
  else
    warn "Singlebox Settings not found in dotfiles"
  fi
else
  warn "Singlebox not installed yet"
fi

# ===========================================================================
# Step 22: WebStorm Settings Sync
# ===========================================================================
section "WebStorm Settings"

info "WebStorm settings need to be synced via JetBrains Settings Sync."
echo ""
info "On your OLD Mac (before wiping):"
info "  1. Open WebStorm → Settings → Settings Sync"
info "  2. Sign in to JetBrains Account"
info "  3. Click 'Enable Settings Sync' → 'Push Settings to Account'"
echo ""
info "On this NEW Mac:"
info "  1. Open WebStorm → Settings → Settings Sync"
info "  2. Sign in with same JetBrains Account"
info "  3. Click 'Get Settings from Account'"
echo ""
info "This will restore: font (25pt), Monokai Pro theme, Claude Code plugin,"
info "gitmoji plugin, react-native-console, and all other settings."
echo ""

if ask "Open WebStorm now to set up Settings Sync?"; then
  open -a "WebStorm" 2>/dev/null || warn "WebStorm not found"
  warn "Press ENTER after you've synced your settings."
  read -r </dev/tty
  success "WebStorm configured"
fi

# ===========================================================================
# Step 23: Touch ID for sudo
# ===========================================================================
section "Touch ID for sudo"

PAM_SUDO="/etc/pam.d/sudo_local"

if [[ -f "$PAM_SUDO" ]] && grep -q "pam_tid" "$PAM_SUDO" 2>/dev/null; then
  success "Touch ID for sudo already enabled"
else
  info "This lets you use Touch ID instead of typing your password for sudo."
  if ask "Enable Touch ID for sudo?"; then
    sudo bash -c 'cat > /etc/pam.d/sudo_local << EOF
# sudo_local: local config for sudo (survives macOS updates)
auth       sufficient     pam_tid.so
EOF'
    success "Touch ID for sudo enabled"
  fi
fi

# ===========================================================================
# Step 24: Firewall & FileVault
# ===========================================================================
section "Firewall & FileVault"

# Firewall
FIREWALL_STATUS=$(sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -c "enabled" || true)
if [[ "$FIREWALL_STATUS" -gt 0 ]]; then
  success "Firewall already enabled"
else
  if ask "Enable macOS Firewall?"; then
    sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
    success "Firewall enabled"
  fi
fi

# FileVault
FILEVAULT_STATUS=$(fdesetup status 2>/dev/null | grep -c "On" || true)
if [[ "$FILEVAULT_STATUS" -gt 0 ]]; then
  success "FileVault already enabled"
else
  if ask "Enable FileVault (full-disk encryption)?"; then
    sudo fdesetup enable
    success "FileVault enabled — save your recovery key somewhere safe!"
  fi
fi

# ===========================================================================
# Step 25: Finder Sidebar
# ===========================================================================
section "Finder Sidebar"

info "Adding ~/Developer to Finder sidebar..."

# Check if already in sidebar, then add if not
if command -v mysides &>/dev/null; then
  if mysides list 2>/dev/null | grep -q "Developer"; then
    success "Developer already in Finder sidebar"
  else
    mysides add Developer "file://$HOME/Developer/"
    success "Developer added to Finder sidebar"
  fi
else
  # Alternative: use Finder AppleScript (try/catch handles duplicates)
  osascript -e "
    tell application \"Finder\"
      set devFolder to POSIX file \"$HOME/Developer\" as alias
      try
        make new item at sidebar favorites with properties {target:devFolder}
      end try
    end tell
  " 2>/dev/null && success "Developer added to Finder sidebar" \
    || warn "Could not add automatically. Drag ~/Developer to Finder sidebar manually."
fi

# ===========================================================================
# Step 26: Login Items
# ===========================================================================
section "Login Items"

info "Setting apps to open at login..."

LOGIN_APPS=(
  "/Applications/1Password.app"
  "/Applications/Amphetamine.app"
  "/Applications/Rocket.app"
  "/Applications/Google Drive.app"
  "/Applications/Elgato Control Center.app"
  "/Applications/Singlebox.app"
  "/Applications/BetterDisplay.app"
  "/Applications/DisplayLink Manager.app"
)

for app in "${LOGIN_APPS[@]}"; do
  app_name=$(basename "$app" .app)
  if [[ -d "$app" ]]; then
    # Check if already a login item to avoid duplicates
    if osascript -e "tell application \"System Events\" to get the name of every login item" 2>/dev/null | grep -q "$app_name"; then
      success "Login item already exists: ${app_name}"
    else
      osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$app\", hidden:false}" 2>/dev/null \
        && success "Login item added: ${app_name}" \
        || warn "Could not add: ${app_name}"
    fi
  else
    warn "Not installed, skipping: ${app_name}"
  fi
done

# Activate BetterDisplay Pro licence if key is available
BETTERDISPLAY_BIN="/Applications/BetterDisplay.app/Contents/MacOS/BetterDisplay"
if [[ -f "$BETTERDISPLAY_BIN" ]] && [[ -n "${BETTERDISPLAY_EMAIL:-}" ]] && [[ -n "${BETTERDISPLAY_KEY:-}" ]]; then
  info "Activating BetterDisplay Pro licence..."
  "$BETTERDISPLAY_BIN" manageLicense -activate -email="$BETTERDISPLAY_EMAIL" -key="$BETTERDISPLAY_KEY" \
    && success "BetterDisplay Pro activated" \
    || warn "BetterDisplay activation failed — activate manually"
elif [[ -f "$BETTERDISPLAY_BIN" ]]; then
  warn "BetterDisplay licence key not found in ~/.secrets.env — activate manually"
fi

# Open Privacy settings — apps will need Accessibility & Full Disk Access
echo ""
info "Some apps need privacy permissions (Accessibility)."
info "Opening System Settings — please grant access to each app listed below."

ACCESSIBILITY_APPS=(
  "Amphetamine:com.if.Amphetamine"
  "BetterDisplay:pro.betterdisplay.BetterDisplay"
  "Rocket:net.matthewpalmer.Rocket"
  "Rectangle:com.knollsoft.Rectangle"
  "iTerm2:com.googlecode.iterm2"
)

open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
echo ""

for entry in "${ACCESSIBILITY_APPS[@]}"; do
  app_name="${entry%%:*}"
  warn "  Grant Accessibility access to: ${app_name}"
done

echo ""
warn "Toggle each app ON in the System Settings window that just opened."
warn "Press ENTER after you've granted all permissions."
read -r </dev/tty
success "Accessibility permissions step complete"

# Set up daily auto-updates for Homebrew (formulae, casks, and App Store apps)
echo ""
if ask "Enable daily auto-updates for all apps (Homebrew + App Store)?"; then
  brew tap domt4/autoupdate 2>/dev/null || warn "Could not tap domt4/autoupdate"
  brew autoupdate start --upgrade --cleanup --enable-notification 2>/dev/null \
    && success "Auto-updates enabled (daily, with notifications)" \
    || warn "Could not enable autoupdate. Run manually: brew autoupdate start"
fi

# ===========================================================================
# Step 27: Amphetamine Power Protect
# ===========================================================================
section "Amphetamine Power Protect"

# Check if already installed
if [[ -f "/private/etc/sudoers.d/amphetamine-power-protect" ]] || \
   ls /private/etc/sudoers.d/*mphetamine* &>/dev/null 2>&1; then
  success "Amphetamine Power Protect already installed"
else

info "Power Protect enables closed-display mode without Touch ID prompts."
info "This downloads the installer and opens it — you'll need to run it manually."
echo ""

POWER_PROTECT_TMPDIR=$(mktemp -d)
POWER_PROTECT_DMG="$POWER_PROTECT_TMPDIR/Power Protect for Amphetamine.dmg"
POWER_PROTECT_URL="https://github.com/x74353/Amphetamine-Power-Protect/raw/main/DMG/Power%20Protect%20for%20Amphetamine.dmg"

if ask "Download and open Amphetamine Power Protect installer?"; then
  info "Downloading..."
  if ! curl -fsSL "$POWER_PROTECT_URL" -o "$POWER_PROTECT_DMG"; then
    warn "Failed to download Power Protect. Install manually later."
    rm -rf "${POWER_PROTECT_TMPDIR:-}"
  elif ! hdiutil attach "$POWER_PROTECT_DMG" -nobrowse -quiet; then
    warn "Failed to mount DMG. Install Power Protect manually."
    rm -rf "${POWER_PROTECT_TMPDIR:-}"
  else
    success "Downloaded and mounted"
    open "/Volumes/Power Protect for Amphetamine"
    success "Opened — run the installer inside the window"
    echo ""

    # Wait for installation to complete (timeout after 2 minutes)
    info "Waiting for Power Protect to be installed..."
    TIMEOUT=120
    ELAPSED=0
    while true; do
      if [[ -f "/private/etc/sudoers.d/amphetamine-power-protect" ]] || \
         ls /private/etc/sudoers.d/*mphetamine* &>/dev/null 2>&1; then
        success "Power Protect installed successfully"
        break
      fi
      sleep 3
      ELAPSED=$((ELAPSED + 3))
      if ((ELAPSED >= TIMEOUT)); then
        warn "Timed out waiting. Install Power Protect manually later."
        break
      fi
      echo -e "${DIM}  Still waiting... (${ELAPSED}s/${TIMEOUT}s)${NC}"
    done

    # Clean up
    hdiutil detach "/Volumes/Power Protect for Amphetamine" -quiet 2>/dev/null || true
    rm -rf "${POWER_PROTECT_TMPDIR:-}"
    success "Cleaned up"
  fi
fi

fi  # end of "already installed" check

# ===========================================================================
# Step 28: RAG System (Local Semantic Search)
# ===========================================================================
section "RAG System"

RAG_DIR="${DOTFILES_DIR}/rag"
RAG_HOME="$HOME/.rag"

if [[ -d "$RAG_DIR" ]]; then
  if ask "Set up the local RAG system (semantic search for conversations and code)?"; then
    # Create runtime directories
    mkdir -p "$RAG_HOME/logs"

    # Copy config template
    if [[ ! -f "$RAG_HOME/config.yaml" ]]; then
      cp "$RAG_DIR/config.yaml.template" "$RAG_HOME/config.yaml"
      success "Config template copied to $RAG_HOME/config.yaml"
    else
      success "Config already exists"
    fi

    # Create Python virtual environment
    if [[ ! -d "$RAG_HOME/venv" ]]; then
      info "Creating Python virtual environment..."
      python3 -m venv "$RAG_HOME/venv"
      success "Virtual environment created"
    else
      success "Virtual environment already exists"
    fi

    # Install dependencies
    info "Installing Python dependencies..."
    if "$RAG_HOME/venv/bin/pip" install --quiet --upgrade pip && \
       "$RAG_HOME/venv/bin/pip" install --quiet -r "$RAG_DIR/requirements.txt" && \
       "$RAG_HOME/venv/bin/pip" install --quiet -e "$RAG_DIR"; then
      success "Dependencies installed"
    else
      warn "Some Python dependencies failed to install. Run pip install manually."
    fi

    # Pull Ollama embedding model
    if command -v ollama &>/dev/null; then
      info "Pulling mxbai-embed-large model (one-time, ~670MB)..."
      ollama pull mxbai-embed-large || warn "Failed to pull model. Run: ollama pull mxbai-embed-large"
      ollama list 2>/dev/null | grep -q "mxbai-embed-large" && success "Embedding model ready"
    else
      warn "Ollama not found. Install it first, then run: ollama pull mxbai-embed-large"
    fi

    # Install launchd plists (substitute username in paths)
    for plist in "$RAG_DIR/launchd/"*.plist; do
      [[ -f "$plist" ]] || continue
      plist_name=$(basename "$plist")
      target="$HOME/Library/LaunchAgents/$plist_name"
      if [[ -f "$target" ]]; then
        launchctl unload "$target" 2>/dev/null || true
      fi
      # Replace hardcoded username with current user's home directory
      sed "s|/Users/warrendeleon|$HOME|g" "$plist" > "$target"
      launchctl load "$target"
      success "Loaded $plist_name"
    done

    # Register MCP server with Claude Code
    if command -v claude &>/dev/null; then
      info "Registering RAG MCP server..."
      claude mcp add --scope user --transport stdio rag \
        --directory "$RAG_DIR" \
        -- "$RAG_HOME/venv/bin/python" -m src.server 2>/dev/null || \
        warn "MCP registration failed. Register manually later."
      success "MCP server registered"
    else
      warn "Claude CLI not found. Register MCP manually after installing claude-code."
    fi

    # Start bulk indexing (recent conversations first)
    if ask "Start bulk indexing? (runs in background, recent 30 days first)"; then
      info "Enqueuing files for indexing..."
      (cd "$RAG_DIR" && "$RAG_HOME/venv/bin/python" scripts/bulk_index.py --recent-days 30 2>&1 | tail -5) \
        || warn "Bulk index failed. Run manually later."
      success "Bulk index enqueued. The indexer service will process them in the background."
    fi

    success "RAG system set up"
  fi
else
  warn "RAG directory not found at ${RAG_DIR}"
fi

# ===========================================================================
# Done!
# ===========================================================================
finish_all
trap - EXIT INT TERM WINCH
restore_scroll_region
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║                    Setup Complete!                           ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
info "Post-setup checklist:"
echo "  1. Restart your terminal (or run: source ~/.zshrc)"
echo "  2. Edit ~/.secrets.env with your secret values"
echo "  3. Sign in to: NordVPN, Tailscale, Slack, Teams, Zoom, Mattermost, Spotify"
echo "  4. Set iTerm2 font to 'MesloLGS NF' (Preferences → Profiles → Text)"
echo "  5. Open Amphetamine → start a session → configure preferences"
echo "  6. Save your FileVault recovery key somewhere safe"
echo "  7. Open DisplayLink Manager and sign in (installed via Brewfile)"
echo "  8. Set up the SSH remote for rn-warrendeleon: git remote set-url origin git@github.com:warrendeleon/rn-warrendeleon.git"
echo ""
success "Enjoy your new Mac!"
