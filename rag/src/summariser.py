"""Summarise content via `claude -p --model haiku` with rate limiting and fallback."""

from __future__ import annotations

import logging
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

# Rate limiting: 20 calls per minute
RATE_LIMIT = 20
RATE_WINDOW = 60  # seconds

# Prompts by content type
PROMPTS = {
    "conversation": (
        "Summarise this conversation turn concisely. "
        "Keep: the user's question/request, key decisions made, solutions found, and outcomes. "
        "Strip: tool calls, file contents, system reminders, thinking blocks, raw code output. "
        "Output a 2-4 sentence summary."
    ),
    "code": (
        "Summarise this source code file concisely. "
        "Keep: component/function purpose, key props/parameters, important logic, patterns used. "
        "Strip: imports, boilerplate, StyleSheet definitions, verbose JSX. "
        "Output a 2-4 sentence summary."
    ),
    "markdown": (
        "Summarise this markdown document concisely. "
        "Keep: key concepts, decisions, requirements, action items. "
        "Strip: formatting, table of contents, redundant headers. "
        "Output a 2-4 sentence summary."
    ),
    "config": (
        "Summarise this configuration file concisely. "
        "Keep: non-default settings, custom values, important overrides. "
        "Strip: comments, default values, boilerplate. "
        "Output a 1-2 sentence summary."
    ),
}


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, max_calls: int = RATE_LIMIT, window: float = RATE_WINDOW) -> None:
        self._max_calls = max_calls
        self._window = window
        self._calls: list[float] = []
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until a call slot is available."""
        while True:
            with self._lock:
                now = time.time()
                # Remove expired entries
                self._calls = [t for t in self._calls if now - t < self._window]
                if len(self._calls) < self._max_calls:
                    self._calls.append(now)
                    return
                # Calculate wait time
                oldest = self._calls[0]
                wait_time = self._window - (now - oldest) + 0.1
            time.sleep(wait_time)


_rate_limiter = RateLimiter()


def summarise(text: str, content_type: str = "conversation") -> str | None:
    """Summarise text using claude -p --model haiku.

    Returns the summary, or None on failure.
    """
    prompt = PROMPTS.get(content_type, PROMPTS["conversation"])

    # Truncate input to avoid overwhelming haiku
    max_input = 50_000
    if len(text) > max_input:
        text = text[:max_input] + "\n\n[truncated]"

    _rate_limiter.wait()

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", prompt],
            input=text,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.warning("claude -p failed (exit %d): %s", result.returncode, result.stderr[:200])
            return None

        summary = result.stdout.strip()
        if not summary:
            return None

        return summary

    except subprocess.TimeoutExpired:
        logger.warning("claude -p timed out")
        return None
    except FileNotFoundError:
        logger.warning("claude CLI not found")
        return None
    except Exception:
        logger.exception("Unexpected error in summarise")
        return None


def fallback_extract(text: str, max_chars: int = 2000) -> str:
    """Fallback: return first N chars when summarisation fails."""
    if len(text) <= max_chars:
        return text
    # Try to cut at a sentence boundary
    cutoff = text[:max_chars]
    last_period = cutoff.rfind(".")
    if last_period > max_chars // 2:
        return cutoff[: last_period + 1]
    return cutoff
