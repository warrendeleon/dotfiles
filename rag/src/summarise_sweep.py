"""Sweep finished Claude Code sessions into wiki summary pages.

This is the single producer behind the resume feature. It is run three ways,
all funnelling through the same gate and ledger so they never double-write:

- a launchd timer (the spine): summarise any finished, substantial session not
  already handled, catching even hard-killed sessions on the next tick;
- a SessionEnd hook (immediacy): summarise one named session the moment it ends;
- a one-off backfill: the same sweep over all history, with Sonnet.

A session is "finished" when its transcript has been idle past a threshold, or
when SessionEnd names it explicitly. The ledger skips anything already summarised
at its current size, so repeated runs are cheap and resumable.
"""

from __future__ import annotations

import argparse
import fcntl
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Iterable, Iterator

from .parsers.jsonl import parse_conversation
from .queue_db import JobQueue, JobType, _file_hash
from .summariser import (
    DEFAULT_MODEL,
    HollowSummary,
    build_text,
    has_content,
    lint,
    machine_folder,
    parse_date_from_turns,
    parse_summary,
    render_page,
    run_claude,
    slugify,
)
from .summary_ledger import SummaryLedger
from .watcher import CLAUDE_PROJECTS_DIR, EXCLUDED_PROJECT_SUFFIXES

logger = logging.getLogger(__name__)

# Wiki area that summaries are written into, split by domain.
# Overridable via RAG_WIKI_ROOT for multi-machine layouts and testing.
WIKI_SESSIONS_ROOT = Path(os.environ.get("RAG_WIKI_ROOT") or (Path.home() / ".wiki" / "wiki"))

# A session is treated as finished once its transcript has been idle this long.
# Long enough that the live session is never summarised mid-flight.
DEFAULT_IDLE_MINUTES = 30

# Going-forward model is config-driven; the backfill overrides to Sonnet.
CONFIG_PATH = Path.home() / ".rag" / "config.yaml"

# A single advisory lock so a manual backfill and a timer tick never run
# concurrently and double-spend on the same work.
LOCK_PATH = Path.home() / ".rag" / "summariser.lock"


def acquire_lock():
    """Take a non-blocking process lock. Returns the file handle, or None if held."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh

# Markers that route a session to the hl/ domain. The ~/Developer catch-all dir
# mixes personal and HL work, so dir name alone is not enough; the transcript
# text is sniffed too.
_HL_DIR_MARKERS = ("-hl-", "hargreaves", "ucx")
_HL_TEXT_MARKERS = ("hargreaves", "hl-mobile", "ucx-core", "/hl/", "gitlab")


def _now() -> float:
    return time.time()


# The hub the sync uses; a session's origin machine is read from its per-machine
# trees there. Same preference order as sync.sh's SSH_HOSTS.
HUB_HOSTS = ("minipc-lan", "minipc-tailscale")


def local_machine_id() -> str:
    """This machine's id (matches sync.sh's machine-id); origin for native sessions."""
    try:
        mid = (Path.home() / ".rag" / "machine-id").read_text().strip()
        return mid or "unknown"
    except OSError:
        return "unknown"


def hub_session_origins() -> dict[str, str]:
    """Map session_id -> origin machine id, read from the hub's per-machine trees.

    A foreign session loses its origin when it merges into the local projects
    dir, but the hub keeps it (claude-sync/<machine>/...). Best-effort: if no hub
    is reachable, callers fall back to the local machine.
    """
    origins: dict[str, str] = {}
    for hub in HUB_HOSTS:
        try:
            out = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", hub,
                 "find ~/claude-sync -name '*.jsonl'"],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.SubprocessError, OSError):
            continue
        if out.returncode != 0:
            continue
        for line in out.stdout.splitlines():
            parts = line.strip().split("/")
            if "claude-sync" not in parts or not parts[-1].endswith(".jsonl"):
                continue
            i = parts.index("claude-sync")
            if i + 1 < len(parts):
                origins[parts[-1][:-6]] = parts[i + 1]
        return origins  # first reachable hub wins
    logger.warning("hub unreachable; session origins default to local machine")
    return origins


def load_summary_model() -> str:
    """Read the going-forward summary model from config, default Haiku."""
    try:
        import yaml
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                cfg = yaml.safe_load(f) or {}
            model = cfg.get("summary_model")
            if model:
                return str(model)
    except Exception:
        logger.debug("Could not read summary_model from config")
    return DEFAULT_MODEL


def detect_domain(project: str, text_sample: str) -> str:
    """Classify a session as 'hl' or 'personal'.

    Dedicated HL project dirs win outright. Otherwise the transcript text is
    sniffed for HL markers, since the ~/Developer dir holds both kinds of work.
    Borderline cases (a personal session that names an HL path) route to hl,
    erring toward the stricter category.
    """
    proj = project.lower()
    if any(m in proj for m in _HL_DIR_MARKERS):
        return "hl"
    low = text_sample.lower()
    if any(m in low for m in _HL_TEXT_MARKERS):
        return "hl"
    return "personal"


def transcript_date(path: Path) -> str:
    """Session date as YYYY-MM-DD, from the file's last-modified time.

    mtime tracks when Claude Code last wrote the transcript, so it is the
    session's own date and never "today".
    """
    return time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))


def iter_transcripts(projects_dir: Path | None = None) -> Iterator[Path]:
    """Yield every conversation transcript, minus the excluded project dirs."""
    projects_dir = projects_dir or CLAUDE_PROJECTS_DIR
    if not projects_dir.exists():
        return
    for path in projects_dir.glob("*/*.jsonl"):
        full = str(path)
        if any(suffix in full for suffix in EXCLUDED_PROJECT_SUFFIXES):
            continue
        yield path


def is_finished(path: Path, idle_minutes: int, now: float) -> bool:
    """True if the transcript has been idle long enough to be done."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return (now - mtime) >= idle_minutes * 60


def needs_summary(
    path: Path,
    ledger: SummaryLedger,
    now: float,
    wiki_ids: frozenset[str] = frozenset(),
) -> bool:
    """Decide whether a session still needs summarising.

    Two layers:
    - Global dedup on the session id against the shared wiki. The JSONL stem is
      a globally-unique session UUID, written into every page's `session_id`.
      If a page already exists for it and this machine has no ledger record,
      another source already covered it (another RAG machine, or this machine
      before its ledger was wiped); skip. The synced wiki is the source of
      truth, so this holds across machines and survives a lost ledger.
    - Local ledger as a fast cache: gates on mtime versus the last write, so an
      unchanged transcript is skipped without hashing a possibly huge file, and
      a session that grew is re-summarised by the machine that owns it.
    """
    session_id = path.stem
    row = ledger.get(session_id)
    if row is None:
        # New to this machine. Skip only if the shared wiki already has it.
        return session_id not in wiki_ids
    if row["status"] not in ("written", "needs-review", "skipped"):
        return True  # retry a prior error
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return mtime > row["updated_at"]


def _iter_session_pages():
    """Every session page, in the machine layout plus the legacy domain layout."""
    roots = [WIKI_SESSIONS_ROOT / "sessions"]
    roots += [WIKI_SESSIONS_ROOT / d / "sessions" for d in ("personal", "hl")]
    for root in roots:
        if not root.is_dir():
            continue
        # machine layout is sessions/<machine>/*.md; legacy is <domain>/sessions/*.md
        yield from root.glob("*/*.md")
        yield from root.glob("*.md")


def wiki_session_ids() -> frozenset[str]:
    """Session ids already summarised in the shared wiki (the global dedup set).

    Reads the `session_id` frontmatter of every session page. Cheap (a few dozen
    small files) and read directly, so it needs no ChromaDB at sweep time. Scans
    both the machine layout and the legacy domain layout during migration.
    """
    ids: set[str] = set()
    for page in _iter_session_pages():
        try:
            text = page.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^session_id:\s*(\S+)\s*$", text, re.MULTILINE)
        if m:
            ids.add(m.group(1).strip())
    return frozenset(ids)


def _write_page(page_text: str, machine: str, date: str, slug: str, session_id: str) -> Path:
    """Write the page under wiki/sessions/<machine>/, disambiguating collisions."""
    sessions_dir = WIKI_SESSIONS_ROOT / "sessions" / machine_folder(machine)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date}-{slug}.md"
    target = sessions_dir / filename
    # Two sessions on the same day with the same slug: append a short id.
    if target.exists() and session_id not in target.read_text(encoding="utf-8"):
        target = sessions_dir / f"{date}-{slug}-{session_id[:8]}.md"
    target.write_text(page_text, encoding="utf-8")
    return target


def summarise_one(
    path: Path,
    ledger: SummaryLedger,
    model: str,
    dry_run: bool = False,
    index_queue: JobQueue | None = None,
    origins: dict[str, str] | None = None,
) -> str:
    """Summarise a single transcript and write its page. Returns a status string."""
    session_id = path.stem
    project = path.parent.name
    # Origin machine: from the hub map for a pulled session, else this machine.
    machine = (origins or {}).get(session_id) or local_machine_id()

    turns = parse_conversation(path)
    text, n_turns = build_text(turns)
    if not has_content(len(text)):
        if not dry_run:
            fhash = _file_hash(str(path))
            ledger.record(session_id, str(path), fhash, None, "skipped", None)
        logger.info("skip (near-empty): %s", session_id[:8])
        return "skipped"

    domain = detect_domain(project, text[:20_000])
    date = parse_date_from_turns(turns) or transcript_date(path)

    if dry_run:
        logger.info("would summarise %s -> %s (turns=%d, chars=%d)",
                    session_id[:8], domain, n_turns, len(text))
        return "dry-run"

    try:
        envelope = run_claude(text, model=model)
        fields = parse_summary(envelope["result"])
    except HollowSummary as e:
        # The model found nothing worth a note: a clean skip, not an error,
        # so it is never retried in a loop.
        logger.info("skip (no substance) %s: %s", session_id[:8], e)
        ledger.record(session_id, str(path), _file_hash(str(path)), None, "skipped", model)
        return "skipped"
    except (RuntimeError, ValueError) as e:
        logger.warning("summary failed for %s: %s", session_id[:8], e)
        ledger.record(session_id, str(path), _file_hash(str(path)), None, "error", model)
        return "error"

    page = render_page(
        fields, date=date, domain=domain, project=project,
        session_id=session_id, model=model, needs_review=False,
        transcript_path=str(path), machine=machine,
    )
    violations = lint(page)
    if violations:
        # Re-render with the needs-review flag so the page itself records it.
        page = render_page(
            fields, date=date, domain=domain, project=project,
            session_id=session_id, model=model, needs_review=True,
            transcript_path=str(path), machine=machine,
        )
        logger.info("flagged needs-review %s: %s", session_id[:8], ", ".join(violations))

    prev = ledger.get(session_id)
    slug = slugify(fields["title"])
    target = _write_page(page, machine, date, slug, session_id)

    # Resume case: a re-summarised session whose title or date changed lands at a
    # new filename. Remove the previous page so the stale one is not orphaned.
    prev_path = prev["page_path"] if prev else None
    if prev_path and prev_path != str(target):
        try:
            old = Path(prev_path)
            if old.is_file():
                old.unlink()
                logger.info("removed superseded page for %s: %s", session_id[:8], old.name)
        except OSError:
            logger.warning("could not remove superseded page %s", prev_path)

    status = "needs-review" if violations else "written"
    ledger.record(session_id, str(path), _file_hash(str(path)), str(target), status, model)

    # Make the new page searchable: enqueue it for the indexer, which embeds it
    # into Chroma and the FTS index with the one shared embedder. Best-effort.
    if index_queue is not None:
        try:
            index_queue.enqueue(str(target), JobType.WIKI.value, priority=50)
        except Exception:
            logger.warning("could not enqueue %s for indexing", target.name)

    logger.info("%s %s -> %s", status, session_id[:8], target)
    return status


def sweep(
    *,
    model: str,
    idle_minutes: int = DEFAULT_IDLE_MINUTES,
    only_session: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    ledger: SummaryLedger | None = None,
    index_queue: JobQueue | None = None,
) -> dict[str, int]:
    """Run the sweep. Returns a count of outcomes by status.

    Processes every finished, unsummarised session. A one-off backfill is just
    this with no limit and a stronger model. Only an explicit --session bypasses
    the idle gate, so a backfill never touches the live session it runs from.
    """
    ledger = ledger or SummaryLedger()
    index_queue = index_queue or JobQueue()
    now = _now()
    counts: dict[str, int] = {}

    # The shared wiki is the global dedup set: any session already summarised
    # there (by this or any machine) is skipped unless this machine owns it.
    wiki_ids = wiki_session_ids()
    # Origin machine per session, so each page is filed under wiki/sessions/<machine>/.
    origins = hub_session_origins()

    candidates: Iterable[Path] = iter_transcripts()
    if only_session:
        candidates = [p for p in candidates if p.stem == only_session]

    processed = 0
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        # Only an explicit --session bypasses the idle gate (SessionEnd knows
        # the session has ended). Everything else waits until a session is quiet.
        if not only_session and not is_finished(path, idle_minutes, now):
            continue
        if not needs_summary(path, ledger, now, wiki_ids):
            continue

        status = summarise_one(path, ledger, model, dry_run=dry_run,
                               index_queue=index_queue, origins=origins)
        counts[status] = counts.get(status, 0) + 1
        processed += 1
        if limit and processed >= limit:
            break

    logger.info("sweep done: %s", counts)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarise finished Claude Code sessions. "
                    "For a one-off backfill: --model sonnet (no --limit).")
    parser.add_argument("--session", help="Summarise only this session id (SessionEnd hook).")
    parser.add_argument("--model", help="Override the summary model (e.g. sonnet for backfill).")
    parser.add_argument("--idle-minutes", type=int, default=DEFAULT_IDLE_MINUTES)
    parser.add_argument("--limit", type=int, help="Stop after N summaries.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be summarised without calling the model.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    lock = None
    if not args.dry_run:
        lock = acquire_lock()
        if lock is None:
            logger.info("another summariser run holds the lock, exiting")
            return

    model = args.model or load_summary_model()
    try:
        sweep(
            model=model,
            idle_minutes=args.idle_minutes,
            only_session=args.session,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    main()
