#!/bin/bash
# One deterministic pass over a drafted pull request review, then a receipt.
# Nothing is cloned or run: the pull request's own diff is the source.
#
#   pr-check.sh --repo <owner/name> --pr <number> <review-file|payload.json> [...]
#
# A .json payload for `gh api --input` is scanned through its body strings, so the
# file that is posted gets the same check as the markdown it was built from.
#
# Every `path:line` or `path:line-line` in the review files is compared with the
# hunks of `gh pr diff`. A reference to a line the pull request did not add or
# change is a carried-over fault: it is listed, and the receipt is written clean
# only when the review names none, or names each of them under a heading
# containing "carried over", "already on main" or "pre-existing".
set -euo pipefail

repo="" pr=""
files=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --pr)   pr="$2";   shift 2 ;;
    *)      files+=("$1"); shift ;;
  esac
done
[[ -n "$repo" && -n "$pr" && ${#files[@]} -gt 0 ]] || { echo "usage: pr-check.sh --repo <owner/name> --pr <number> <review-file>..." >&2; exit 1; }

diff=$(gh pr diff "$pr" --repo "$repo") || { echo "pr-check: gh pr diff failed for $repo#$pr" >&2; exit 1; }
DIFF="$diff" python3 - "${files[@]}" <<'PY'
import os, re, sys
# lines the pull request added or changed, per file, from the unified diff
changed = {}
path = None; new = 0
for ln in os.environ["DIFF"].splitlines():
    if ln.startswith("+++ "):
        path = ln[4:].strip(); path = path[2:] if path.startswith("b/") else path
        changed.setdefault(path, set()); continue
    m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
    if m: new = int(m.group(1)); continue
    if path is None: continue
    if ln.startswith("+"): changed[path].add(new); new += 1
    elif ln.startswith("-"): pass
    elif ln.startswith("\\"): pass
    else: new += 1
def review_text(f):
    """The text that will be posted. A .json payload for `gh api --input` carries it in
    string fields (body, comments[].body); those are joined so the same headings and
    references are checked in what is actually sent."""
    raw = open(f, encoding="utf-8").read()
    if not f.lower().endswith(".json"): return raw
    import json
    parts = []
    def walk(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k == "body" and isinstance(v, str): parts.append(v)
                else: walk(v)
        elif isinstance(n, list):
            for v in n: walk(v)
    try: walk(json.loads(raw))
    except Exception: return raw
    return "\n\n".join(parts)
refs = 0; carried = []; unlabelled = []; unknown = []; cited = []
for f in sys.argv[1:]:
    text = review_text(f)
    for m in re.finditer(r"`?((?:[\w.-]+/)*[\w.-]+):(\d+)(?:-(\d+))?`?", text):
        p, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
        if "/" not in p and "." not in p: continue   # a path, not "SCB-1234:" or "12:30"
        refs += 1
        head = ""
        for h in re.finditer(r"^#+\s*(.+)$", text[:m.start()], re.M): head = h.group(1)
        labelled = re.search(r"carried over|already on main|pre-?existing|context|evidence|background", head, re.I) is not None
        blocking = re.search(r"blocking|must fix|request(ed)? changes|defect", head, re.I) is not None
        ref = f"{p}:{a}" + (f"-{b}" if b != a else "")
        hit = [k for k in changed if k == p or k.endswith("/" + p)]
        if not hit:
            # a file the pull request does not touch: fine as cited evidence, a failure only
            # when the review presents it as a defect of this change
            (unknown if blocking and not labelled else cited).append(ref); continue
        touched = any(n in changed[hit[0]] for n in range(a, b + 1))
        if not touched:
            (carried if labelled else unlabelled).append(ref)
print(f"pr-check: {refs} file:line references; {len(carried)} carried-over and labelled; {len(cited)} cited from files outside the diff; "
      f"{len(unknown)} outside the diff but under a blocking heading; {len(unlabelled)} on unchanged lines but presented as this change's:")
for u in unlabelled: print("  - " + u)
for u in unknown: print("  ! " + u + " (file not in the diff, under a blocking heading)")
sys.exit(1 if (unlabelled or unknown) else 0)
PY
status=$?
hist="[{\"round\":1,\"mode\":\"recheck\",\"checked\":1,\"found\":$status,\"fresh\":$status,\"confirmed\":$status,\"lostConfirms\":0,\"incomplete\":false}]"
"$HOME/Developer/dotfiles/claude/hooks/write-receipt.sh" --profile "pull request review" --clean "$([[ $status -eq 0 ]] && echo true || echo false)" --history "$hist" "${files[@]}"
exit $status
