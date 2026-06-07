#!/bin/bash
# SessionEnd hook: summarise the session that just finished, in the background,
# so a fresh conversation can resume it without waiting for the timer sweep.
#
# Fires the sweep for this one session id (which bypasses the idle gate). The
# done-ledger means a trivial session costs nothing and a session already
# summarised is skipped. Detached and fail-silent: a summariser problem must
# never delay or block a session ending.

input=$(cat)

# Pull the session id from the SessionEnd payload.
sid=$(printf '%s' "$input" \
  | grep -oE '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' \
  | head -1 \
  | sed -E 's/.*:[[:space:]]*"([^"]*)".*/\1/')
[ -n "$sid" ] || exit 0

RAG_DIR="$HOME/Developer/dotfiles/rag"
PY="$HOME/.rag/venv/bin/python"
LOG="$HOME/.rag/logs/summariser.log"
[ -x "$PY" ] || exit 0
[ -d "$RAG_DIR" ] || exit 0

# Double-fork so the hook returns immediately and the summary runs detached.
( cd "$RAG_DIR" && nohup "$PY" -m src.summarise_sweep --session "$sid" >>"$LOG" 2>&1 & ) >/dev/null 2>&1

exit 0
