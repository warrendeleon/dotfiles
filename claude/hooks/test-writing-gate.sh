#!/bin/bash
# Regression checks for writing-gate.sh: feed it a transcript and a tool call, and
# compare allow (exit 0) or block (exit 2) with the expectation.
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/writing-gate.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
G="$TMP/guides"; mkdir -p "$G"
for g in edit-doc-checklist writing-guides plain-sentence-construction ai-writing-gotchas uk-tone-writing accuracy-and-reproducibility skim-layer revision-passes jira-ticket-template email-replies slack-messages slide-decks; do : > "$G/$g.md"; done
fails=0

# transcript <file> <event>...   event: a guide name (a full Read), name:partial, or COMPACT
transcript() {
  local out=$1; shift; : > "$out"
  for ev in "$@"; do
    python3 - "$ev" "$G" >> "$out" <<'PY'
import json, sys
ev, g = sys.argv[1], sys.argv[2]
if ev == "COMPACT":
    print(json.dumps({"type": "system", "subtype": "compact_boundary"}))
else:
    name, _, part = ev.partition(":")
    args = {"file_path": f"{g}/{name}.md"}
    if part:
        args["limit"] = 50
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": args}]}}))
PY
  done
}

# check <name> <expect allow|block> <tool> <tool_input json> <event>...
check() {
  local name=$1 expect=$2 tool=$3 tinput=$4; shift 4
  local t="$TMP/$name.jsonl"
  transcript "$t" "$@"
  python3 -c 'import json,sys;print(json.dumps({"tool_name":sys.argv[1],"tool_input":json.loads(sys.argv[2]),"transcript_path":sys.argv[3]}))' "$tool" "$tinput" "$t" \
    | WRITING_GUIDES_DIR="$G" "$HOOK" >/dev/null 2>"$TMP/err"
  local code=$? got=allow
  [ "$code" = 2 ] && got=block
  [ "$code" != 0 ] && [ "$code" != 2 ] && got="error($code)"
  if [ "$got" = "$expect" ]; then echo "ok   $name"; else echo "FAIL $name: expected $expect, got $got"; cat "$TMP/err"; fails=$((fails + 1)); fi
}

CORE="writing-guides plain-sentence-construction ai-writing-gotchas uk-tone-writing"
PROSE="$CORE accuracy-and-reproducibility skim-layer revision-passes"
MSG="$CORE skim-layer revision-passes"
MD='{"file_path":"/tmp/x/report.md","content":"words"}'
SLACK='{"channel":"C1","text":"hello"}'

check md-no-guides        block Write "$MD"
check md-all-guides       allow Write "$MD" $PROSE
check md-one-missing      block Write "$MD" $CORE skim-layer revision-passes
check md-partial-read     block Write "$MD" $CORE accuracy-and-reproducibility:partial skim-layer revision-passes
check md-after-compact    block Write "$MD" $PROSE COMPACT
check md-reread-after     allow Write "$MD" $PROSE COMPACT $PROSE
check edit-md             block Edit  '{"file_path":"/tmp/x/post.mdx","old_string":"a","new_string":"b"}'
check code-file           allow Write '{"file_path":"/tmp/x/app.ts","content":"const a = 1"}'
check claude-md           allow Write '{"file_path":"/tmp/x/CLAUDE.md","content":"rules"}'
check skill-in-dotfiles   allow Write '{"file_path":"/Users/x/Developer/dotfiles/claude/skills/a/SKILL.md","content":"x"}'
check skill-file          allow Write '{"file_path":"/Users/x/.claude/skills/a/SKILL.md","content":"x"}'
check html-app            allow Write '{"file_path":"/tmp/x/app.html","content":"<script>let a=1</script><div id=app></div>"}'
check html-document       block Write "$(python3 -c 'import json;print(json.dumps({"file_path":"/tmp/x/report.html","content":"<p>"+"word "*600+"</p>"}))')"
check deck-needs-guide    block Write '{"file_path":"/tmp/x/slides.md","content":"# a"}' $PROSE
check deck-with-guide     allow Write '{"file_path":"/tmp/x/slides.md","content":"# a"}' $MSG slide-decks
check slack-no-surface    block mcp__slack__slack_send_message "$SLACK" $MSG
check slack-with-surface  allow mcp__slack__slack_send_message "$SLACK" $MSG slack-messages
check slack-read          allow mcp__slack__slack_search_messages '{"query":"x"}'
check jira-comment        block mcp__atlassian__addCommentToJiraIssue '{"issueIdOrKey":"SCB-1","commentBody":"x"}' $PROSE
check jira-with-surface   allow mcp__atlassian__addCommentToJiraIssue '{"issueIdOrKey":"SCB-1","commentBody":"x"}' $PROSE jira-ticket-template
check email               block mcp__airmail__send_email '{"to":"a@example.com","body":"x"}' $MSG
check email-with-surface  allow mcp__airmail__send_email '{"to":"a@example.com","body":"x"}' $MSG email-replies
check rag-log             allow mcp__rag__log_action '{"action":"x"}'
check gh-comment          block Bash '{"command":"gh pr comment 1 --body-file b.md"}'
check gh-comment-ok       allow Bash '{"command":"gh pr comment 1 --body-file b.md"}' $PROSE
check gh-view             allow Bash '{"command":"gh pr view 1"}'
check commit              block Bash '{"command":"git commit -m \"fix: x\""}'
check commit-ok           allow Bash '{"command":"git commit -m \"fix: x\""}' writing-guides plain-sentence-construction ai-writing-gotchas
check commit-in-quotes    allow Bash '{"command":"grep -n \"git commit\" notes.txt"}'
check pbcopy              block Bash '{"command":"cat msg.txt | pbcopy"}' $MSG
check pbcopy-with-surface allow Bash '{"command":"cat msg.txt | pbcopy"}' $MSG slack-messages
check plain-bash          allow Bash '{"command":"ls -la"}'
echo "# Page" > "$TMP/page.md"; echo "# Deck" > "$TMP/slides.md"
check edit-existing-bare      block Edit  "{\"file_path\":\"$TMP/page.md\",\"old_string\":\"a\",\"new_string\":\"b\"}"
check edit-existing-checklist allow Edit  "{\"file_path\":\"$TMP/page.md\",\"old_string\":\"a\",\"new_string\":\"b\"}" edit-doc-checklist
check edit-checklist-partial  block Edit  "{\"file_path\":\"$TMP/page.md\",\"old_string\":\"a\",\"new_string\":\"b\"}" edit-doc-checklist:partial
check edit-checklist-compact  block Edit  "{\"file_path\":\"$TMP/page.md\",\"old_string\":\"a\",\"new_string\":\"b\"}" edit-doc-checklist COMPACT
check edit-missing-file       block Edit  "{\"file_path\":\"$TMP/new.md\",\"old_string\":\"\",\"new_string\":\"b\"}" edit-doc-checklist
check write-needs-profile     block Write "{\"file_path\":\"$TMP/page.md\",\"content\":\"x\"}" edit-doc-checklist
check edit-deck-checklist     block Edit  "{\"file_path\":\"$TMP/slides.md\",\"old_string\":\"a\",\"new_string\":\"b\"}" edit-doc-checklist
check edit-deck-with-surface  allow Edit  "{\"file_path\":\"$TMP/slides.md\",\"old_string\":\"a\",\"new_string\":\"b\"}" edit-doc-checklist slide-decks
check commit-not-checklist    block Bash  '{"command":"git commit -m \"fix: x\""}' edit-doc-checklist
check read-tool           allow Read '{"file_path":"/tmp/x/report.md"}'

exit $fails
