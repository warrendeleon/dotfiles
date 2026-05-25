#!/usr/bin/env bash
# Multi-machine sync for Claude Code conversation history.
#
# This script rsyncs ~/.claude/projects/ to a hub host (a personal mini PC
# running Ubuntu, reached on LAN or via Tailscale), then pulls down trees from
# every other machine that syncs to the same hub. The watcher on each machine
# picks up the foreign JSONLs and indexes them, so RAG search returns results
# from every machine you use.
#
# NOT FOR YOU IF you only use one machine, or you don't have a hub box to
# centralise on. To disable:
#   1. Don't install the launchd plist for this script (skip the sync step in
#      setup.sh, or remove the rag-sync .plist install block).
#   2. Or: leave the script in place but never load the plist. The watcher and
#      indexer don't depend on it.
#
# If you want the same idea against your own hub, change SSH_HOSTS below and
# make sure the target accepts your SSH key. The hub just needs rsync and a
# writable directory at $HUB_SYNC_DIR.
set -euo pipefail

CLAUDE_PROJECTS="$HOME/.claude/projects"
RAG_HOME="$HOME/.rag"
SYNC_STATE="$RAG_HOME/sync"
MACHINE_ID_FILE="$RAG_HOME/machine-id"
FOREIGN_MANIFEST="$SYNC_STATE/foreign-files.txt"
LOCKDIR="$SYNC_STATE/sync.lock"
LOGFILE="$RAG_HOME/logs/sync.log"
HUB_SYNC_DIR="claude-sync"
SSH_HOSTS=("minipc-lan" "minipc-tailscale")
CONNECT_TIMEOUT=5
RSYNC_TIMEOUT=60

RSYNC_EXCLUDE_PATTERNS=(
    "*-dotfiles-rag*"
)

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOGFILE"
}

acquire_lock() {
    mkdir "$LOCKDIR" 2>/dev/null || {
        log "Another sync is running, skipping"
        exit 0
    }
    trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT
}

ensure_machine_id() {
    if [[ ! -f "$MACHINE_ID_FILE" ]]; then
        hostname -s > "$MACHINE_ID_FILE"
        log "Created machine-id: $(cat "$MACHINE_ID_FILE")"
    fi
    MACHINE_ID=$(cat "$MACHINE_ID_FILE")
}

find_hub() {
    for host in "${SSH_HOSTS[@]}"; do
        if ssh -o ConnectTimeout="$CONNECT_TIMEOUT" -o BatchMode=yes "$host" true 2>/dev/null; then
            echo "$host"
            return 0
        fi
    done
    return 1
}

ensure_remote_dir() {
    local hub="$1"
    ssh "$hub" "mkdir -p ~/$HUB_SYNC_DIR/$MACHINE_ID"
    echo "$MACHINE_ID" | ssh "$hub" "cat > ~/$HUB_SYNC_DIR/$MACHINE_ID/.machine"
}

push() {
    local hub="$1"

    if [[ ! -d "$CLAUDE_PROJECTS" ]]; then
        log "No projects directory, skipping push"
        return 0
    fi

    local exclude_args=()
    for pattern in "${RSYNC_EXCLUDE_PATTERNS[@]}"; do
        exclude_args+=(--exclude "$pattern")
    done

    if [[ -s "$FOREIGN_MANIFEST" ]]; then
        exclude_args+=(--exclude-from "$FOREIGN_MANIFEST")
    fi

    local count
    count=$(rsync -azn --itemize-changes \
        "${exclude_args[@]}" \
        --include='*/' \
        --include='*.jsonl' \
        --exclude='*' \
        --timeout="$RSYNC_TIMEOUT" \
        "$CLAUDE_PROJECTS/" \
        "$hub:~/$HUB_SYNC_DIR/$MACHINE_ID/" 2>/dev/null | grep -c '^<f' || true)

    if [[ "$count" -gt 0 ]]; then
        rsync -az \
            "${exclude_args[@]}" \
            --include='*/' \
            --include='*.jsonl' \
            --exclude='*' \
            --partial --partial-dir=.rsync-partial \
            --timeout="$RSYNC_TIMEOUT" \
            "$CLAUDE_PROJECTS/" \
            "$hub:~/$HUB_SYNC_DIR/$MACHINE_ID/"
        log "Pushed $count file(s) to hub"
    fi
}

pull() {
    local hub="$1"

    local remote_machines
    remote_machines=$(ssh "$hub" "ls ~/$HUB_SYNC_DIR/ 2>/dev/null" || true)

    if [[ -z "$remote_machines" ]]; then
        return 0
    fi

    for remote_machine in $remote_machines; do
        if [[ "$remote_machine" == "$MACHINE_ID" ]]; then
            continue
        fi

        local new_files
        new_files=$(rsync -azn --itemize-changes \
            --include='*/' \
            --include='*.jsonl' \
            --exclude='*' \
            --timeout="$RSYNC_TIMEOUT" \
            "$hub:~/$HUB_SYNC_DIR/$remote_machine/" \
            "$CLAUDE_PROJECTS/" 2>/dev/null | grep '^>f' | awk '{print $2}' || true)

        if [[ -z "$new_files" ]]; then
            continue
        fi

        rsync -az \
            --include='*/' \
            --include='*.jsonl' \
            --exclude='*' \
            --partial --partial-dir=.rsync-partial \
            --timeout="$RSYNC_TIMEOUT" \
            "$hub:~/$HUB_SYNC_DIR/$remote_machine/" \
            "$CLAUDE_PROJECTS/"

        local pulled=0
        while IFS= read -r relpath; do
            [[ -z "$relpath" ]] && continue
            echo "$relpath" >> "$FOREIGN_MANIFEST"
            pulled=$((pulled + 1))
        done <<< "$new_files"

        if [[ "$pulled" -gt 0 ]]; then
            sort -u -o "$FOREIGN_MANIFEST" "$FOREIGN_MANIFEST"
            log "Pulled $pulled file(s) from $remote_machine"
        fi
    done
}

main() {
    mkdir -p "$SYNC_STATE" "$(dirname "$LOGFILE")"

    # Rotate log if over 1MB
    if [[ -f "$LOGFILE" ]] && [[ $(stat -f%z "$LOGFILE" 2>/dev/null || stat -c%s "$LOGFILE" 2>/dev/null || echo 0) -gt 1048576 ]]; then
        tail -100 "$LOGFILE" > "$LOGFILE.tmp" && mv "$LOGFILE.tmp" "$LOGFILE"
    fi

    acquire_lock
    ensure_machine_id
    touch "$FOREIGN_MANIFEST"

    local hub
    hub=$(find_hub) || {
        log "Hub unreachable, skipping"
        exit 0
    }

    ensure_remote_dir "$hub"
    push "$hub"
    pull "$hub"
    log "Sync complete"
}

main "$@"
