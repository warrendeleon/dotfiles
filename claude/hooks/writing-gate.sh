#!/bin/bash
# PreToolUse gate: nothing written for a reader leaves the chat until the writing
# guides for that kind of text have been read in this session.
#
# Warren has asked for "follow writing-guides.md" and "make sure it is styled and
# formatted correctly" in about 340 messages across 107 sessions (July to November
# 2026). The rule was in CLAUDE.md, the output style and a memory, and was still
# skipped, because all three are advice. This makes it a condition of the write.
#
# What it gates (the text is prose and goes somewhere other than the chat):
#   Write, Edit      a prose file: .md .mdx .txt .rst .adoc, or an .html document
#   Bash             gh pr/issue writes, gh api mutations, git commit, pbcopy (the clipboard)
#   mcp__*           any tool that sends, posts, creates or updates on a shared system
#
# What it checks: the session transcript holds a full Read (no offset, no limit) of
# every guide the router's profile names for that surface, made since the last
# compaction. A compaction summarises the guides away, so they must be read again.
# The profiles are the rows of ~/.wiki/personal/writing/writing-guides.md; the surface
# guide (Slack, Jira, email, decks) is where the formatting rules for that medium live.
#
# An Edit to a file that already exists is let through on edit-doc-checklist.md alone
# (plus slide-decks.md for a deck): the guides condensed one rule per line.
#
# It cannot judge whether the text follows the guides. It guarantees they are in
# context when the text is written, which is the step that was being skipped.
#
# Blocks with exit 2 and the list of files still to read on stderr.
set -uo pipefail
input=$(cat)
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT="$input" HOOKS_DIR="$HOOKS_DIR" GUIDES_DIR="${WRITING_GUIDES_DIR:-$HOME/.wiki/personal/writing}" python3 - <<'PY'
import json, os, re, sys

sys.path.insert(0, os.environ["HOOKS_DIR"])
from lib_transcript import _records

try:
    call = json.loads(os.environ["INPUT"])
except Exception:
    sys.exit(0)
tool = call.get("tool_name", "")
inp = call.get("tool_input", {}) or {}
GUIDES = os.path.realpath(os.environ["GUIDES_DIR"])
HOME = os.path.expanduser("~")

ROUTER = "writing-guides"
G1, G2, G3 = "plain-sentence-construction", "ai-writing-gotchas", "uk-tone-writing"
G5, G6, G7 = "accuracy-and-reproducibility", "skim-layer", "revision-passes"
# One row per surface, copied from the router's "Finite reading profiles" table.
PROFILES = {
    "prose":  [ROUTER, G1, G2, G3, G5, G6, G7],
    "github": [ROUTER, G1, G2, G3, G5, G6, G7],
    "jira":   [ROUTER, G1, G2, G3, G5, G6, G7, "jira-ticket-template"],
    "email":  [ROUTER, G1, G2, G3, G6, G7, "email-replies"],
    "slack":  [ROUTER, G1, G2, G3, G6, G7, "slack-messages"],
    "deck":   [ROUTER, G1, G2, G3, G6, G7, "slide-decks"],
    "message": [ROUTER, G1, G2, G3, G6, G7],
    "short":  [ROUTER, G1, G2],
}
LABELS = {
    "prose": "a document", "github": "a GitHub review, comment or description",
    "jira": "a Jira ticket or comment", "email": "an email", "slack": "a Slack message",
    "deck": "a slide deck", "message": "a message on a shared system",
    "short": "a commit message",
}

PROSE_EXT = (".md", ".mdx", ".txt", ".rst", ".adoc")
TAGS = re.compile(r"(?is)<(script|style)\b.*?</\1\s*>|<[^>]+>")
# Files that are instructions or state for the assistant, never text for a reader.
SKIP_PATH = re.compile(
    r"(/\.claude/|/claude/skills/[^/]+/|/node_modules/|/\.git/|/\.taste-skill/|/(CLAUDE|AGENTS|MEMORY)\.md$|/LICEN[CS]E|/CHANGELOG\.md$|/requirements[^/]*\.txt$|/robots\.txt$)"
)


def html_is_document(path, content):
    """An .html file is gated when it reads as prose, not when it is an application."""
    text = content
    if text is None:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return False
    prose = re.sub(r"\s+", " ", TAGS.sub(" ", text)).strip()
    return len(prose) >= 1500


def file_surface():
    path = inp.get("file_path") or ""
    if not path:
        return None
    full = os.path.realpath(os.path.expanduser(path))
    if SKIP_PATH.search(full) or SKIP_PATH.search(path):
        return None
    low = full.lower()
    deck = bool(re.search(r"(slides?|deck)[^/]*\.(md|html)$|/(slides?|decks?)/", low))
    if low.endswith(PROSE_EXT):
        return "deck" if deck else "prose"
    if low.endswith((".html", ".htm")):
        if html_is_document(full, inp.get("content")):
            return "deck" if deck else "prose"
    return None


def gh_api_mutation(cmd, raw):
    if not re.search(r"\bgh\s+api\b", cmd):
        return False
    method = re.search(r"(?:-X|--method)[=\s]+([A-Za-z]+)", cmd)
    if method:
        return method.group(1).upper() not in ("GET", "HEAD")
    if re.search(r"\bgh\s+api\s+graphql\b", cmd):
        return bool(re.search(r"\bmutation\b\s*[({\w]", raw))
    return bool(re.search(r"\s-[fF]\s|--field|--raw-field|--input", cmd))


def bash_surface():
    raw = inp.get("command", "") or ""
    # Quoted strings are data (a commit body, a grep pattern), never the command.
    cmd = re.sub(r"'[^']*'|\"[^\"]*\"", " ", raw)
    if re.search(r"\bgh\s+(pr|issue)\s+(comment|review|edit|create|close)\b", cmd) or re.search(r"\bgh\s+release\s+(create|edit)\b", cmd):
        return "github"
    if gh_api_mutation(cmd, raw):
        return "github"
    if re.search(r"\bgit\s+(-C\s+\S+\s+)?commit\b", cmd) and not re.search(r"--no-edit|--fixup|-C\s+HEAD|--reuse-message", cmd):
        return "short"
    # The router's clipboard rules sit in the Slack row; slack-messages.md holds the rich-text ones.
    if re.search(r"(^|[|;&]\s*)pbcopy\b", cmd):
        return "slack"
    return None


MCP_LOCAL = re.compile(r"^mcp__(rag|ccd_[a-z_]+|scheduled-tasks|computer-use|Claude_Browser|claude-in-chrome|visualize|terminal|mcp-registry|Claude_Code_iOS_Simulator|easel)__")
READ_VERBS = re.compile(r"^(notion-)?(search|list|get|fetch|read|query|download|find|analy[sz]e|suggest|check|wait|show|refresh|export|batch_triage|manage_capabilities)", re.I)
TEXT_VERBS = re.compile(r"(send|reply|forward|post|publish|create|update|comment|edit|draft|write|execute)", re.I)


def mcp_surface():
    if MCP_LOCAL.match(tool):
        return None
    name = tool.rsplit("__", 1)[-1]
    if READ_VERBS.match(name) or not TEXT_VERBS.search(name):
        return None
    blob = (tool + " " + json.dumps(inp)[:4000]).lower()
    if "slack" in blob:
        return "slack"
    if "jira" in blob or "atlassian" in blob or "confluence" in blob:
        return "jira"
    if re.search(r"airmail|gmail|outlook|send_email|reply_to_message|forward_message|quick_reply", blob):
        return "email"
    if "github" in blob:
        return "github"
    return "message"


if tool in ("Write", "Edit", "MultiEdit"):
    surface = file_surface()
elif tool == "Bash":
    surface = bash_surface()
elif tool.startswith("mcp__"):
    surface = mcp_surface()
else:
    surface = None
if not surface:
    sys.exit(0)

# A subagent has its own transcript; the guides must be in its context, not the parent's.
transcript = call.get("agent_transcript_path") or call.get("transcript_path") or ""
read = set()
for rec in _records(transcript) or []:
    if rec.get("subtype") == "compact_boundary" or rec.get("isCompactSummary"):
        read.clear()
        continue
    if rec.get("type") != "assistant":
        continue
    for block in (rec.get("message") or {}).get("content") or []:
        if not (isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Read"):
            continue
        args = block.get("input") or {}
        if args.get("limit") or (args.get("offset") or 0) > 1:
            continue  # a partial read does not put the guide in context
        p = os.path.realpath(os.path.expanduser(args.get("file_path") or ""))
        if os.path.dirname(p) == GUIDES and p.endswith(".md"):
            read.add(os.path.basename(p)[:-3])

missing = [g for g in PROFILES[surface] if g not in read]
if not missing:
    sys.exit(0)

# An edit to a file that already exists may be made on the checklist, which condenses guides
# 1, 2, 3, 5, 6 and 7 one rule per line (about 3,000 tokens against about 40,000 for the set).
# A new document, and every write that leaves this machine, still needs the full profile.
CHECKLIST = "edit-doc-checklist"
small_edit = (
    tool in ("Edit", "MultiEdit")
    and surface in ("prose", "deck")
    and os.path.isfile(os.path.realpath(os.path.expanduser(inp.get("file_path") or "")))
)
if small_edit:
    short = [CHECKLIST] + (["slide-decks"] if surface == "deck" else [])
    if all(g in read for g in short):
        sys.exit(0)
    missing = [g for g in short if g not in read]

paths = "\n".join(f"  {GUIDES}/{g}.md" for g in missing)
sys.stderr.write(
    f"writing gate: this call writes {LABELS[surface]}, and the writing guides for it have not been read in this session"
    " (or not since its last compaction).\n"
    f"Read each of these in full (no offset, no limit), then write the text to them and to the medium's own\n"
    f"formatting rules, and make the call again:\n{paths}\n"
    "Do not ask Warren whether to follow the guides and do not tell him the gate fired: read them and carry on.\n"
)
sys.exit(2)
PY
