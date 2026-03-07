"""Parse Claude Code conversation JSONL files into indexable turns."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Max file size: 100MB (conversation files can be large but not unbounded)
MAX_FILE_SIZE = 100_000_000

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
        # Decode the directory name (uses - as separator for path components)
        meta["project_path"] = parent
        meta["project"] = parent

    return meta


def parse_conversation(path: str | Path) -> list[dict[str, Any]]:
    """Parse a JSONL conversation file into indexable turn documents.

    Each turn pairs a user message with its assistant response.
    Returns a list of dicts with keys: text, metadata, needs_summary.
    """
    path = Path(path)
    if not path.exists() or not path.suffix == ".jsonl":
        return []

    try:
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            logger.warning("Skipping oversized JSONL: %s (%d bytes)", path, size)
            return []
    except OSError:
        return []

    session_meta = _extract_session_metadata(path)
    turns: list[dict[str, Any]] = []

    # Read all messages
    messages: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue
    except OSError:
        logger.exception("Failed to read %s", path)
        return []

    # Filter to user and assistant messages only
    filtered = []
    for msg in messages:
        msg_type = msg.get("type")
        role = msg.get("role")

        # Support both {type: "human/assistant"} and {role: "user/assistant"}
        if msg_type in ("human", "user") or role == "user":
            filtered.append(("user", msg))
        elif msg_type == "assistant" or role == "assistant":
            filtered.append(("assistant", msg))

    # Group into turns (user Q + assistant A)
    i = 0
    turn_number = 0
    while i < len(filtered):
        role, msg = filtered[i]

        if role == "user":
            user_text = _clean_text(_extract_text(msg.get("content", msg.get("message", ""))))

            # Look for the next assistant response
            assistant_text = ""
            if i + 1 < len(filtered) and filtered[i + 1][0] == "assistant":
                assistant_text = _clean_text(_extract_text(filtered[i + 1][1].get("content", "")))
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
