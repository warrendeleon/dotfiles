#!/bin/bash
# Write a verification receipt for one or more deliverables.
#
# The review-loop workflow calls this as its last stage. verify-receipt.sh, the
# PreToolUse gate, refuses to send, post, publish or copy a deliverable unless a
# receipt exists for it with clean=true and a sha256 that still matches the file.
#
# Usage:
#   write-receipt.sh --profile NAME --clean true|false --history JSON path [path ...]
#
# Receipts live in ~/.claude/receipts/, one JSON file per run, newest wins.
set -euo pipefail

profile="" clean="false" history="[]"
paths=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) profile="$2"; shift 2 ;;
    --clean)   clean="$2";   shift 2 ;;
    --history) history="$2"; shift 2 ;;
    *)         paths+=("$1"); shift ;;
  esac
done
[[ ${#paths[@]} -gt 0 ]] || { echo "write-receipt: no paths given" >&2; exit 1; }

dir="$HOME/.claude/receipts"
mkdir -p "$dir"
# Prune receipts older than 30 days; a receipt only ever matches one exact draft.
find "$dir" -name '*.json' -type f -mtime +30 -delete 2>/dev/null || true

PROFILE="$profile" CLEAN="$clean" HISTORY="$history" DIR="$dir" python3 - "${paths[@]}" <<'PY'
import hashlib, json, os, sys, datetime, re

targets = []
for p in sys.argv[1:]:
    p = os.path.realpath(os.path.expanduser(p))
    if not os.path.isfile(p):
        print(f"write-receipt: not a file: {p}", file=sys.stderr); sys.exit(1)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    targets.append({"path": p, "sha256": h})

try:
    history = json.loads(os.environ["HISTORY"])
except Exception:
    history = []
clean = os.environ["CLEAN"].lower() == "true"
rounds = len(history)
# A clean receipt requires the loop's own evidence: the last round was a complete
# re-check (or a discovery round that found nothing at all), every confirmer answered,
# and nothing was confirmed wrong. Anything else is recorded as not clean.
last = history[-1] if history else {}
loop_clean = bool(history) and not last.get("incomplete") and last.get("checked", 0) > 0 \
    and last.get("confirmed", 1) == 0 and last.get("lostConfirms", 0) == 0 \
    and (last.get("mode") == "recheck" or (last.get("mode") == "discover" and last.get("found", 1) == 0))
if clean and not loop_clean:
    clean = False
    note = "clean requested but the history does not show two clean rounds"
else:
    note = ""

now = datetime.datetime.now().astimezone()
slug = re.sub(r"[^a-z0-9]+", "-", os.path.basename(targets[0]["path"]).lower()).strip("-")[:40]
out = os.path.join(os.environ["DIR"], f"{now.strftime('%Y%m%dT%H%M%S')}-{slug}.json")
json.dump({
    "when": now.isoformat(timespec="seconds"),
    "profile": os.environ["PROFILE"],
    "clean": clean,
    "rounds": rounds,
    "history": history,
    "targets": targets,
    "note": note,
}, open(out, "w"), indent=2)
print(out)
if not clean:
    print(f"write-receipt: receipt is NOT clean ({note or 'clean=false'})", file=sys.stderr)
PY
