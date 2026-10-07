"""Shared transcript reader for the consent and reply-length gates.

Claude Code writes the session transcript as JSONL. Human turns are records with
type "user" whose message content is a string or text blocks; tool results are
also type "user" but carry tool_result blocks and a toolUseResult key. Assistant
turns are type "assistant" with text and tool_use blocks.
"""
import json
import re

TAG_RE = re.compile(
    r"<(system-reminder|local-command-stdout|command-name|command-message|command-args|local-command-caveat)>.*?</\1>",
    re.S,
)
# A quoted reply from the app arrives prefixed with an HTML comment. Left in
# place it makes the turn look like markup, and _is_human drops it, so a go
# word inside a quoted reply was invisible to the consent gate (10 Sep).
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FENCE_RE = re.compile(r"```.*?```", re.S)


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(parts) if parts else None
    return None


def _records(path):
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for line in fh:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def _is_human(rec):
    if rec.get("type") != "user" or rec.get("isSidechain") or rec.get("isMeta"):
        return False
    if "toolUseResult" in rec:
        return False
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
        return False
    t = _text(c)
    if t is None:
        return False
    t = COMMENT_RE.sub("", TAG_RE.sub("", t)).strip()
    return bool(t) and not t.startswith("<")


def _queued_human(rec):
    """A message Warren sent mid-turn arrives as a queued_command attachment."""
    if rec.get("type") != "attachment":
        return None
    a = rec.get("attachment") or {}
    if a.get("type") == "queued_command" and (a.get("origin") or {}).get("kind") == "human":
        return (a.get("prompt") or "").strip() or None
    return None


def human_turns(path):
    """Return every human message in order, oldest first."""
    out = []
    for rec in _records(path):
        queued = _queued_human(rec)
        if queued:
            out.append(queued)
        elif _is_human(rec):
            out.append(COMMENT_RE.sub("", TAG_RE.sub("", _text(rec["message"]["content"]))).strip())
    return out


# A background task finishing, or a CI-monitor event from the desktop app (5 Oct 2026, PR
# auto-fix), each starts a new turn without Warren saying anything.
NOTIFICATION_RE = re.compile(r"\s*<(task-notification|ci-monitor-event)\b")


def _is_notification(rec):
    """A background agent or command finishing starts a new turn without Warren saying anything."""
    if rec.get("type") != "user" or rec.get("isSidechain"):
        return False
    t = _text((rec.get("message") or {}).get("content"))
    return bool(t) and bool(NOTIFICATION_RE.match(TAG_RE.sub("", t)))


def last_turns(path):
    """Return (last_human_text, assistant_prose_of_the_current_turn).

    Assistant text is every text block emitted since the turn began, joined, with
    fenced code blocks removed so a requested command or snippet does not count as
    prose. A turn begins at a human message or at a task notification: replies to
    several notifications after one short message were being summed as one reply
    and bounced at 300 words for a one-line status (2 Oct 2026, SCB-6338 agents).
    """
    human = None
    assistant = []
    for rec in _records(path):
        queued = _queued_human(rec)
        if queued:
            human = queued
            assistant = []
        elif _is_human(rec):
            human = COMMENT_RE.sub("", TAG_RE.sub("", _text(rec["message"]["content"]))).strip()
            assistant = []
        elif _is_notification(rec):
            assistant = []
        elif rec.get("type") == "assistant" and not rec.get("isSidechain"):
            t = _text((rec.get("message") or {}).get("content"))
            if t:
                assistant.append(t)
    return human, FENCE_RE.sub("", "\n".join(assistant))


def words(s):
    return len(re.findall(r"\S+", s or ""))
