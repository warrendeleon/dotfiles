#!/bin/bash
set -u

# Load NAS configuration from ~/.secrets.env. Required vars:
#   NAS_USER             SMB username
#   NAS_LAN_HOST         private LAN address (e.g. 192.168.10.2)
#   NAS_TAILSCALE_HOST   Tailscale MagicDNS name for off-LAN access
#   NAS_SHARES           space-separated share names (e.g. "video home")
#
# Tries LAN first (no Tailscale dependency at home), falls back to Tailscale.
[[ -f "$HOME/.secrets.env" ]] && source "$HOME/.secrets.env"

NAS_DIR="$HOME/NAS"
LOG="$HOME/Library/Logs/mount-nas.log"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"; }

if [[ -z "${NAS_USER:-}" || -z "${NAS_LAN_HOST:-}${NAS_TAILSCALE_HOST:-}" ]]; then
  log "NAS_USER and at least one of NAS_LAN_HOST/NAS_TAILSCALE_HOST must be set in ~/.secrets.env; not mounting"
  exit 0
fi

ADDRESSES=()
[[ -n "${NAS_LAN_HOST:-}" ]] && ADDRESSES+=("$NAS_LAN_HOST")
[[ -n "${NAS_TAILSCALE_HOST:-}" ]] && ADDRESSES+=("$NAS_TAILSCALE_HOST")

# shellcheck disable=SC2206
SHARES=(${NAS_SHARES:-video home})
USER_NAME="$NAS_USER"

pick_server() {
  for srv in "${ADDRESSES[@]}"; do
    if /sbin/ping -c1 -W1000 "$srv" >/dev/null 2>&1; then
      echo "$srv"
      return 0
    fi
  done
  return 1
}

is_mounted() { /sbin/mount | grep -q " on $1 "; }

mkdir -p "$NAS_DIR"

log "starting mount-nas"
SERVER=$(pick_server)
if [[ -z "$SERVER" ]]; then
  log "no reachable NAS address; giving up"
  exit 1
fi
log "using server: $SERVER"

for s in "${SHARES[@]}"; do
  target="/Volumes/$s"
  if is_mounted "$target"; then
    log "$s already mounted"
  else
    if /usr/bin/osascript -e "mount volume \"smb://${USER_NAME}@${SERVER}/${s}\"" >>"$LOG" 2>&1; then
      log "mounted $s from $SERVER"
    else
      log "failed to mount $s from $SERVER"
      continue
    fi
  fi
  link="$NAS_DIR/$s"
  if [[ ! -L "$link" || "$(readlink "$link")" != "$target" ]]; then
    rm -f "$link"
    ln -s "$target" "$link"
    log "refreshed symlink $link -> $target"
  fi
done
