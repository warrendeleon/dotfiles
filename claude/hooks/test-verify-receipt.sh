#!/bin/bash
# Regression checks for verify-receipt.sh: receipt a draft in a throwaway HOME, then
# feed the hook a tool call and compare allow (exit 0) or deny (exit 2).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fails=0
mkdir -p "$TMP/home" "$TMP/drafts" "$TMP/elsewhere"
echo "Review text" > "$TMP/drafts/review.md"
echo "Not receipted" > "$TMP/drafts/other.md"
HIST='[{"round":1,"mode":"recheck","checked":1,"found":0,"fresh":0,"confirmed":0,"lostConfirms":0,"incomplete":false}]'
HOME="$TMP/home" "$DIR/write-receipt.sh" --profile test --clean true --history "$HIST" "$TMP/drafts/review.md" > /dev/null

# check <name> <expect allow|deny> <command> [cwd]
check() {
  local name=$1 expect=$2 cmd=$3 cwd=${4:-$TMP/elsewhere}
  python3 -c 'import json,sys;print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' "$cmd" "$cwd" \
    | HOME="$TMP/home" "$DIR/verify-receipt.sh" 2> /dev/null
  local status=$? got=allow
  [ $status -eq 2 ] && got=deny
  if [ "$got" = "$expect" ]; then echo "ok   $name"; else echo "FAIL $name: expected $expect, got $got"; fails=$((fails + 1)); fi
}

GH="gh"
API="$GH api repos/o/r/pulls/1/reviews --method POST"
REVIEW="$GH pr review 1 --comment"
check absolute-receipted   allow "$API --input $TMP/drafts/review.md"
# 7 Oct 2026: a relative path after `cd` was resolved from the session's folder and refused.
check cd-then-relative     allow "cd $TMP/drafts && $API --input review.md"
check cwd-relative         allow "$API --input review.md" "$TMP/drafts"
check relative-wrong-base  deny  "$API --input review.md"
check cd-unreceipted       deny  "cd $TMP/drafts && $API --input other.md"
check body-file-receipted  allow "$REVIEW --body-file $TMP/drafts/review.md"
check inline-body          deny  "$REVIEW --body text"
echo "Changed" >> "$TMP/drafts/review.md"
check stale-receipt        deny  "$API --input $TMP/drafts/review.md"

exit $fails
