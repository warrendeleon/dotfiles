"""Parse Claude Code conversation JSONL files into indexable turns."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# No hard file size limit. Large files are streamed line by line.
# Individual turns that exceed the summary threshold get flagged.

# Content block types to strip from assistant messages
STRIP_CONTENT_TYPES = {"tool_use", "tool_result", "thinking"}

# Regex to strip <system-reminder>...</system-reminder> blocks
SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>",
    re.DOTALL,
)

# Max chars before a turn needs summarisation
SUMMARY_THRESHOLD = 10_000


def _extract_text(content: Any) -> str:
    """Extract plain text from a message content field."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                # Skip tool_use, tool_result, thinking, image blocks
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)

    return ""


def _clean_text(text: str) -> str:
    """Strip system reminders and excessive whitespace."""
    text = SYSTEM_REMINDER_RE.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _get_message_content(msg: dict[str, Any]) -> str:
    """Extract content from a JSONL message, handling the nested structure.

    Claude Code JSONL uses: {"type": "user", "message": {"role": "user", "content": "..."}}
    The content is inside the nested 'message' object, not at the top level.
    """
    # Try nested message.content first (Claude Code format)
    inner = msg.get("message")
    if isinstance(inner, dict):
        content = inner.get("content", "")
        if content:
            return _extract_text(content)

    # Fall back to top-level content
    content = msg.get("content", "")
    if content:
        return _extract_text(content)

    return ""


def _extract_session_metadata(path: Path) -> dict[str, str]:
    """Extract metadata from the JSONL file path."""
    meta: dict[str, str] = {}

    # Session ID from filename
    stem = path.stem
    meta["session_id"] = stem

    # Project path from parent directories
    # Pattern: ~/.claude/projects/<encoded-project-path>/<session>.jsonl
    parent = path.parent.name
    if parent and parent != "projects":
        meta["project_path"] = parent
        meta["project"] = parent

    return meta


def parse_conversation(path: str | Path) -> list[dict[str, Any]]:
    """Parse a JSONL conversation file into indexable turn documents.

    Each turn pairs a user message with its assistant response.
    Returns a list of dicts with keys: text, metadata, needs_summary.

    Streams the file line by line so large files (300MB+) are handled
    without loading the entire file into memory.
    """
    path = Path(path)
    if not path.exists() or not path.suffix == ".jsonl":
        return []

    session_meta = _extract_session_metadata(path)

    # Stream and filter to user/assistant messages only
    filtered: list[tuple[str, dict[str, Any]]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type in ("human", "user"):
                    filtered.append(("user", msg))
                elif msg_type == "assistant":
                    filtered.append(("assistant", msg))
    except OSError:
        logger.exception("Failed to read %s", path)
        return []

    # Group into turns (user Q + assistant A)
    turns: list[dict[str, Any]] = []
    i = 0
    turn_number = 0
    while i < len(filtered):
        role, msg = filtered[i]

        if role == "user":
            user_text = _clean_text(_get_message_content(msg))

            # Look for the next assistant response
            assistant_text = ""
            if i + 1 < len(filtered) and filtered[i + 1][0] == "assistant":
                assistant_text = _clean_text(_get_message_content(filtered[i + 1][1]))
                i += 2
            else:
                i += 1

            if not user_text and not assistant_text:
                continue

            turn_number += 1
            combined = f"User: {user_text}\n\nAssistant: {assistant_text}" if assistant_text else f"User: {user_text}"

            metadata = {
                **session_meta,
                "turn_number": turn_number,
                "file_path": str(path),
                "source_type": "conversation",
            }

            # Get timestamp from message if available
            ts = msg.get("timestamp") or msg.get("created_at")
            if ts:
                metadata["timestamp"] = str(ts)

            turns.append({
                "text": combined,
                "metadata": metadata,
                "needs_summary": len(combined) > SUMMARY_THRESHOLD,
                "identifier": f"{path.stem}:turn:{turn_number}",
            })
        else:
            # Orphan assistant message without a preceding user message
            i += 1

    return turns
