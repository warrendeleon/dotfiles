#!/bin/bash
# Regression checks for agent-gate.sh: feed it a tool call and compare allow (exit 0)
# or block (exit 2) with the expectation.
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/agent-gate.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fails=0

# check <name> <expect allow|block> <tool> <tool_input json>
# Optional arguments: Warren's latest message, the session's model, and how many Fable agents
# the session has already launched.
check() {
  local name=$1 expect=$2 tool=$3 tinput=$4 said=${5:-} model=${6:-claude-opus-5-5} earlier=${7:-0}
  local t="$TMP/$name.jsonl"
  python3 -c 'import json,sys
print(json.dumps({"type":"assistant","message":{"model":sys.argv[2],"content":[{"type":"text","text":"hi"}]}}))
for i in range(int(sys.argv[3])): print(json.dumps({"type":"assistant","message":{"model":sys.argv[2],"content":[{"type":"tool_use","id":"toolu_%d"%i,"name":"Agent","input":{"model":"fable","effort":"high"}}]}}))
if sys.argv[1]: print(json.dumps({"type":"user","message":{"role":"user","content":sys.argv[1]}}))' "$said" "$model" "$earlier" > "$t"
  python3 -c 'import json,sys;print(json.dumps({"tool_name":sys.argv[1],"tool_input":json.loads(sys.argv[2]),"transcript_path":sys.argv[3]}))' "$tool" "$tinput" "$t" | "$HOOK" >/dev/null 2>&1
  local code=$? got=allow
  [ "$code" = 2 ] && got=block
  [ "$code" != 0 ] && [ "$code" != 2 ] && got="error($code)"
  if [ "$got" = "$expect" ]; then echo "ok   $name"; else echo "FAIL $name: expected $expect, got $got"; fails=$((fails + 1)); fi
}

check agent-bare            block Agent '{"description":"x","prompt":"y"}'
check agent-model-only      block Agent '{"description":"x","prompt":"y","model":"sonnet"}'
check agent-effort-only     block Agent '{"description":"x","prompt":"y","effort":"low"}'
check agent-both            allow Agent '{"description":"x","prompt":"y","model":"sonnet","effort":"medium"}'
check agent-typed-bare      block Agent '{"description":"x","prompt":"y","subagent_type":"web-fetch"}'
check agent-typed-both      allow Agent '{"description":"x","prompt":"y","subagent_type":"web-fetch","model":"haiku","effort":"low"}'
check agent-fork            allow Agent '{"description":"x","prompt":"y","subagent_type":"fork"}'
check agent-fable-first     allow Agent '{"description":"x","prompt":"y","model":"fable","effort":"high"}' "review the gate"
check agent-fable-second    block Agent '{"description":"x","prompt":"y","model":"fable","effort":"high"}' "review the gate" claude-opus-5-5 1
check agent-fable-asked     allow Agent '{"description":"x","prompt":"y","model":"fable","effort":"high"}' "use Fable for this review" claude-opus-5-5 3
check agent-opus-high       allow Agent '{"description":"x","prompt":"y","model":"opus","effort":"high"}' "" claude-opus-5-5 3
check agent-max-first       allow Agent '{"description":"x","prompt":"y","model":"opus","effort":"max"}' "review the gate"
check agent-max-after-fable block Agent '{"description":"x","prompt":"y","model":"opus","effort":"xhigh"}' "" claude-opus-5-5 1
check agent-max-asked       allow Agent '{"description":"x","prompt":"y","model":"opus","effort":"max"}' "ultrathink on this one" claude-opus-5-5 2
check fork-on-fable         block Agent '{"description":"x","prompt":"y","subagent_type":"fork"}' "carry on" claude-fable-5-2
check fork-on-fable-asked   allow Agent '{"description":"x","prompt":"y","subagent_type":"fork"}' "fork this off" claude-fable-5-2
check task-legacy-name      block Task  '{"description":"x","prompt":"y"}'
check bash-short            allow Bash  '{"command":"ls"}'
check bash-two-minutes      allow Bash  '{"command":"npm test","timeout":120000}'
check bash-three-minutes    allow Bash  '{"command":"npm test","timeout":180000}'
check bash-ten-foreground   block Bash  '{"command":"npm run build","timeout":600000}'
check bash-ten-background   allow Bash  '{"command":"npm run build","timeout":600000,"run_in_background":true}'
check bash-bad-timeout      allow Bash  '{"command":"ls","timeout":"soon"}'
check workflow-plain        allow Workflow '{"scriptPath":"x.js","args":{"profile":"blog","targets":["a.md"],"maxRounds":2}}'
check workflow-fable-arg    block Workflow '{"scriptPath":"x.js","args":{"models":{"find":"fable"}}}' "run the review"
check workflow-max-arg      block Workflow '{"scriptPath":"x.js","args":{"efforts":{"find":"max"}}}' "run the review"
check workflow-fable-asked  allow Workflow '{"scriptPath":"x.js","args":{"models":{"find":"fable"}}}' "run it with Fable critics"
check workflow-fable-script block Workflow '{"script":"await agent(p, { model: \u0027fable\u0027, effort: \u0027high\u0027 })"}' "go"
check workflow-notes-prose  allow Workflow '{"scriptPath":"x.js","args":{"notes":"the post compares Fable and Opus pricing in its second section, at length"}}'
check other-tool            allow Read  '{"file_path":"/tmp/x"}'

# A workflow agent with no model inherits the session's, which may be Fable; the gate does not
# see workflow agents, so every agent() call in a workflow names its model.
bare=$(grep -nE 'agent\(.*\{' "$(dirname "$HOOK")"/../workflows/*.js | grep -vE "model|tier\(|\.\.\.opts" || true)
if [ -z "$bare" ]; then echo "ok   workflows-name-a-model"; else echo "FAIL workflows-name-a-model: $bare"; fails=$((fails + 1)); fi

exit $fails
