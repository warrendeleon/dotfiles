#!/usr/bin/env bash
# ===========================================================================
# Mac Setup Script
# Fully configures a new Mac for React Native + iOS + Android development
#
# Usage (fresh Mac — no git yet):
#   mkdir -p ~/Developer && curl -fsSL https://github.com/warrendeleon/dotfiles/archive/refs/heads/main.tar.gz | tar xz -C ~/Developer && mv ~/Developer/dotfiles-main ~/Developer/dotfiles && cd ~/Developer/dotfiles && chmod +x setup.sh && ./setup.sh
#
# Usage (git available):
#   git clone https://github.com/warrendeleon/dotfiles.git ~/Developer/dotfiles && cd ~/Developer/dotfiles && ./setup.sh
# ===========================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Guard: never run as root (Homebrew refuses, sudo is used internally)
# ---------------------------------------------------------------------------
if [[ "$EUID" -eq 0 ]]; then
  echo "Error: Do not run this script with sudo. Run as your normal user:"
  echo "  ./setup.sh"
  echo "The script will ask for your password when it needs elevated access."
  exit 1
fi

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
LOGFILE="${DOTFILES_DIR}/setup.log"

# Log all output (stdout + stderr) to file while still showing on screen
exec > >(tee -a "$LOGFILE") 2>&1
echo "=== Setup started: $(date) ==="
echo "=== macOS $(sw_vers -productVersion 2>/dev/null || echo 'unknown') ($(uname -m)) ==="

# Guard: must be run from a cloned repo, not via pipe
if [[ -z "${BASH_SOURCE[0]:-}" ]] || [[ ! -f "${DOTFILES_DIR}/Brewfile" ]]; then
  echo "Error: Run this script from the dotfiles directory, not via pipe."
  echo "  Fresh Mac:  mkdir -p ~/Developer && curl -fsSL https://github.com/warrendeleon/dotfiles/archive/refs/heads/main.tar.gz | tar xz -C ~/Developer && mv ~/Developer/dotfiles-main ~/Developer/dotfiles && cd ~/Developer/dotfiles && chmod +x setup.sh && ./setup.sh"
  echo "  With git:   git clone https://github.com/warrendeleon/dotfiles.git ~/Developer/dotfiles && cd ~/Developer/dotfiles && ./setup.sh"
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
  "Password Manager"
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
trap cleanup_widget EXIT

# Ctrl+C: clean up and exit immediately
trap 'cleanup_widget; echo -e "\n${RED}✗${NC}  Cancelled by user."; exit 130' INT TERM

# On error: log context and point user to the log file
trap 'echo -e "\n${RED}✗${NC}  Error on line ${LINENO} (exit code $?). Log saved to:\n   ${LOGFILE}"' ERR

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

# Split Brewfile into core (auto-install) and pick (interactive)
BREWFILE="${DOTFILES_DIR}/Brewfile"
CORE_BREWFILE=$(mktemp)
PICK_LINES=()
PICK_LABELS=()
PICK_SELECTED=()
PICK_SECTIONS=()

# Always include taps
grep '^tap ' "$BREWFILE" > "$CORE_BREWFILE"

current_section=""
while IFS= read -r line; do
  # Track section headers from comments
  if [[ "$line" =~ ^#\ =+ ]]; then
    continue
  elif [[ "$line" =~ ^#\ ([A-Z][A-Za-z\ \&/,\(\)\-]+) ]]; then
    current_section="${BASH_REMATCH[1]}"
    # Strip [pick] marker from section headers
    current_section="${current_section% \[pick\]}"
    current_section="${current_section% }"
    continue
  fi

  # Skip empty, comments, taps
  [[ -z "$line" ]] && continue
  [[ "$line" =~ ^# ]] && continue
  [[ "$line" =~ ^tap\  ]] && continue

  if [[ "$line" =~ \[pick\] ]]; then
    # Extract name and description (strip [pick] marker)
    local_name=""
    local_desc=""
    if [[ "$line" =~ ^(brew|cask|mas)\ +\"([^\"]+)\" ]]; then
      local_name="${BASH_REMATCH[2]}"
    fi
    if [[ "$line" =~ \#\ *(.+)\ *\[pick\] ]]; then
      local_desc="${BASH_REMATCH[1]}"
    fi
    [[ -z "$local_name" ]] && continue

    # Strip [pick] from the line for the actual Brewfile
    clean_line=$(echo "$line" | sed 's/ *\[pick\]//')
    PICK_LINES+=("$clean_line")
    if [[ -n "$local_desc" ]]; then
      PICK_LABELS+=("${local_name} — ${local_desc}")
    else
      PICK_LABELS+=("${local_name}")
    fi
    PICK_SELECTED+=(1)

    if [[ -n "$current_section" ]]; then
      PICK_SECTIONS+=("$current_section")
      current_section=""
    else
      PICK_SECTIONS+=("")
    fi
  else
    # Core package — always install
    echo "$line" >> "$CORE_BREWFILE"
  fi
done < "$BREWFILE"

TOTAL_PICK=${#PICK_LINES[@]}

# Install core packages first (no interaction needed)
info "Installing core CLI tools and runtimes..."
brew bundle --file="$CORE_BREWFILE" --verbose || warn "Some core packages failed"
rm -f "$CORE_BREWFILE"
success "Core packages installed"

# Interactive picker for apps
echo ""
info "Select which apps to install (${TOTAL_PICK} available)."
info "All are selected by default. Deselect what you don't need."
echo ""
info "↑/↓ move  SPACE toggle  a select all  n deselect all  ENTER confirm"
echo ""

_picker_height=0

_draw_picker() {
  local current=$1 rows
  rows=$(tput lines 2>/dev/null || echo 40)

  local max_visible=$((rows - 10))
  [[ $max_visible -lt 10 ]] && max_visible=10
  [[ $max_visible -gt $TOTAL_PICK ]] && max_visible=$TOTAL_PICK

  local visible_start=$((current - max_visible / 2))
  [[ $visible_start -lt 0 ]] && visible_start=0
  local visible_end=$((visible_start + max_visible))
  [[ $visible_end -gt $TOTAL_PICK ]] && visible_end=$TOTAL_PICK
  [[ $visible_start -gt $((TOTAL_PICK - max_visible)) ]] && visible_start=$((TOTAL_PICK - max_visible))
  [[ $visible_start -lt 0 ]] && visible_start=0

  # Count how many lines this draw will produce (items + section headers)
  local total_lines=0
  for ((i=visible_start; i<visible_end; i++)); do
    [[ -n "${PICK_SECTIONS[$i]}" ]] && total_lines=$((total_lines + 1))
    total_lines=$((total_lines + 1))
  done

  # On redraw, move up the fixed height (padded from previous draw)
  if [[ "${2:-}" == "redraw" ]]; then
    printf '\033[%dA' "$_picker_height"
  fi

  # Set fixed height to the max we'll ever need (first draw sets it)
  [[ $total_lines -gt $_picker_height ]] && _picker_height=$total_lines

  local drawn=0
  for ((i=visible_start; i<visible_end; i++)); do
    if [[ -n "${PICK_SECTIONS[$i]}" ]]; then
      printf '\r\033[K'
      echo -e "  ${BOLD}${CYAN}── ${PICK_SECTIONS[$i]} ──${NC}"
      drawn=$((drawn + 1))
    fi

    local check=" "
    [[ "${PICK_SELECTED[$i]}" -eq 1 ]] && check="${GREEN}✓${NC}" || check=" "
    local ptr="  "
    [[ "$i" -eq "$current" ]] && ptr="${YELLOW}▸${NC} " || ptr="  "
    printf '\r\033[K'
    echo -e "${ptr}[${check}] ${PICK_LABELS[$i]}"
    drawn=$((drawn + 1))
  done

  # Pad with empty lines to maintain fixed height
  while [[ $drawn -lt $_picker_height ]]; do
    printf '\r\033[K\n'
    drawn=$((drawn + 1))
  done
}

_cur=0
_draw_picker $_cur "first"

while true; do
  IFS= read -rsn1 key </dev/tty
  case "$key" in
    $'\x1b')
      read -rsn2 seq </dev/tty
      case "$seq" in
        '[A') [[ $_cur -gt 0 ]] && _cur=$((_cur - 1)) ;;
        '[B') [[ $_cur -lt $((TOTAL_PICK - 1)) ]] && _cur=$((_cur + 1)) ;;
      esac
      _draw_picker $_cur "redraw"
      ;;
    ' ')
      [[ "${PICK_SELECTED[$_cur]}" -eq 1 ]] && PICK_SELECTED[$_cur]=0 || PICK_SELECTED[$_cur]=1
      _draw_picker $_cur "redraw"
      ;;
    'a')
      for ((i=0; i<TOTAL_PICK; i++)); do PICK_SELECTED[$i]=1; done
      _draw_picker $_cur "redraw"
      ;;
    'n')
      for ((i=0; i<TOTAL_PICK; i++)); do PICK_SELECTED[$i]=0; done
      _draw_picker $_cur "redraw"
      ;;
    '')
      break
      ;;
  esac
done

echo ""

# Build temp Brewfile with taps + selected apps
PICK_BREWFILE=$(mktemp)
grep '^tap ' "$BREWFILE" > "$PICK_BREWFILE"
selected_count=0
for ((i=0; i<TOTAL_PICK; i++)); do
  if [[ "${PICK_SELECTED[$i]}" -eq 1 ]]; then
    echo "${PICK_LINES[$i]}" >> "$PICK_BREWFILE"
    selected_count=$((selected_count + 1))
  fi
done

info "Installing ${selected_count} selected apps..."
brew bundle --file="$PICK_BREWFILE" --verbose || warn "Some packages failed to install via Homebrew"
rm -f "$PICK_BREWFILE"

# Retry failed casks with direct download as fallback
declare -A DIRECT_DOWNLOADS=(
  ["bitwarden"]="https://vault.bitwarden.com/download/?app=desktop&platform=macos|Bitwarden.dmg"
  ["1password"]="https://downloads.1password.com/mac/1Password.dmg|1Password.dmg"
  ["ecamm-live"]="https://www.ecamm.com/cgi-bin/customercenter?action=download&product=ecammlive&platform=mac|EcammLive.zip"
)

for ((i=0; i<TOTAL_PICK; i++)); do
  [[ "${PICK_SELECTED[$i]}" -eq 1 ]] || continue
  # Extract cask name from the line
  if [[ "${PICK_LINES[$i]}" =~ ^cask\ +\"([^\"]+)\" ]]; then
    cask_name="${BASH_REMATCH[1]}"
    # Check if brew installed it
    if ! brew list --cask "$cask_name" &>/dev/null; then
      fallback="${DIRECT_DOWNLOADS[$cask_name]+${DIRECT_DOWNLOADS[$cask_name]}}"
      if [[ -n "$fallback" ]]; then
        url="${fallback%%|*}"
        filename="${fallback#*|}"
        warn "${cask_name} failed via Homebrew. Trying direct download..."
        if curl -fsSL -o "$HOME/Downloads/${filename}" "$url" 2>/dev/null; then
          if [[ "$filename" == *.dmg ]]; then
            open "$HOME/Downloads/${filename}"
            success "Downloaded ${cask_name} to ~/Downloads. Install from the opened DMG."
          elif [[ "$filename" == *.zip ]]; then
            unzip -qo "$HOME/Downloads/${filename}" -d /Applications/ 2>/dev/null \
              && success "${cask_name} installed from direct download" \
              || open "$HOME/Downloads/${filename}"
          fi
        else
          warn "Direct download also failed for ${cask_name}. Install manually."
        fi
      fi
    fi
  fi
done

success "Brewfile processing complete (${selected_count} apps selected)"

# Start Xcode download in the background (~12GB, takes a while)
XCODE_PID=""
if ! [[ -d "/Applications/Xcode.app" ]] && [[ -z "${XCODE_PID:-}" ]]; then
  if command -v xcodes &>/dev/null; then
    info "Starting Xcode download in the background via xcodes + aria2 (~12GB)..."
    xcodes install --latest --experimental-unxip &
    XCODE_PID=$!
    success "Xcode downloading (PID: ${XCODE_PID}) — continuing with other steps"
  elif command -v mas &>/dev/null; then
    info "Starting Xcode download in the background via App Store (~12GB)..."
    mas install 497799835 &
    XCODE_PID=$!
    success "Xcode downloading (PID: ${XCODE_PID}) — continuing with other steps"
  else
    warn "Neither xcodes nor mas available. Install Xcode manually from the App Store."
  fi
else
  success "Xcode already installed"
fi

# ===========================================================================
# Step 4: Password Manager Setup
# ===========================================================================
section "Password Manager"

# Bitwarden
if [[ -d "/Applications/Bitwarden.app" ]]; then
  success "Bitwarden app installed"
  info "Please sign in to Bitwarden now if you haven't already."
  echo ""
  if ask "Open Bitwarden to sign in?"; then
    open -a "Bitwarden" 2>/dev/null || warn "Could not open Bitwarden"
    warn "Press ENTER after you've signed in to Bitwarden."
    read -r </dev/tty
    success "Bitwarden ready"
  fi

  # Set up Bitwarden CLI
  if command -v bw &>/dev/null; then
    if bw status 2>/dev/null | grep -q '"status":"unlocked"'; then
      success "Bitwarden CLI already unlocked"
    else
      info "Log in to Bitwarden CLI with: bw login"
      warn "Then unlock with: export BW_SESSION=\$(bw unlock --raw)"
    fi
  fi
else
  warn "Bitwarden not found. Install Homebrew packages first (Step 3)."
fi

# 1Password (legacy)
if [[ -d "/Applications/1Password.app" ]]; then
  success "1Password app installed (legacy)"
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

# zsh-syntax-highlighting plugin
if [[ -d "${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting" ]]; then
  success "zsh-syntax-highlighting already installed"
else
  info "Installing zsh-syntax-highlighting..."
  git clone https://github.com/zsh-users/zsh-syntax-highlighting "${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting" || {
    warn "Failed to clone zsh-syntax-highlighting. Check network and retry."
  }
  [[ -d "${ZSH_CUSTOM}/plugins/zsh-syntax-highlighting" ]] && success "zsh-syntax-highlighting installed"
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

  # Set git identity in ~/.gitconfig.local (per-machine, not tracked)
  GIT_LOCAL="$HOME/.gitconfig.local"
  if [[ -f "$GIT_LOCAL" ]]; then
    info "Git identity already set in ~/.gitconfig.local"
    info "  name:  $(git config --global user.name 2>/dev/null || echo '(not set)')"
    info "  email: $(git config --global user.email 2>/dev/null || echo '(not set)')"
  else
    read -rp "Git full name (e.g. Warren de Leon): " GIT_NAME </dev/tty
    read -rp "Git email (e.g. hi@warrendeleon.com): " GIT_EMAIL </dev/tty
    cat > "$GIT_LOCAL" << GITEOF
[user]
	name = ${GIT_NAME}
	email = ${GIT_EMAIL}
GITEOF
    success "Git identity saved to ~/.gitconfig.local"
  fi

  # SSH config
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  symlink "${DOTFILES_DIR}/ssh/config"         "$HOME/.ssh/config"

  success "All dotfiles linked"
else
  warn "Skipped dotfiles. Link manually later."
fi

# ===========================================================================
# Step 7: Secrets
# ===========================================================================
section "Secrets"

LOCAL_SECRETS="${DOTFILES_DIR}/secrets/.secrets.env"
ICLOUD_SECRETS="$HOME/Library/Mobile Documents/com~apple~CloudDocs/.secrets.env"

if [[ -f "$HOME/.secrets.env" ]]; then
  success "~/.secrets.env already exists"
elif [[ -f "$LOCAL_SECRETS" ]]; then
  info "Found secrets in dotfiles (secrets/.secrets.env)"
  cp "$LOCAL_SECRETS" "$HOME/.secrets.env"
  chmod 600 "$HOME/.secrets.env"
  success "Copied ~/.secrets.env from dotfiles (permissions: 600)"
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

  # JetBrains Mono (WebStorm/VS Code editor font with ligatures)
  if [[ ! -f "${FONT_DIR}/JetBrainsMono-Regular.ttf" ]]; then
    info "Downloading JetBrains Mono font..."
    JB_MONO_URL="https://github.com/JetBrains/JetBrainsMono/releases/latest/download/JetBrainsMono-2.304.zip"
    JB_MONO_TMP=$(mktemp -d)
    curl -fsSL "$JB_MONO_URL" -o "$JB_MONO_TMP/jbmono.zip" 2>/dev/null && \
      unzip -qo "$JB_MONO_TMP/jbmono.zip" -d "$JB_MONO_TMP" 2>/dev/null && \
      cp "$JB_MONO_TMP"/fonts/ttf/*.ttf "$FONT_DIR/" 2>/dev/null && \
      success "JetBrains Mono installed" || \
      warn "Failed to download JetBrains Mono"
    rm -rf "$JB_MONO_TMP"
  else
    success "JetBrains Mono already installed"
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

  if ask "Install gitmoji-cli?"; then
    npm install -g gitmoji-cli
    success "gitmoji-cli installed"
  fi

  if ask "Install Claude Code (AI coding assistant)?"; then
    npm install -g @anthropic-ai/claude-code
    CLAUDE_CODE_INSTALLED=true
    success "Claude Code installed"
  fi

  if ask "Install Amazon Q / Kiro CLI (AI coding assistant)?"; then
    brew install --cask kiro-cli
    success "Kiro CLI installed (formerly Amazon Q)"
  fi
else
  warn "npm not found. Install Node.js first (Step 9)."
fi

# ---------------------------------------------------------------------------
# Claude Code Configuration
# ---------------------------------------------------------------------------
if command -v claude &>/dev/null || [[ "${CLAUDE_CODE_INSTALLED:-}" == "true" ]]; then
  info "Configuring Claude Code..."

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
  # Symlink global docs
  if [[ -d "${DOTFILES_DIR}/claude/docs" ]]; then
    symlink "${DOTFILES_DIR}/claude/docs" "$HOME/.claude/docs"
  fi
  success "Claude Code configured"
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
# Step 15: SSH Key (from iCloud Drive)
# ===========================================================================
section "SSH Key"

SSH_KEY="$HOME/.ssh/id_rsa"
LOCAL_SSH="${DOTFILES_DIR}/secrets/id_rsa"
ICLOUD_SSH="$HOME/Library/Mobile Documents/com~apple~CloudDocs/ssh/id_rsa"

if [[ -f "$SSH_KEY" ]]; then
  success "SSH key already exists (${SSH_KEY})"
else
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"

  # Pick the first available source: dotfiles local copy, then iCloud
  SSH_SOURCE=""
  if [[ -f "$LOCAL_SSH" ]]; then
    SSH_SOURCE="$LOCAL_SSH"
    info "Found SSH key in dotfiles (secrets/id_rsa)"
  elif [[ -f "$ICLOUD_SSH" ]]; then
    SSH_SOURCE="$ICLOUD_SSH"
    info "Found SSH key in iCloud Drive"
  fi

  if [[ -n "$SSH_SOURCE" ]]; then
    cp "$SSH_SOURCE" "$SSH_KEY"
    chmod 600 "$SSH_KEY"

    # Derive public key from private key
    ssh-keygen -y -f "$SSH_KEY" > "${SSH_KEY}.pub"
    chmod 644 "${SSH_KEY}.pub"

    # Add to macOS keychain
    eval "$(ssh-agent -s)"
    ssh-add --apple-use-keychain "$SSH_KEY"

    success "SSH key installed and added to keychain"
    echo ""
    info "Public key:"
    cat "${SSH_KEY}.pub"
  else
    warn "SSH key not found in dotfiles (secrets/id_rsa) or iCloud Drive"
    info "To use an existing key: cp ~/.ssh/id_rsa ${DOTFILES_DIR}/secrets/id_rsa"
    echo ""
    if ask "Generate a new RSA SSH key instead?"; then
      GIT_EMAIL_FOR_SSH=$(git config --global user.email 2>/dev/null || echo "")
      ssh-keygen -t rsa -b 4096 -C "${GIT_EMAIL_FOR_SSH:-$(whoami)@$(hostname)}" -f "$SSH_KEY"
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
  # Back up existing profile outside DynamicProfiles dir (iTerm2 reads all JSON in this dir)
  if [[ -f "$ITERM_PROFILES_DIR/Default.json" ]]; then
    cp "$ITERM_PROFILES_DIR/Default.json" "${DOTFILES_DIR}/iterm2/Default.json.backup.$(date +%Y%m%d_%H%M%S)"
  fi
  sed "s|__HOME_DIR__|${HOME}|g" "${DOTFILES_DIR}/iterm2/Default.json" > "$ITERM_PROFILES_DIR/Default.json"
  success "Dynamic profile installed (home directory: ${HOME})"

  # Set iTerm2 preferences via defaults
  defaults write com.googlecode.iterm2 "Default Bookmark Guid" -string "dotfiles-profile"

  # Appearance: compact tabs
  defaults write com.googlecode.iterm2 TabViewType -int 1
  defaults write com.googlecode.iterm2 HideTab -bool false
  defaults write com.googlecode.iterm2 AlternateMouseScroll -bool true

  # No annoying prompts on quit
  defaults write com.googlecode.iterm2 PromptOnQuit -bool false
  defaults write com.googlecode.iterm2 OnlyWhenMoreTabs -bool false

  success "iTerm2 preferences set"
fi

# ---------------------------------------------------------------------------
# VS Code Configuration
# ---------------------------------------------------------------------------
VSCODE_USER_DIR="$HOME/Library/Application Support/Code/User"

if [[ -d "/Applications/Visual Studio Code.app" ]] || command -v code &>/dev/null; then
  if ask "Configure VS Code (settings, extensions)?"; then
    mkdir -p "$VSCODE_USER_DIR"

    # Back up existing settings
    if [[ -f "$VSCODE_USER_DIR/settings.json" ]]; then
      cp "$VSCODE_USER_DIR/settings.json" "$VSCODE_USER_DIR/settings.json.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    cp "${DOTFILES_DIR}/vscode/settings.json" "$VSCODE_USER_DIR/settings.json"
    success "VS Code settings installed"

    # Install extensions
    if command -v code &>/dev/null; then
      while IFS= read -r ext; do
        [[ -z "$ext" ]] && continue
        code --install-extension "$ext" --force 2>/dev/null || warn "Failed to install $ext"
      done < "${DOTFILES_DIR}/vscode/extensions.txt"
      success "VS Code extensions installed"
    else
      info "Install 'code' CLI: VS Code → Cmd+Shift+P → 'Shell Command: Install'"
    fi
  fi
fi

# ---------------------------------------------------------------------------
# WebStorm Configuration
# ---------------------------------------------------------------------------
WEBSTORM_DIR=$(ls -1d "$HOME/Library/Application Support/JetBrains/WebStorm"* 2>/dev/null | sort -V | tail -1 || true)

if [[ -n "$WEBSTORM_DIR" ]]; then
  if ask "Configure WebStorm (fonts, keymap)?"; then
    # Editor font (JetBrains Mono with ligatures)
    cp "${DOTFILES_DIR}/webstorm/editor-font.xml" "$WEBSTORM_DIR/options/editor-font.xml"
    success "WebStorm editor font set to JetBrains Mono 13pt"

    # Terminal font (MesloLGS NF for Powerlevel10k)
    cp "${DOTFILES_DIR}/webstorm/console-font.xml" "$WEBSTORM_DIR/options/console-font.xml"
    success "WebStorm terminal font set to MesloLGS NF"

    # Raycast Compatible keymap (frees Ctrl+Option+Arrow)
    mkdir -p "$WEBSTORM_DIR/keymaps"
    cp "${DOTFILES_DIR}/webstorm/Raycast Compatible.xml" "$WEBSTORM_DIR/keymaps/Raycast Compatible.xml"
    success "WebStorm 'Raycast Compatible' keymap installed"
    info "Select it in: Settings → Keymap → Raycast Compatible"
  fi
else
  info "WebStorm not installed yet — run this again after first launch"
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

  # Set machine hostname (macOS + Tailscale together)
  CURRENT_HOSTNAME=$(scutil --get ComputerName 2>/dev/null || hostname -s)
  info "Current machine name: ${CURRENT_HOSTNAME}"
  read -rp "Enter new hostname (or press ENTER to keep '${CURRENT_HOSTNAME}'): " NEW_HOSTNAME </dev/tty
  if [[ -n "$NEW_HOSTNAME" ]]; then
    # macOS has three hostname layers
    sudo scutil --set ComputerName "$NEW_HOSTNAME"
    sudo scutil --set LocalHostName "$NEW_HOSTNAME"
    sudo scutil --set HostName "$NEW_HOSTNAME"
    success "macOS hostname set to: ${NEW_HOSTNAME}"

    # Match Tailscale hostname
    if "$TAILSCALE_CLI" status &>/dev/null 2>&1; then
      "$TAILSCALE_CLI" set --hostname="$NEW_HOSTNAME" || warn "Could not set Tailscale hostname."
      success "Tailscale hostname set to: ${NEW_HOSTNAME}"
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

# Register this Mac with iMessage sync on the homelab server
if ask "Register this Mac with iMessage sync on the homelab server?"; then
  TAILSCALE_IP=$("$TAILSCALE_CLI" ip -4 2>/dev/null || true)
  if [[ -n "$TAILSCALE_IP" ]]; then
    IMESSAGE_ENTRY="$(whoami)@${TAILSCALE_IP}"
    MONDAY_ENV="/home/warren/homelab/stacks/monday/.env"
    if ssh -o ConnectTimeout=10 -o BatchMode=yes minipc "grep -q '${TAILSCALE_IP}' ${MONDAY_ENV}" 2>/dev/null; then
      success "Already registered: ${IMESSAGE_ENTRY}"
    else
      if ssh -o ConnectTimeout=10 -o BatchMode=yes minipc "sed -i 's|^MACS=.*|&,${IMESSAGE_ENTRY}|' ${MONDAY_ENV} && cd /home/warren/homelab/stacks/monday && docker compose up -d imessage-sync" 2>/dev/null; then
        success "Registered ${IMESSAGE_ENTRY} with iMessage sync and restarted container"
      else
        warn "Could not register. Add manually: ${IMESSAGE_ENTRY} to MACS in ${MONDAY_ENV}"
      fi
    fi
  else
    warn "Could not get Tailscale IP. Connect to Tailscale first."
  fi
fi

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
    sudo tee /etc/pam.d/sudo_local > /dev/null << 'EOF'
# sudo_local: local config for sudo (survives macOS updates)
auth       sufficient     pam_tid.so
EOF
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

# Import BetterDisplay display profiles (resolutions, brightness, DDC settings)
BETTERDISPLAY_PLIST="${DOTFILES_DIR}/betterdisplay/BetterDisplay.plist"
if [[ -f "$BETTERDISPLAY_PLIST" ]]; then
  defaults import me.waydabber.BetterDummy "$BETTERDISPLAY_PLIST"
  success "BetterDisplay display profiles imported"
fi

# Import Amphetamine preferences
AMPHETAMINE_PLIST="${DOTFILES_DIR}/amphetamine/Amphetamine.plist"
if [[ -f "$AMPHETAMINE_PLIST" ]]; then
  defaults import com.if.Amphetamine "$AMPHETAMINE_PLIST"
  success "Amphetamine preferences imported"
fi

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
  brew autoupdate start --upgrade --cleanup --immediate 2>/dev/null \
    && success "Auto-updates enabled (daily, immediate, on system boot)" \
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
# Git Maintenance (all repos in ~/Developer)
# ===========================================================================
info "Enabling git maintenance for all repos in ~/Developer..."
find "$HOME/Developer" -maxdepth 3 -name ".git" -type d 2>/dev/null | while read gitdir; do
  repo=$(dirname "$gitdir")
  git -C "$repo" maintenance start 2>/dev/null && echo "  ✓ $(basename "$repo")" || true
done
success "Git maintenance enabled (background prefetch, commit-graph, loose-objects)"

# ===========================================================================
# Weekly Cleanup (launchd)
# ===========================================================================
CLEANUP_SCRIPT="${DOTFILES_DIR}/scripts/weekly-cleanup.sh"
CLEANUP_PLIST_SRC="${DOTFILES_DIR}/scripts/com.dotfiles.weekly-cleanup.plist"
CLEANUP_PLIST_DST="$HOME/Library/LaunchAgents/com.dotfiles.weekly-cleanup.plist"

if [[ -f "$CLEANUP_SCRIPT" ]]; then
  chmod +x "$CLEANUP_SCRIPT"
  mkdir -p "$HOME/Library/LaunchAgents"
  sed "s|__HOME__|$HOME|g" "$CLEANUP_PLIST_SRC" > "$CLEANUP_PLIST_DST"
  launchctl unload "$CLEANUP_PLIST_DST" 2>/dev/null || true
  launchctl load "$CLEANUP_PLIST_DST"
  success "Weekly cleanup enabled (every 7 days, catches up after boot)"
fi

# ===========================================================================
# Step 28: RAG System (Local Semantic Search)
# ===========================================================================
section "RAG System"

RAG_DIR="${DOTFILES_DIR}/rag"
RAG_HOME="$HOME/.rag"

if ! command -v claude &>/dev/null && [[ "${CLAUDE_CODE_INSTALLED:-}" != "true" ]]; then
  info "Skipping RAG system (Claude Code not installed)"
elif [[ -d "$RAG_DIR" ]]; then
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

    # Create Python virtual environment (chromadb requires Python ≤3.13)
    if [[ ! -d "$RAG_HOME/venv" ]]; then
      info "Creating Python virtual environment..."
      PYTHON_313="/opt/homebrew/opt/python@3.13/bin/python3.13"
      if [[ -x "$PYTHON_313" ]]; then
        "$PYTHON_313" -m venv "$RAG_HOME/venv"
      else
        warn "Python 3.13 not found at $PYTHON_313 — falling back to python3 (chromadb may fail on 3.14+)"
        python3 -m venv "$RAG_HOME/venv"
      fi
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
      # Replace placeholder with current user's home directory
      sed "s|__HOME__|$HOME|g" "$plist" > "$target"
      launchctl load "$target"
      success "Loaded $plist_name"
    done

    # Create wrapper script (Claude Code doesn't reliably apply cwd)
    cat > "$RAG_HOME/start-server.sh" <<WRAPEOF
#!/bin/bash
cd "$RAG_DIR"
exec "$RAG_HOME/venv/bin/python" -m src.server "\$@"
WRAPEOF
    chmod +x "$RAG_HOME/start-server.sh"
    success "Created server wrapper at $RAG_HOME/start-server.sh"

    # Register MCP server with Claude Code
    # Claude Code reads MCP config from ~/.claude.json under mcpServers
    CLAUDE_JSON="$HOME/.claude.json"
    if [[ -f "$CLAUDE_JSON" ]]; then
      python3 -c "
import json, pathlib
p = pathlib.Path('$CLAUDE_JSON')
cfg = json.loads(p.read_text()) if p.stat().st_size > 0 else {}
cfg.setdefault('mcpServers', {})
cfg['mcpServers']['rag'] = {
    'type': 'stdio',
    'command': '$RAG_HOME/start-server.sh',
    'args': [],
    'env': {
        'ANONYMIZED_TELEMETRY': 'false',
        'CHROMA_TELEMETRY': 'false'
    }
}
p.write_text(json.dumps(cfg, indent=2) + '\n')
" 2>/dev/null && success "MCP server registered in $CLAUDE_JSON" \
        || warn "MCP registration failed. Add rag entry to $CLAUDE_JSON manually."
    else
      cat > "$CLAUDE_JSON" <<MCPEOF
{
  "mcpServers": {
    "rag": {
      "type": "stdio",
      "command": "$RAG_HOME/start-server.sh",
      "args": [],
      "env": {
        "ANONYMIZED_TELEMETRY": "false",
        "CHROMA_TELEMETRY": "false"
      }
    }
  }
}
MCPEOF
      success "MCP server registered (created $CLAUDE_JSON)"
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
