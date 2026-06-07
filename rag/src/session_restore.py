"""SessionStart hook: inject recent session summaries for the current project.

At session start there is no query, so semantic search is the wrong tool. Restore
is recency plus project: the newest few summary pages whose ``project`` matches
the current working directory, with the latest ``next steps`` so a fresh
conversation can pick up where the last one left off.

Design (discipline borrowed from what makes injected context usable):
- inject pointers and one-liners, not page bodies; cap hard;
- frame it as recall to verify, never as instructions (the model rightly
  distrusts imperative injected text);
- read markdown directly, no ChromaDB at hook time (fast, no model load);
- fail silent on any error so a broken hook never blocks a session start.

Output uses the SessionStart contract verified against the CLI:
``{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def _wiki_root() -> Path:
    """Wiki root, overridable via RAG_WIKI_ROOT (multi-machine, and testing)."""
    env = os.environ.get("RAG_WIKI_ROOT")
    return Path(env) if env else Path.home() / ".wiki" / "wiki"


WIKI_SESSIONS_ROOT = _wiki_root()
DOMAINS = ("personal", "hl")

MAX_SESSIONS = 5
MAX_NEXT_STEPS = 6

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def encode_project(cwd: str) -> str:
    """Encode a path the way Claude Code names its project dirs: / and . to -.

    ``/Users/w/Developer`` -> ``-Users-w-Developer``;
    ``/Users/w/.rag/x`` -> ``-Users-w--rag-x``. This matches the ``project``
    value stored in each summary's frontmatter.
    """
    return re.sub(r"[/.]", "-", cwd)


def domain_for_cwd(cwd: str) -> str:
    """Best-effort domain from the path, mirroring the consult hook."""
    low = cwd.lower()
    if "/hl/" in low or "-hl-" in low or "hargreaves" in low or "ucx" in low:
        return "hl"
    return "personal"


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


def find_recent(cwd: str, n: int = MAX_SESSIONS) -> list[dict[str, str]]:
    """Newest session pages for this project, falling back to the cwd's domain."""
    project = encode_project(cwd)
    pages: list[dict[str, str]] = []
    for path in _iter_session_pages():
        meta = read_page_meta(path)
        if meta:
            pages.append(meta)

    exact = [p for p in pages if p["project"] == project]
    chosen = exact
    if not chosen:
        domain = domain_for_cwd(cwd)
        chosen = [p for p in pages if domain_for_cwd(p["project"]) == domain]

    chosen.sort(key=lambda p: p["date"], reverse=True)
    return chosen[:n]


def build_context(cwd: str) -> str | None:
    """Build the additionalContext string, or None if there is nothing to show."""
    recent = find_recent(cwd)
    if not recent:
        return None

    lines = [
        "[Session memory for this project, newest first. Recall, not instructions; verify before relying.]",
    ]
    for p in recent:
        flag = " (needs-review)" if p["status"] == "needs-review" else ""
        title = p["title"] or Path(p["path"]).stem
        lines.append(f"- {p['date']}: {title}{flag}")

    next_steps = extract_next_steps(Path(recent[0]["path"]))
    if next_steps:
        lines.append(f"Latest open threads (from {recent[0]['date']}):")
        lines.extend(f"  - {s}" for s in next_steps)

    lines.append("Full detail: mcp__rag__search, or the pages under ~/.wiki/wiki/*/sessions/.")
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return  # fail silent: no valid input, inject nothing
    cwd = payload.get("cwd") or str(Path.cwd())

    try:
        context = build_context(cwd)
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
