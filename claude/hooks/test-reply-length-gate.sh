#!/bin/bash
# Regression checks for reply-length-gate.sh: build a transcript, run the hook,
# and compare allow (no output) or block (a JSON decision) with the expectation.
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reply-length-gate.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fails=0

# Records: H:<text> human, A:<n> assistant prose of n words, N notification.
check() {
  local name=$1 expect=$2; shift 2
  local transcript="$TMP/$name.jsonl"
  : > "$transcript"
  for r in "$@"; do
    python3 - "$r" >> "$transcript" <<'PY'
import json, sys
r = sys.argv[1]
if r.startswith("H:"):
    print(json.dumps({"type": "user", "message": {"role": "user", "content": r[2:]}}))
elif r.startswith("A:"):
    print(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": " ".join(["word"] * int(r[2:]))}]}}))
elif r == "N":
    print(json.dumps({"type": "user", "message": {"role": "user", "content": "<task-notification>\n<task-id>x</task-id>\n<status>completed</status>\n</task-notification>"}}))
PY
  done
  local out
  out=$(python3 -c 'import json,sys;print(json.dumps({"transcript_path":sys.argv[1]}))' "$transcript" | "$HOOK")
  local got=allow
  [ -n "$out" ] && got=block
  if [ "$got" = "$expect" ]; then echo "ok   $name"; else echo "FAIL $name: expected $expect, got $got"; fails=$((fails + 1)); fi
}

check short-reply           allow "H:is it done?" "A:20"
check long-reply            block "H:is it done?" "A:200"
check long-ask-allowed      allow "H:explain how the gate works" "A:200"
check long-human-allowed    allow "H:$(printf 'w %.0s' {1..40})" "A:200"
# 2 Oct 2026: one-line replies to several agent notifications were summed and bounced.
check notifications-reset   allow "H:is it done?" "A:60" "N" "A:60" "N" "A:60" "N" "A:20"
check long-after-notif      block "H:is it done?" "A:20" "N" "A:200"

exit $fails
