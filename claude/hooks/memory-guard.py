#!/usr/bin/env python3
"""PreToolUse hook: memory files hold working rules and wiki triggers, never facts.

The wiki (~/.wiki) is the long-term memory. A Write into a Claude Code memory folder
(~/.claude/projects/<project>/memory/) is refused unless the file is the MEMORY.md index,
a `type: feedback` rule, or a `project` or `reference` trigger whose body points into the
wiki (a ~/.wiki/ path). Facts go on the wiki page for their subject instead.

Edits to existing files are left alone: the hook guards what new memory can be.
"""
import json
import os
import re
import sys

MEMORY_DIR = re.compile(r"/\.claude/projects/[^/]+/memory/")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)
TYPE = re.compile(r"^\s*type:\s*['\"]?([A-Za-z_-]+)", re.M)
WIKI_POINTER = re.compile(r"(~|/Users/[^/\s]+)/\.wiki/")


def is_memory_file(path):
    path = os.path.expanduser(path)
    return bool(MEMORY_DIR.search(path)) and path.endswith(".md") and os.path.basename(path) != "MEMORY.md"


def refusal(tool_name, tool_input):
    """Return the reason to refuse, or None to allow."""
    if tool_name != "Write":
        return None
    path = tool_input.get("file_path", "")
    if not is_memory_file(path):
        return None

    match = FRONTMATTER.match(tool_input.get("content", ""))
    if not match:
        return "it has no frontmatter, so it is not a working rule or a wiki trigger"
    frontmatter, body = match.groups()
    kind_match = TYPE.search(frontmatter)
    kind = kind_match.group(1) if kind_match else ""

    if kind == "feedback":
        return None
    if kind in ("project", "reference") and WIKI_POINTER.search(body):
        return None
    if kind in ("project", "reference"):
        return f"it is a `{kind}` file with no ~/.wiki/ pointer, so it holds facts rather than a trigger into the wiki"
    return f"its type is `{kind or 'missing'}`, and only working rules (`feedback`) or wiki triggers belong in memory"


def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = refusal(event.get("tool_name", ""), event.get("tool_input") or {})
    if reason is None:
        return 0
    message = (
        f"Memory guard: this memory file was refused because {reason}. "
        "The wiki (~/.wiki) is the long-term memory: put the fact on the wiki page for its subject "
        "(search first and add to the existing page; a new page only when none covers it, linked from its index). "
        "If it must be remembered before acting, add a one-line trigger pointing at that page to an existing memory file."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": message,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
