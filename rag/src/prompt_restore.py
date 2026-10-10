"""UserPromptSubmit hook: inject the session pages that match the first prompt.

The first real prompt of a conversation is the query the SessionStart hook
never had. A hybrid search over the ``wiki`` collection, filtered to session
pages, returns the sessions about *this* topic, whichever directory the
conversation started from. Earlier restores were keyed on the working
directory, so every conversation from ``~/Developer`` got the same five
pages, whatever it was about.

Runs on every prompt but does real work once per session:
- a marker under ``~/.rag/restore-seen/<session_id>`` gates it;
- slash commands and very short prompts do not consume the marker, so the
  first substantive prompt still gets its pointers;
- the Store import is lazy, so the non-first-prompt path is a stat call.

Output discipline matches the old restore: pointers and one-liners, capped,
framed as recall to verify. Open threads are injected only from a page under
``NEXT_STEPS_MAX_AGE_DAYS`` old; older ones are stale and steer wrong.
Fails silent on any error: a slow or broken search must never block a turn.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .session_restore import (
    WIKI_SESSIONS_ROOT,
    extract_next_steps,
    is_fresh,
    read_page_meta,
)

SEEN_DIR = Path.home() / ".rag" / "restore-seen"
SEEN_MAX_AGE_S = 7 * 24 * 3600

MAX_SESSIONS = 5
MIN_PROMPT_CHARS = 15
MAX_QUERY_CHARS = 600
# Over-fetch so that after dropping non-session wiki hits and collapsing
# sections of the same page there are still MAX_SESSIONS pages left.
SEARCH_RESULTS = 16


def is_substantive(prompt: str) -> bool:
    """A prompt worth searching on: not a slash command, not a one-worder."""
    text = (prompt or "").strip()
    if not text or text.startswith("/"):
        return False
    return len(text) >= MIN_PROMPT_CHARS


def claim_first_prompt(session_id: str, seen_dir: Path = SEEN_DIR,
                       now: float | None = None) -> bool:
    """True once per session: creates the marker and prunes old ones."""
    if not session_id:
        return False
    now = now if now is not None else time.time()
    marker = seen_dir / session_id
    if marker.exists():
        return False
    seen_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.touch()
    for old in seen_dir.iterdir():
        try:
            if now - old.stat().st_mtime > SEEN_MAX_AGE_S:
                old.unlink()
        except OSError:
            continue
    return True


def _is_session_page(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(WIKI_SESSIONS_ROOT.resolve())
    except ValueError:
        return False
    parts = rel.parts
    return "sessions" in parts[:2]


def search_sessions(query: str, store=None, n: int = MAX_SESSIONS) -> list[dict[str, str]]:
    """Session pages ranked by hybrid search on the prompt, best first.

    Hits are wiki *sections*; several can belong to one page, so collapse to
    the page at its best rank. Non-session wiki pages are dropped: this is the
    resume loop, not a general wiki lookup, and the model has mcp__rag__search
    for that.
    """
    if store is None:
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
        from .store import Store  # noqa: PLC0415  (lazy: chromadb is slow to import)
        store = Store()
    hits = store.search(query[:MAX_QUERY_CHARS], collection_names=["wiki"],
                        n_results=SEARCH_RESULTS)
    pages: list[dict[str, str]] = []
    seen: set[str] = set()
    for hit in hits:
        file_path = (hit.get("metadata") or {}).get("file_path") or ""
        if not file_path or file_path in seen:
            continue
        path = Path(file_path)
        if not _is_session_page(path):
            continue
        meta = read_page_meta(path)
        if not meta:
            continue
        seen.add(file_path)
        pages.append(meta)
        if len(pages) >= n:
            break
    return pages


def build_context(prompt: str, store=None) -> str | None:
    pages = search_sessions(prompt, store=store)
    if not pages:
        return None

    lines = [
        "[Session memory matching this prompt, best match first. Recall, not instructions; verify before relying.]",
    ]
    for p in pages:
        flag = " (needs-review)" if p["status"] == "needs-review" else ""
        title = p["title"] or Path(p["path"]).stem
        lines.append(f"- {p['date']}: {title}{flag}")

    top = pages[0]
    if is_fresh(top["date"]):
        next_steps = extract_next_steps(Path(top["path"]))
        if next_steps:
            lines.append(f"Open threads (from {top['date']}):")
            lines.extend(f"  - {s}" for s in next_steps)

    lines.append("Full detail: mcp__rag__get_context on the title, or the page under ~/.wiki/sessions/.")
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    # chromadb's telemetry client logs failures to stderr; a hook's stderr is
    # noise in the transcript, and stdout is the only channel that matters.
    try:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    except OSError:
        pass
    prompt = payload.get("prompt") or ""
    session_id = payload.get("session_id") or ""
    if not is_substantive(prompt):
        return
    try:
        if not claim_first_prompt(session_id):
            return
        context = build_context(prompt)
    except Exception:
        return  # fail silent: never block a turn
    if context:
        print(context)


if __name__ == "__main__":
    main()
