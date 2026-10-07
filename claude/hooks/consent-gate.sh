#!/bin/bash
# PreToolUse gate: an outward-facing write needs a fresh, explicit go from Warren.
#
# Covers Bash commands that post, comment, edit, merge or push to a shared or
# public surface (gh pr/issue writes, gh api mutations, curl mutations to a
# remote host, every git push) and MCP tools that send, post, create, update or
# delete on a colleague-visible system (email, calendar, Jira, Slack, GitHub,
# Notion, Composio). Reads and local-only tools pass straight through: a gh api
# call counts as a write only when it names a write method, when a field flag
# makes gh send POST, or when its GraphQL document is a mutation.
#
# The go has to be in Warren's most recent message: post, send, publish, push,
# deploy, go ahead, approved, ship it, submit, merge. A negated form ("don't
# post") does not count. That makes approval per action and per batch: once he
# has said anything else, the next outward write is blocked again and the draft
# has to be shown afresh. The 7 and 8 September Jira incidents and the four
# unasked deploys on 3 September are the reason this exists.
set -uo pipefail
input=$(cat)
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT="$input" HOOKS_DIR="$HOOKS_DIR" python3 - <<'PY'
import json, os, re, sys
sys.path.insert(0, os.environ["HOOKS_DIR"])
from lib_transcript import human_turns

try:
    call = json.loads(os.environ["INPUT"])
except Exception:
    sys.exit(0)
tool = call.get("tool_name", "")
inp = call.get("tool_input", {}) or {}
transcript = call.get("transcript_path", "")

def gh_api_mutation(cmd, raw):
    """True only when `gh api` would actually write.

    gh sends GET unless a method is named or a field flag is present, so a read with
    -f (a search query, a paginated list) was being gated as a write. GraphQL always
    posts, so judge it on whether the document is a mutation.
    """
    if not re.search(r"\bgh\s+api\b", cmd):
        return False
    method = re.search(r"(?:-X|--method)[=\s]+([A-Za-z]+)", cmd)
    if method:
        return method.group(1).upper() not in ("GET", "HEAD")
    if re.search(r"\bgh\s+api\s+graphql\b", cmd):
        return bool(re.search(r"\bmutation\b\s*[({\w]", raw))
    return bool(re.search(r"\s-[fF]\s|--field|--raw-field|--input", cmd))


BASH_RULES = [
    (r"\bgh\s+(pr|issue)\s+(comment|review|edit|close|merge|create|reopen|lock|ready)\b", "a GitHub PR/issue write"),
    (r"\bgh\s+(release|repo)\s+(create|edit|delete|archive|rename)\b", "a GitHub repo/release write"),
    (r"\bgit\s+(-C\s+\S+\s+)?push\b", "a git push"),
    (r"\bcurl\b(?![^\n|;&]*(localhost|127\.0\.0\.1|192\.168\.|minipc))[^\n|;&]*(\s-X\s*(POST|PUT|PATCH|DELETE)|\s--request\s*(POST|PUT|PATCH|DELETE)|\s-d\s|\s--data|\s--json\b|\s-F\s|\s--form\b)", "an HTTP mutation to a remote host"),
]

MCP_LOCAL = re.compile(r"^mcp__(rag|ccd_[a-z_]+|scheduled-tasks|computer-use|Claude_Browser|claude-in-chrome|visualize|terminal|mcp-registry|Claude_Code_iOS_Simulator)__")
MCP_LOCAL_TOOLS = re.compile(r"__(read_me|show_widget)$")
AIRMAIL_OUTWARD = {
    "send_email", "reply_to_message", "forward_message", "quick_reply",
    "create_event", "update_event", "delete_event", "set_vacation_settings",
    "create_rule", "toggle_rule", "delete_rule", "share_icloud", "update_user_profile",
}
READ_VERBS = re.compile(r"^(notion-)?(search|list|get|fetch|read|query|download|find|analy[sz]e|suggest|check|wait|show|refresh|export|batch_triage|manage_capabilities)", re.I)
WRITE_VERBS = re.compile(r"(send|reply|forward|post|publish|create|update|delete|trash|archive|move|transition|assign|comment|edit|execute|spawn|stop|convert|duplicate|add|remove|set|empty)", re.I)


def classify():
    if tool == "Bash":
        # Quoted strings are data (a commit body, a grep pattern), never the command.
        cmd = re.sub(r"'[^']*'|\"[^\"]*\"", " ", inp.get("command", "") or "")
        raw = inp.get("command", "") or ""
        if gh_api_mutation(cmd, raw):
            return "a GitHub API mutation"
        for pat, label in BASH_RULES:
            if re.search(pat, cmd, re.S):
                return label
        return None
    if not tool.startswith("mcp__"):
        return None
    if MCP_LOCAL.match(tool) or MCP_LOCAL_TOOLS.search(tool):
        return None
    name = tool.rsplit("__", 1)[-1]
    if tool.startswith("mcp__airmail__"):
        return f"an outward email/calendar action ({name})" if name in AIRMAIL_OUTWARD else None
    if READ_VERBS.match(name):
        return None
    if WRITE_VERBS.search(name):
        return f"a write to a shared system ({tool})"
    return None


label = classify()
if not label:
    sys.exit(0)

# Standing go: a scheduled task Warren has authorised once, for good, to run one
# exact outward command unattended. A scheduled run has no human turn (its prompt
# arrives as a <scheduled-task> block), so without this every such push was blocked.
# The whole command must match: no chaining, no other branch or remote.
STANDING = {
    # 2 Oct 2026: "configure this routine so I never ever have to interact again".
    "rebase-scb-6272-triplelift": re.compile(
        r"git -C (~|/Users/warrendeleon)/Developer/news\.co\.uk/\.worktrees/ncu-ad-manager-SCB-6272"
        r" push --force-with-lease=feat/SCB-6272-triplelift-parent-id-news-uk:[0-9a-f]{40}"
        r" origin feat/SCB-6272-triplelift-parent-id-news-uk( 2>&1)?"
    ),
}


def scheduled_task_name(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("type") != "user" or rec.get("isSidechain"):
                    continue
                c = (rec.get("message") or {}).get("content")
                if isinstance(c, list):
                    c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict))
                m = re.search(r'<scheduled-task name="([^"]+)"', c or "")
                return m.group(1) if m else None
    except OSError:
        return None
    return None


if tool == "Bash":
    task = scheduled_task_name(transcript)
    rule = STANDING.get(task or "")
    if rule and rule.fullmatch((inp.get("command", "") or "").strip()):
        sys.exit(0)

# Standing go for a named batch of branches, in any session. 2 Oct 2026, the SCB-6338
# Talksport vendor-mapping sub-tasks: "No need for my confirmation for every branch.
# Once the code is perfect and the agents don't find things to change/fix. Then push
# and create the PRs." Only the exact push, lease push and PR create for those
# branches pass; no chaining, no other branch, repo or remote.
_SUB = r"SCB-(6310|6313|6314|6315|6316|6319|6320|6321|6322|6323|6324)"
_BR = r"feat/" + _SUB.replace("(", "(?:") + r"-[a-z0-9-]+"
STANDING_BATCH = [
    re.compile(
        r"git -C (?:~|/Users/warrendeleon)/Developer/news\.co\.uk/\.worktrees/ncu-ad-manager-" + _SUB
        + r" push (?:-u |--force-with-lease=(?P<lb>" + _BR + r"):[0-9a-f]{40} )?origin (?P<br>" + _BR + r")( 2>&1)?"
    ),
    re.compile(
        # 2 Oct: "I don't understand why you can't create all 10 PRs as drafts?"
        r"gh pr create --repo newsuk/ncu-ad-manager --base main --head (?P<br>" + _BR + r")(?: --draft)?"
        r" --title '[^'\n]+' --body-file \S+\.md(?: --label [a-z_]+)+( 2>&1)?"
    ),
]

# A go stays live until the action is done or Warren redirects. Scanning only
# the newest message voided consent whenever he added a follow-up instruction
# before the authorised command had run (10 Sep, the SCB-5786 force-push), so
# look back over the last few turns and let a later veto override.
# 5 Oct: "When you can, hit the release" was five messages back when the production gate opened,
# and a three-message window refused it. A go stands until the action runs or a later veto.
WINDOW = 8
# Ordinary agreement counts. Warren says "go", "yes", "do it" as readily as the
# formal verbs, and refusing those made the gate ask twice for a yes already
# given, which is its own failure (10 Sep). Keep the list plain and additive.
# "Create the PR first" was refused on 23 Sep because create/open/raise were missing,
# and "Close PR ... unassign ... move it" on 28 Sep for close/move/unassign.
GO = (r"(post|send|publish|push|deploy|release|submit|merge|comment it|reply to|resolve|create|open|raise|close|move|unassign"
      r"|go ahead|go for it|\bgo\b|proceed|carry on|crack on|run it|re-? ?run|retry|do it|make it so"
      r"|approved?|agreed?|confirmed?|accepted?|ship it"
      # Picking from a numbered list is a go for those items: "Do 2-3" (2 Oct, PR edits).
      r"|do (?:\d|all|both|them|these|those|that|this)"
      r"|yes|yeah|yep|yup|sure|ok|okay|fine by me|sounds good|please do|that'?s fine)")
# "Don't forget to reply to the comment and resolve it" is a go, not a veto (5 Oct, PR #3412),
# so a negation followed by "forget" does not count.
NEG = r"\b(don'?t|do not|never|stop|without|no)\s+(?!forget\b)(\w+\s+){0,2}" + GO + r"\b"
# Editing verbs count only as an imperative that opens a sentence or clause: "fix the
# comment", "change it to two story points" (2 Oct, SCB-6273). Anywhere else they are
# nouns or questions ("how difficult is the fix?"), so they must not count as a go.
# A polite request is the same imperative: "Can you edit them all up with the
# corrected values?" was refused on 2 Oct (SCB-6314/6319/6321) for lack of this.
IMPERATIVE = (r"(?:^|[.!?;,:]\s*|\b(?:and|then|now|please|so)\s+|\b(?:can|could|would|will)\s+you\s+(?:please\s+)?)"
              r"(fix|change|update|edit|set|add|remove|reopen|assign|rename|retitle|amend)\b")

# "No need just approve it" (5 Oct, PR #3423) declines one thing and asks for another; the
# "no need" belongs to the declined part, so drop it before "just". "No need to push" stays a veto.
turns = [re.sub(r"\bno need\b[,.;:!]?\s+(?=just\b)", "", t.lower()) for t in human_turns(transcript)][-WINDOW:]

# The batch go above holds unless a recent turn vetoes it ("don't push anything").
if tool == "Bash" and not any(re.search(NEG, t) for t in turns):
    raw_cmd = (inp.get("command", "") or "").strip()
    for rule in STANDING_BATCH:
        m = rule.fullmatch(raw_cmd)
        if not m:
            continue
        key = m.group("br")
        # The worktree, the pushed branch and any lease must all name the same ticket.
        keys = set(re.findall(r"SCB-\d{4}", raw_cmd))
        if len(keys) == 1 and (not m.groupdict().get("lb") or m.group("lb") == key):
            sys.exit(0)

# Standing go for rerunning only the failed jobs of a CircleCI workflow, in any session.
# 5 Oct 2026, after a flaky e2e failure on an SCB-6338 PR: "yes I shouldn't have to tell
# you that" and "Do it for the other PRs too". Only the exact from_failed rerun of one
# workflow passes, optionally after loading the token; no other endpoint or body.
CIRCLE_RERUN = re.compile(
    r"(?:set -a; \. ~/\.secrets\.env; set \+a; )?"
    r"curl -s -X POST -H \"Circle-Token: \$CIRCLE_TOKEN\" -H \"Content-Type: application/json\""
    r" -d '\{\"from_failed\": true\}' \"https://circleci\.com/api/v2/workflow/[0-9a-f-]{36}/rerun\""
)
if (tool == "Bash" and not any(re.search(NEG, t) for t in turns)
        and CIRCLE_RERUN.fullmatch((inp.get("command", "") or "").strip())):
    sys.exit(0)

# Standing go for the MF tutorial companion's private staging repository, in any session.
# Warren's standing rule: the staging repo is not outward; push main and the post's tag to it
# without asking (the gate blocked one on 4 Oct 2026, during the post 17 Codex loop). Only main,
# or a force-pushed post tag, to the staging remote of the companion: no chaining, no origin or
# minipc, no other repository, no force-push of main.
COMPANION_STAGING = re.compile(
    r"git -C (?:~|/Users/warrendeleon)/Developer/warrendeleon/react-native-module-federation"
    r" push (?:staging main|-f staging refs/tags/post-\d{2}-[a-z0-9-]+)( 2>&1)?"
)
if (tool == "Bash" and not any(re.search(NEG, t) for t in turns)
        and COMPANION_STAGING.fullmatch((inp.get("command", "") or "").strip())):
    sys.exit(0)

go_at = None
for i, t in enumerate(turns):
    neg = re.search(NEG, t)
    # Inflections count: "posted", "sending", "merged" are the same go as the bare
    # verb, and refusing them makes the gate ask twice for a yes already given
    # (21 Sep, this pull request review).
    pos = list(re.finditer(r"\b" + GO + r"(?:ed|d|ing)?\b", t)) + list(re.finditer(IMPERATIVE, t, re.M))
    if pos and not (neg and len(pos) == 1):
        go_at = i
# A veto in the same turn or any turn after the go cancels it.
if go_at is not None and not any(re.search(NEG, t) for t in turns[go_at + 1:]):
    sys.exit(0)

reason = (
    f"Blocked: this is {label} and Warren's latest message does not authorise it. "
    "Show him the exact draft or command, stop, and ask him to confirm. Any plain agreement counts "
    "(yes, go, do it, send, push). One go covers one named batch, and stays live across follow-up "
    "instructions until the action runs or he vetoes it."
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
PY
