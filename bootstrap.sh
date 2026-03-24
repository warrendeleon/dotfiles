#!/usr/bin/env bash
# ===========================================================================
# Bootstrap Script (run from USB drive)
#
# USB drive layout:
#   /Volumes/YOUR_DRIVE/
#     bootstrap.sh        ← this script
#     secrets/
#       id_rsa            ← SSH private key
#       .secrets.env      ← licence keys, API tokens, etc.
#
# Usage:
#   /Volumes/YOUR_DRIVE/bootstrap.sh
# ===========================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BOLD}ℹ${NC}  $1"; }
success() { echo -e "${GREEN}✓${NC}  $1"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $1"; }
error()   { echo -e "${RED}✗${NC}  $1"; exit 1; }

# Guard: macOS only
[[ "$(uname)" == "Darwin" ]] || error "This script only runs on macOS."

# Guard: not root
[[ "$EUID" -ne 0 ]] || error "Do not run with sudo. Run as your normal user."

# Detect USB drive (directory this script lives in)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_SRC="${SCRIPT_DIR}/secrets"

echo ""
echo -e "${BOLD}Mac Bootstrap${NC}"
echo -e "USB drive: ${SCRIPT_DIR}"
echo ""

# ─── Step 1: Xcode Command Line Tools ─────────────────────────────────────
if xcode-select -p &>/dev/null; then
  success "Xcode Command Line Tools already installed"
else
  info "Installing Xcode Command Line Tools..."
  xcode-select --install 2>/dev/null || true
  echo ""
  warn "A system dialog should appear. Install the tools, then press ENTER."
  read -r </dev/tty

  if ! xcode-select -p &>/dev/null; then
    error "Xcode Command Line Tools not found. Install and re-run."
  fi
  success "Xcode Command Line Tools installed"
fi

# ─── Step 2: Clone dotfiles ───────────────────────────────────────────────
DOTFILES_DIR="$HOME/Developer/dotfiles"
mkdir -p "$HOME/Developer"

if [[ -d "$DOTFILES_DIR/.git" ]]; then
  success "Dotfiles already cloned at ${DOTFILES_DIR}"
  info "Pulling latest..."
  git -C "$DOTFILES_DIR" pull --rebase || warn "Pull failed. Continuing with existing copy."
else
  info "Cloning dotfiles..."
  git clone https://github.com/warrendeleon/dotfiles.git "$DOTFILES_DIR"
  success "Cloned to ${DOTFILES_DIR}"
fi

# ─── Step 3: Copy secrets from USB ────────────────────────────────────────
if [[ -d "$SECRETS_SRC" ]]; then
  info "Copying secrets from USB drive..."
  mkdir -p "${DOTFILES_DIR}/secrets"

  for file in "$SECRETS_SRC"/*; do
    [[ -f "$file" ]] || continue
    filename=$(basename "$file")
    cp "$file" "${DOTFILES_DIR}/secrets/${filename}"
    chmod 600 "${DOTFILES_DIR}/secrets/${filename}"
    success "Copied ${filename}"
  done
else
  warn "No secrets/ folder found on USB drive. Skipping."
  info "Expected at: ${SECRETS_SRC}"
fi

# ─── Step 4: Run setup ───────────────────────────────────────────────────
echo ""
success "Bootstrap complete."
echo ""
info "Next step:"
echo "  cd ${DOTFILES_DIR} && ./setup.sh"
echo ""

if read -rp "Run setup.sh now? [y/N] " response </dev/tty; [[ "$response" =~ ^[Yy]$ ]]; then
  cd "$DOTFILES_DIR"
  chmod +x setup.sh
  exec ./setup.sh
fi
