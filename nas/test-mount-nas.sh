#!/bin/bash
# Regression checks for mount-nas.sh: a NAS that can't be reached or can't be
# mounted must be logged and skipped, never raised as a Finder error dialog.
# Runs the script under a throwaway HOME so the real log and ~/NAS are untouched.
set -uo pipefail
SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/mount-nas.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fails=0

ok()   { echo "ok   $1"; }
fail() { echo "FAIL $1: $2"; fails=$((fails + 1)); }

# run <name> <lan host>: run the script against a fake config, print its log
run() {
  local home="$TMP/$1"
  mkdir -p "$home/Library/Logs"
  printf 'NAS_USER=nobody\nNAS_LAN_HOST=%s\nNAS_SHARES=nas-test-share\n' "$2" > "$home/.secrets.env"
  HOME="$home" /bin/bash "$SCRIPT" >/dev/null 2>&1
  cat "$home/Library/Logs/mount-nas.log" 2>/dev/null
}

# AppleScript's "mount volume" shows a modal dialog on failure; it must not come back.
if grep -v '^ *#' "$SCRIPT" | grep -q 'mount volume'; then
  fail no-applescript-mount "script calls AppleScript 'mount volume'"
else
  ok no-applescript-mount
fi

# TEST-NET-1 never answers, so the port probe gives up before any mount.
log=$(run unreachable 192.0.2.1)
if grep -q 'no reachable NAS address' <<<"$log"; then ok unreachable; else fail unreachable "$log"; fi

# Port 445 open but the share can't mount: the NetFS failure is logged quietly.
# Needs File Sharing on this Mac, so localhost answers on 445.
if /usr/bin/nc -z -G 2 127.0.0.1 445 >/dev/null 2>&1; then
  start=$(date +%s)
  log=$(run mount-fails 127.0.0.1)
  took=$(( $(date +%s) - start ))
  if grep -q 'NetFS error' <<<"$log" && grep -q 'failed to mount nas-test-share' <<<"$log"; then
    ok "mount-fails (${took}s)"
  else
    fail mount-fails "$log"
  fi
else
  echo "skip mount-fails: nothing listening on 127.0.0.1:445 (turn on File Sharing to run it)"
fi

# A real mount must be logged as mounted, not failed. Opt-in because it
# unmounts the real share first; the script mounts it again.
# Run with NAS_LIVE_SHARE=home and the NAS reachable.
if [[ -n "${NAS_LIVE_SHARE:-}" ]]; then
  share=$NAS_LIVE_SHARE
  home="$TMP/live"
  mkdir -p "$home/Library/Logs"
  # shellcheck disable=SC1091
  (source "$HOME/.secrets.env"
   printf 'NAS_USER=%s\nNAS_LAN_HOST=%s\nNAS_TAILSCALE_HOST=%s\nNAS_SHARES=%s\n' \
     "$NAS_USER" "${NAS_LAN_HOST:-}" "${NAS_TAILSCALE_HOST:-}" "$share") > "$home/.secrets.env"
  if /sbin/mount | grep -q " on /Volumes/$share " && ! /usr/sbin/diskutil unmount "/Volumes/$share" >/dev/null 2>&1; then
    fail live-mount "/Volumes/$share is busy; close what is using it and rerun"
  else
    HOME="$home" /bin/bash "$SCRIPT" >/dev/null 2>&1
    log=$(cat "$home/Library/Logs/mount-nas.log")
    if grep -q "mounted $share from" <<<"$log" && [[ "$(readlink "$home/NAS/$share")" == "/Volumes/$share" ]]; then
      ok live-mount
    else
      fail live-mount "$log"
    fi
  fi
else
  echo "skip live-mount: set NAS_LIVE_SHARE=<share> to remount a real share"
fi

exit $fails
