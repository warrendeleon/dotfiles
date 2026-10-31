#!/bin/bash
# Regression checks for pr-check.sh: a stub `gh` serves the diff, then each review draft
# is checked in a throwaway HOME and the exit status compared (0 clean, 1 not clean).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fails=0
mkdir -p "$TMP/home" "$TMP/bin" "$TMP/drafts"

# Stub gh. GH_MODE=whole serves `gh pr diff`; large fails it the way GitHub does past
# 20,000 lines and serves only the per-file patches; broken fails both.
cat > "$TMP/bin/gh" <<'STUB'
#!/bin/bash
patch=$'@@ -1,2 +1,3 @@\n line one\n+added line\n line two'
if [ "$1 $2" = "pr diff" ]; then
  [ "$GH_MODE" = whole ] || [ "$GH_MODE" = huge ] || { echo "HTTP 406: Sorry, the diff exceeded the maximum number of lines (20000)" >&2; exit 1; }
  printf 'diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n%s\n' "$patch"
  # huge: a second file of about 2 MB, past the limit an environment variable can carry
  [ "$GH_MODE" = huge ] && { printf -- '--- /dev/null\n+++ b/docs/big.md\n@@ -0,0 +1,20000 @@\n'; yes '+generated documentation line of about a hundred characters, repeated to make the diff large' | head -n 20000; }
  exit 0
fi
if [ "$1" = api ] && [ "$GH_MODE" = large ]; then
  printf '+++ b/src/a.ts\n%s\n' "$patch"
  exit 0
fi
exit 1
STUB
chmod +x "$TMP/bin/gh"

printf '🟡 **Suggestion:** see `src/a.ts:2`.\n' > "$TMP/drafts/added.md"
printf '🔴 **Change requested:** see `src/a.ts:1`.\n' > "$TMP/drafts/unchanged.md"

# check <name> <mode> <expect 0|1> <draft>
check() {
  local name=$1 mode=$2 expect=$3 draft=$4
  GH_MODE=$mode PATH="$TMP/bin:$PATH" HOME="$TMP/home" "$DIR/pr-check.sh" --repo o/r --pr 1 "$draft" > /dev/null 2>&1
  local got=$?
  if [ "$got" = "$expect" ]; then echo "ok   $name"; else echo "FAIL $name: expected exit $expect, got $got"; fails=$((fails + 1)); fi
}

check whole-diff-added-line      whole  0 "$TMP/drafts/added.md"
check whole-diff-unchanged-line  whole  1 "$TMP/drafts/unchanged.md"
# 19 Oct 2026: newsuk/ncu-ad-manager#3296 was past GitHub's diff limit, so no receipt could be written.
check large-diff-added-line      large  0 "$TMP/drafts/added.md"
check large-diff-unchanged-line  large  1 "$TMP/drafts/unchanged.md"
check no-diff-at-all             broken 1 "$TMP/drafts/added.md"
# Same day: the per-file patches came to more than the argument limit once passed as $DIFF.
check huge-diff-added-line       huge   0 "$TMP/drafts/added.md"

# A draft the gate's fixer deleted is reported by name, not as a Python traceback (28 Oct 2026).
out=$(GH_MODE=whole PATH="$TMP/bin:$PATH" HOME="$TMP/home" "$DIR/pr-check.sh" --repo o/r --pr 1 "$TMP/drafts/added.md" "$TMP/drafts/gone.json" 2>&1)
got=$?
if [ "$got" = 1 ] && [[ "$out" == *"gone.json does not exist"* ]] && [[ "$out" != *Traceback* ]]; then echo "ok   missing-draft"; else echo "FAIL missing-draft: exit $got: $out"; fails=$((fails + 1)); fi

exit $fails
