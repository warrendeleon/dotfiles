"""SessionStart hook: report summariser health, and share the page helpers.

Session pointers are no longer chosen here. At session start there is no
query, and the working directory is a poor proxy for the topic (every
conversation started from ``~/Developer`` was handed the same five pages).
``prompt_restore.py`` picks them by a RAG query on the first real prompt.

What this hook still does is the one alert that cannot be missed: if the
summariser has been failing, say so at the top of every new conversation.
The loop once failed silently for seven weeks because nothing surfaced it.

Design (discipline borrowed from what makes injected context usable):
- inject one line, not a report; cap hard;
- frame it as recall to verify, never as instructions;
- read SQLite and markdown directly, no ChromaDB at hook time;
- fail silent on any error so a broken hook never blocks a session start.

Output uses the SessionStart contract verified against the CLI:
``{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}``.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path


def _wiki_root() -> Path:
    """Wiki root, overridable via RAG_WIKI_ROOT (multi-machine, and testing)."""
    env = os.environ.get("RAG_WIKI_ROOT")
    return Path(env) if env else Path.home() / ".wiki"


WIKI_SESSIONS_ROOT = _wiki_root()
DOMAINS = ("personal", "hl")

MAX_NEXT_STEPS = 6
# Open threads older than this are stale by definition: the work has moved on
# or been dropped, and injecting them steers a fresh conversation wrong.
NEXT_STEPS_MAX_AGE_DAYS = 7
# Window the health line looks back over. One failed sweep in a day is noise;
# a day of failures is the loop being down.
HEALTH_WINDOW_S = 24 * 3600

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _front_value(frontmatter: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*\"?(.*?)\"?\s*$", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else ""


def read_page_meta(path: Path) -> dict[str, str] | None:
    """Pull the frontmatter fields the restore needs. None if not a session page."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return None
    fm = m.group(1)
    if _front_value(fm, "type") != "session":
        return None
    return {
        "path": str(path),
        "title": _front_value(fm, "title"),
        "date": _front_value(fm, "date"),
        "status": _front_value(fm, "status"),
        "project": _front_value(fm, "project"),
    }


def extract_next_steps(path: Path, limit: int = MAX_NEXT_STEPS) -> list[str]:
    """Return the bullets under the page's '## Next steps' section."""
    try:
        body = path.read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"^##\s+Next steps\s*$(.*?)(^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    steps = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- "):
            item = line[2:].strip()
            if item and item != "(none recorded)":
                steps.append(item)
    return steps[:limit]


def is_fresh(date_str: str, today: dt.date | None = None,
             max_age_days: int = NEXT_STEPS_MAX_AGE_DAYS) -> bool:
    """True if a page's YYYY-MM-DD date is within max_age_days of today.

    An unparseable or missing date is not fresh: better to drop stale threads
    than to inject them on a guess.
    """
    try:
        page_date = dt.date.fromisoformat(date_str.strip()[:10])
    except (ValueError, AttributeError):
        return False
    today = today or dt.date.today()
    return 0 <= (today - page_date).days <= max_age_days


def _iter_session_pages():
    """Session pages across machine folders (sessions/<machine>/) and the legacy
    domain layout (<domain>/sessions/), so restore works during migration."""
    roots = [WIKI_SESSIONS_ROOT / "sessions"]
    roots += [WIKI_SESSIONS_ROOT / d / "sessions" for d in DOMAINS]
    for root in roots:
        if not root.is_dir():
            continue
        yield from root.glob("*/*.md")
        yield from root.glob("*.md")


def health_line(ledger=None, now: float | None = None,
                window_s: int = HEALTH_WINDOW_S) -> str | None:
    """One line if the summariser has failed inside the window, else None.

    Reads the done-ledger directly (SQLite, no model). The ledger import is
    lazy so a missing package never breaks the hook.
    """
    if ledger is None:
        from .summary_ledger import SummaryLedger  # noqa: PLC0415
        ledger = SummaryLedger()
    now = now if now is not None else time.time()
    failing = ledger.failures_since(now - window_s)
    if not failing:
        return None
    last_ok = ledger.last_success_at()
    last_err = ledger.last_error_at()
    # Errors that are older than the newest success are a backlog being
    # retried, not an outage: the loop is writing pages again.
    if last_ok is not None and last_err is not None and last_ok > last_err:
        return None
    since = (dt.datetime.fromtimestamp(last_ok).strftime("%Y-%m-%d")
             if last_ok else "never")
    return (
        f"[Session summariser is failing: {failing} session(s) errored in the last "
        f"{window_s // 3600}h, last page written {since}. Tell Warren; the usual "
        "cause is an expired `claude` login (`claude auth login`). "
        "Log: ~/.rag/logs/summariser.err]"
    )


def build_context() -> str | None:
    """Build the additionalContext string, or None if there is nothing to say."""
    return health_line()


def main() -> None:
    try:
        json.load(sys.stdin)
    except Exception:
        return  # fail silent: no valid input, inject nothing

    try:
        context = build_context()
    except Exception:
        return  # fail silent: a broken restore must never block a session
    if not context:
        return

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
