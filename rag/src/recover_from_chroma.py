"""Recover deleted Claude Code sessions from ChromaDB.

Claude Code's ``cleanupPeriodDays`` deleted the JSONL transcripts, but the
indexed turn text survives in ChromaDB. This rebuilds each deleted session from
its indexed turns, archives a best-effort transcript to ``~/claude-recovered/``,
and summarises the substantial ones into ``wiki/sessions/<machine>/``, reusing
the normal summariser path (build_text -> run_claude -> parse_summary ->
render_page) so recovered pages read exactly like live ones.

Input is one or more dumps produced by ``scripts/chroma_dump.py`` (one turn per
line). A dump named with ``--air-dump`` attributes its sessions to the Air
(mbairm1); every other session is attributed ``unknown`` rather than guessed.
When a session appears in more than one dump (the M5 Max pulled and indexed many
of the Air's sessions), the copy with more turns wins.

Sessions whose transcript still exists on disk are skipped (the normal sweep
owns them), as is anything already in the shared wiki. A checkpoint file makes
the batch resumable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

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
from .summarise_sweep import (
    CLAUDE_PROJECTS_DIR,
    EXCLUDED_PROJECT_SUFFIXES,
    _write_page,
    detect_domain,
    wiki_session_ids,
)

ARCHIVE_ROOT = Path.home() / "claude-recovered"
QUARANTINE_ROOT = ARCHIVE_ROOT / "_quarantine"
CHECKPOINT = Path.home() / ".rag" / "recover-done.tsv"

AIR_MACHINE = "Warrens-MacBook-Air-M1"  # machine_folder -> mbairm1
UNKNOWN_MACHINE = "unknown"

# Recovered sessions go to one honest bucket, not a per-machine folder. Origin
# cannot be trusted: the Air ran the sync and indexed sessions it pulled from
# other machines, and the foreign manifest is a current snapshot, so a
# pulled-then-deleted session is gone from the manifest but still in the index.
# A session attributed to the Air can therefore actually be M5/mbp16/MiniPC work
# (e.g. 47320177, all about the M5-only RAG, indexed on the Air but not in its
# manifest). One "recovered" folder states the provenance without faking origin.
RECOVERED_MACHINE = "recovered"

# A real top-level session has a UUID id. Subagent and workflow transcripts
# (ids like "agent-acompact-…", project "subagents" or "wf_…") are fragments of
# a parent session, not sessions to summarise on their own; their text stays
# searchable in ChromaDB regardless.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def is_real_session(sid: str, project: str) -> bool:
    if not _UUID_RE.match(sid):
        return False
    if project == "subagents":
        return False
    # The summariser's own claude -p transcripts and the dotfiles-rag dev dir
    # are junk, same as the live sweep excludes.
    if any(suffix in project for suffix in EXCLUDED_PROJECT_SUFFIXES):
        return False
    return True

# High-signal secret shapes. A summary should never contain these; if one slips
# through the model's redaction, the page is quarantined, not written to the wiki.
_SECRET_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"\bsk-[A-Za-z0-9]{20,}",
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bghp_[A-Za-z0-9]{30,}",
        r"\bxox[baprs]-[A-Za-z0-9-]{10,}",
        r"\bAIza[0-9A-Za-z_\-]{30,}",
        r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}",  # JWT
        r"(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]",
    )
]


def scan_secrets(text: str) -> list[str]:
    """Literal-secret shapes found in a rendered page, by pattern label."""
    hits = []
    for rx in _SECRET_RES:
        if rx.search(text):
            hits.append(rx.pattern[:40])
    return hits


def load_dump(path: Path) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Read a turn-per-line dump. Returns (sid -> turns, sid -> project)."""
    sessions: dict[str, list[dict]] = defaultdict(list)
    projects: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            sid = rec["session_id"]
            sessions[sid].append(rec)
            if rec.get("project"):
                projects.setdefault(sid, rec["project"])
    return sessions, projects


def ondisk_sids() -> set[str]:
    """Session ids that still have a real transcript anywhere we can see."""
    ids: set[str] = set()
    for p in CLAUDE_PROJECTS_DIR.glob("*/*.jsonl"):
        ids.add(p.stem)
    hub = Path.home() / "claude-sync"
    if hub.is_dir():
        for p in hub.glob("*/*/*.jsonl"):
            ids.add(p.stem)
    return ids


def load_checkpoint() -> set[str]:
    done: set[str] = set()
    if CHECKPOINT.exists():
        for line in CHECKPOINT.read_text(encoding="utf-8").splitlines():
            sid = line.split("\t", 1)[0].strip()
            if sid:
                done.add(sid)
    return done


def mark_done(sid: str, status: str) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT, "a", encoding="utf-8") as fh:
        fh.write(f"{sid}\t{status}\n")


def turns_to_dicts(turns: list[dict]) -> list[dict[str, Any]]:
    """Sort raw dump turns and shape them for build_text/parse_date_from_turns."""
    ordered = sorted(turns, key=lambda r: r.get("turn", 0))
    return [
        {"text": r.get("text", ""), "metadata": {"timestamp": r.get("timestamp", "")}}
        for r in ordered
    ]


def write_archive(project: str, sid: str, turns: list[dict]) -> Path:
    """Write the best-effort reconstructed transcript, one turn per line."""
    proj = re.sub(r"[^A-Za-z0-9._-]+", "-", project or "unknown-project").strip("-") or "unknown-project"
    out_dir = ARCHIVE_ROOT / proj
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{sid}.jsonl"
    ordered = sorted(turns, key=lambda r: r.get("turn", 0))
    with open(path, "w", encoding="utf-8") as fh:
        for r in ordered:
            fh.write(json.dumps({
                "turn": r.get("turn", 0),
                "timestamp": r.get("timestamp", ""),
                "text": r.get("text", ""),
            }) + "\n")
    return path


def merge_dumps(
    air_dump: Path | None, other_dumps: list[Path]
) -> tuple[dict[str, list[dict]], dict[str, str], set[str]]:
    """Merge dumps. Returns (sid -> best turns, sid -> project, air_sids).

    For a session in several dumps, the copy with more turns wins (most complete).
    """
    best: dict[str, list[dict]] = {}
    projects: dict[str, str] = {}
    air_sids: set[str] = set()

    def absorb(path: Path, is_air: bool) -> None:
        sessions, projs = load_dump(path)
        for sid, turns in sessions.items():
            if is_air:
                air_sids.add(sid)
            if sid not in best or len(turns) > len(best[sid]):
                best[sid] = turns
            projects.setdefault(sid, projs.get(sid, ""))

    if air_dump:
        absorb(air_dump, is_air=True)
    for d in other_dumps:
        absorb(d, is_air=False)
    return best, projects, air_sids


def process(
    sid: str,
    turns: list[dict],
    project: str,
    machine: str,
    model: str,
    wiki_ids: frozenset[str],
    dry_run: bool,
) -> str:
    """Archive one session and, if substantial, summarise it. Returns a status."""
    archive_path = write_archive(project, sid, turns)

    tdicts = turns_to_dicts(turns)
    text, n_turns = build_text(tdicts)

    if not has_content(len(text)):
        return "archived-thin"

    if sid in wiki_ids:
        return "archived-wiki-has-it"

    date = parse_date_from_turns(tdicts) or "1970-01-01"
    domain = detect_domain(project, text[:20_000])

    try:
        envelope = run_claude(text, model=model)
    except RuntimeError as exc:
        return f"error:{str(exc)[:60]}"

    try:
        fields = parse_summary(envelope.get("result", ""))
    except HollowSummary:
        return "archived-hollow"
    except ValueError as exc:
        return f"error:parse:{str(exc)[:50]}"

    # Mark provenance: reconstructed from the index, lossy, origin uncertain.
    fields["tags"] = ["recovered"] + [t for t in fields.get("tags", []) if t != "recovered"]

    page = render_page(
        fields, date=date, domain=domain, project=project,
        session_id=sid, model=model, needs_review=False,
        transcript_path=str(archive_path), machine=machine,
    )
    violations = lint(page)
    if violations:
        page = render_page(
            fields, date=date, domain=domain, project=project,
            session_id=sid, model=model, needs_review=True,
            transcript_path=str(archive_path), machine=machine,
        )

    leaks = scan_secrets(page)
    slug = slugify(fields["title"])
    if leaks:
        QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
        q = QUARANTINE_ROOT / f"{date}-{slug}-{sid[:8]}.md"
        if not dry_run:
            q.write_text(page, encoding="utf-8")
        return f"QUARANTINED:{','.join(leaks)}"

    if dry_run:
        print(f"\n----- DRY-RUN PAGE for {sid[:8]} ({machine_folder(machine)}) -----")
        print(page[:1800])
        return "dry-run"

    target = _write_page(page, machine, date, slug, sid)
    return f"written:{target.name}" if not violations else f"needs-review:{target.name}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--air-dump", type=Path, help="dump whose sessions are the Air's")
    ap.add_argument("--dump", type=Path, action="append", default=[],
                    help="other dump(s) to merge; the more complete copy of a session wins")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="process at most N sessions (0 = all)")
    ap.add_argument("--pilot", default="", help="comma-separated session ids to process only")
    ap.add_argument("--dry-run", action="store_true", help="print pages, do not write to wiki")
    ap.add_argument("--list-candidates", type=int, default=0,
                    help="print N candidate sessions (sid, turns, air/unknown, project) and exit")
    args = ap.parse_args()

    best, projects, air_sids = merge_dumps(args.air_dump, args.dump)
    on_disk = ondisk_sids()
    wiki_ids = wiki_session_ids()
    done = load_checkpoint()

    def machine_for(sid: str) -> str:
        # Origin is not reliably knowable for recovered sessions; one bucket.
        return RECOVERED_MACHINE

    # Candidate sessions: real top-level sessions, indexed, not on disk.
    candidates = [
        sid for sid in best
        if sid not in on_disk and is_real_session(sid, projects.get(sid, ""))
    ]

    if args.list_candidates:
        ranked = sorted(candidates, key=lambda s: len(best[s]), reverse=True)
        for sid in ranked[: args.list_candidates]:
            tag = "air" if sid in air_sids else "unknown"
            print(f"{sid}\tturns={len(best[sid])}\t{tag}\t{projects.get(sid,'')}")
        print(f"\n# {len(candidates)} candidates total "
              f"({sum(1 for s in candidates if s in air_sids)} air, "
              f"{sum(1 for s in candidates if s not in air_sids)} unknown)")
        return

    if args.pilot:
        targets = [s.strip() for s in args.pilot.split(",") if s.strip()]
    else:
        targets = [s for s in candidates if s not in done]
        if args.limit:
            targets = targets[: args.limit]

    counts: dict[str, int] = defaultdict(int)
    for i, sid in enumerate(targets, 1):
        if sid not in best:
            print(f"[{i}/{len(targets)}] {sid[:8]} NOT in dumps", file=sys.stderr)
            continue
        machine = machine_for(sid)
        status = process(
            sid, best[sid], projects.get(sid, ""), machine,
            args.model, wiki_ids, args.dry_run,
        )
        bucket = status.split(":", 1)[0]
        counts[bucket] += 1
        if not args.dry_run and not args.pilot and not status.startswith("error"):
            mark_done(sid, status)
        print(f"[{i}/{len(targets)}] {sid[:8]} {machine_folder(machine)} -> {status}")

    print("\n=== recovery run summary ===")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")


if __name__ == "__main__":
    main()
