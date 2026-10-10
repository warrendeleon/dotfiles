"""Tests for the session sweep: domain routing, gating, and one full write."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from src import summarise_sweep as sweep
from src.queue_db import JobQueue, JobType
from src.summary_ledger import SummaryLedger


def _write_jsonl(path: Path, n_turns: int, text: str = "work on the thing") -> None:
    lines = []
    for _ in range(n_turns):
        lines.append({"type": "user", "message": {"role": "user", "content": text}})
        lines.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": text * 20}]},
        })
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")


# --- detect_domain ----------------------------------------------------------

def test_detect_domain_hl_dir() -> None:
    assert sweep.detect_domain("-Users-w-Developer-HL-pokedex", "anything") == "hl"


def test_detect_domain_hl_text_marker() -> None:
    assert sweep.detect_domain("-Users-w-Developer", "we fixed the hl-mobile build") == "hl"


def test_detect_domain_personal() -> None:
    assert sweep.detect_domain("-Users-w-Developer", "rebuilt the personal blog") == "personal"


# --- is_finished ------------------------------------------------------------

def test_is_finished_idle(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    p.write_text("{}")
    now = time.time()
    os.utime(p, (now - 40 * 60, now - 40 * 60))  # idle 40 min
    assert sweep.is_finished(p, idle_minutes=30, now=now) is True


def test_is_finished_active(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    p.write_text("{}")
    now = time.time()
    os.utime(p, (now - 5 * 60, now - 5 * 60))  # idle 5 min
    assert sweep.is_finished(p, idle_minutes=30, now=now) is False


# --- needs_summary ----------------------------------------------------------

def test_needs_summary_unseen(tmp_path: Path) -> None:
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "sess.jsonl"
    p.write_text("{}")
    assert sweep.needs_summary(p, led, time.time()) is True


def test_needs_summary_unchanged_is_skipped(tmp_path: Path) -> None:
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "sess.jsonl"
    p.write_text("{}")
    led.record("sess", str(p), "h", "/page.md", "written", "haiku")
    # File older than the ledger write: unchanged, skip.
    past = time.time() - 3600
    os.utime(p, (past, past))
    assert sweep.needs_summary(p, led, time.time()) is False


def test_needs_summary_grown_is_resummarised(tmp_path: Path) -> None:
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "sess.jsonl"
    p.write_text("{}")
    led.record("sess", str(p), "h", "/page.md", "written", "haiku")
    # File touched after the ledger write: session grew, re-summarise.
    future = time.time() + 3600
    os.utime(p, (future, future))
    assert sweep.needs_summary(p, led, time.time()) is True


def test_needs_summary_prior_error_retries(tmp_path: Path) -> None:
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "sess.jsonl"
    p.write_text("{}")
    led.record("sess", str(p), "h", None, "error", "haiku")
    past = time.time() - 3600
    os.utime(p, (past, past))
    assert sweep.needs_summary(p, led, time.time()) is True


def test_needs_summary_skips_when_in_shared_wiki(tmp_path: Path) -> None:
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "abc123.jsonl"
    p.write_text("{}")
    # No local ledger record, but the shared wiki already has a page for it:
    # another machine (or a pre-wipe run) covered it. Skip.
    assert sweep.needs_summary(p, led, time.time(), frozenset({"abc123"})) is False


def test_needs_summary_new_when_not_in_wiki(tmp_path: Path) -> None:
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "abc123.jsonl"
    p.write_text("{}")
    assert sweep.needs_summary(p, led, time.time(), frozenset({"other"})) is True


def test_needs_summary_owner_growth_beats_wiki_set(tmp_path: Path) -> None:
    # This machine owns the page (ledger record). A grown transcript must still
    # be re-summarised even though its id is in the wiki set (its own page).
    led = SummaryLedger(db_path=tmp_path / "l.db")
    p = tmp_path / "abc123.jsonl"
    p.write_text("{}")
    led.record("abc123", str(p), "h", "/page.md", "written", "haiku")
    future = time.time() + 3600
    os.utime(p, (future, future))
    assert sweep.needs_summary(p, led, time.time(), frozenset({"abc123"})) is True


def test_wiki_session_ids_reads_frontmatter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path)
    d = tmp_path / "personal" / "sessions"
    d.mkdir(parents=True)
    (d / "a.md").write_text("---\ntype: session\nsession_id: sess-aaa\n---\n# A\n")
    (d / "b.md").write_text("---\ntype: session\nsession_id: sess-bbb\n---\n# B\n")
    (tmp_path / "hl" / "sessions").mkdir(parents=True)
    (tmp_path / "hl" / "sessions" / "c.md").write_text("---\nsession_id: sess-ccc\n---\n# C\n")
    assert sweep.wiki_session_ids() == frozenset({"sess-aaa", "sess-bbb", "sess-ccc"})


def test_sweep_skips_session_already_in_wiki(tmp_path: Path, monkeypatch) -> None:
    # A foreign session already summarised elsewhere (page in the synced wiki)
    # must not be re-summarised here, even with an empty local ledger.
    monkeypatch.setattr(sweep, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(sweep, "hub_session_origins", lambda: {})  # no SSH to the hub in tests
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    calls = {"n": 0}

    def _count(*a, **k):
        calls["n"] += 1
        return _fake_envelope(_good_fields())

    monkeypatch.setattr(sweep, "run_claude", _count)

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    t = proj / "donealr1.jsonl"
    _write_jsonl(t, 6)
    now = time.time()
    os.utime(t, (now - 3600, now - 3600))  # idle, would otherwise be summarised

    # Pre-seed the wiki with a page for this session id.
    wd = tmp_path / "wiki" / "personal" / "sessions"
    wd.mkdir(parents=True)
    (wd / "x.md").write_text("---\ntype: session\nsession_id: donealr1\n---\n# done\n")

    led = SummaryLedger(db_path=tmp_path / "l.db")
    q = JobQueue(db_path=tmp_path / "q.db")
    sweep.sweep(model="sonnet", idle_minutes=30, ledger=led, index_queue=q)

    assert calls["n"] == 0  # never summarised, already in the wiki
    assert led.get("donealr1") is None


# --- iter_transcripts -------------------------------------------------------

def test_iter_transcripts_excludes_workdir_and_rag(tmp_path: Path) -> None:
    (tmp_path / "proj-normal").mkdir()
    (tmp_path / "proj-normal" / "a.jsonl").write_text("{}")
    (tmp_path / "x-summariser-workdir").mkdir()
    (tmp_path / "x-summariser-workdir" / "b.jsonl").write_text("{}")
    (tmp_path / "y-dotfiles-rag").mkdir()
    (tmp_path / "y-dotfiles-rag" / "c.jsonl").write_text("{}")

    found = {p.name for p in sweep.iter_transcripts(tmp_path)}
    assert found == {"a.jsonl"}


# --- summarise_one (model call mocked) --------------------------------------

def _fake_envelope(fields: dict) -> dict:
    return {"type": "result", "subtype": "success", "is_error": False,
            "result": json.dumps(fields), "usage": {}, "total_cost_usd": 0.0}


def _good_fields() -> dict:
    return {
        "title": "Fix the sweep gate",
        "tags": ["rag"],
        "request": "Make the sweep idempotent.",
        "investigated": ["mtime gating"],
        "learned": ["ledger dedups by mtime"],
        "completed": ["added the gate", "wrote tests"],
        "next_steps": ["wire the hooks"],
    }


def test_summarise_one_writes_page_and_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    monkeypatch.setattr(sweep, "run_claude", lambda *a, **k: _fake_envelope(_good_fields()))

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    transcript = proj / "abc12345.jsonl"
    _write_jsonl(transcript, n_turns=6)

    led = SummaryLedger(db_path=tmp_path / "l.db")
    status = sweep.summarise_one(transcript, led, model="sonnet", origins={"abc12345": "mbp16"})

    assert status == "written"
    # Filed under the origin machine's folder, not a domain folder.
    pages = list((tmp_path / "wiki" / "sessions" / "mbp16m1max").glob("*.md"))
    assert len(pages) == 1
    text = pages[0].read_text()
    assert "status: auto" in text
    assert "machine: mbp16" in text
    assert "# Fix the sweep gate" in text
    row = led.get("abc12345")
    assert row["status"] == "written"


def test_summarise_one_skips_near_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    called = {"n": 0}
    monkeypatch.setattr(sweep, "run_claude", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    transcript = proj / "tiny.jsonl"
    # A one-liner well under the content floor: "User: hi\n\nAssistant: ok".
    transcript.write_text(
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n"
        + json.dumps({"type": "assistant",
                      "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}}),
        encoding="utf-8",
    )

    led = SummaryLedger(db_path=tmp_path / "l.db")
    status = sweep.summarise_one(transcript, led, model="haiku")

    assert status == "skipped"
    assert called["n"] == 0  # near-empty: model never called
    assert led.get("tiny")["status"] == "skipped"


def test_summarise_one_hollow_is_skipped_not_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    hollow = _good_fields()
    hollow["completed"] = []
    hollow["next_steps"] = []  # model found nothing substantive
    monkeypatch.setattr(sweep, "run_claude", lambda *a, **k: _fake_envelope(hollow))

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    transcript = proj / "hollow12.jsonl"
    _write_jsonl(transcript, n_turns=6)  # passes the content floor, reaches the model

    led = SummaryLedger(db_path=tmp_path / "l.db")
    status = sweep.summarise_one(transcript, led, model="sonnet")

    # Hollow output is a clean skip, never an error (which would retry-loop).
    assert status == "skipped"
    assert led.get("hollow12")["status"] == "skipped"
    assert not list((tmp_path / "wiki").rglob("*.md"))


def test_summarise_one_flags_needs_review_on_em_dash(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    fields = _good_fields()
    fields["completed"] = ["added the gate — and tests"]  # em-dash
    monkeypatch.setattr(sweep, "run_claude", lambda *a, **k: _fake_envelope(fields))

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    transcript = proj / "dash1234.jsonl"
    _write_jsonl(transcript, n_turns=6)

    led = SummaryLedger(db_path=tmp_path / "l.db")
    status = sweep.summarise_one(transcript, led, model="sonnet", origins={"dash1234": "mbp16"})

    assert status == "needs-review"
    page = list((tmp_path / "wiki" / "sessions" / "mbp16m1max").glob("*.md"))[0].read_text()
    assert "status: needs-review" in page


def test_sweep_skips_active_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(sweep, "hub_session_origins", lambda: {})  # no SSH to the hub in tests
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    monkeypatch.setattr(sweep, "run_claude", lambda *a, **k: _fake_envelope(_good_fields()))

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    old = proj / "old12345.jsonl"
    new = proj / "new12345.jsonl"
    _write_jsonl(old, 6)
    _write_jsonl(new, 6)
    now = time.time()
    os.utime(old, (now - 3600, now - 3600))  # idle 1h
    os.utime(new, (now - 60, now - 60))       # active 1 min ago

    led = SummaryLedger(db_path=tmp_path / "l.db")
    q = JobQueue(db_path=tmp_path / "q.db")
    sweep.sweep(model="sonnet", idle_minutes=30, ledger=led, index_queue=q)

    assert led.get("old12345")["status"] == "written"
    assert led.get("new12345") is None  # active session never touched


def test_sweep_session_arg_bypasses_idle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(sweep, "hub_session_origins", lambda: {})  # no SSH to the hub in tests
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    monkeypatch.setattr(sweep, "run_claude", lambda *a, **k: _fake_envelope(_good_fields()))

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    active = proj / "fresh123.jsonl"
    _write_jsonl(active, 6)
    now = time.time()
    os.utime(active, (now - 30, now - 30))  # active, would fail the idle gate

    led = SummaryLedger(db_path=tmp_path / "l.db")
    q = JobQueue(db_path=tmp_path / "q.db")
    sweep.sweep(model="haiku", idle_minutes=30, only_session="fresh123", ledger=led, index_queue=q)

    # SessionEnd path: an explicit session is summarised even though it is fresh.
    assert led.get("fresh123")["status"] == "written"
    # The new page (named by date+slug, not session id) was enqueued as a WIKI job.
    pending = q.dequeue(batch_size=5)
    assert any(j.job_type == JobType.WIKI.value and j.file_path.endswith(".md") for j in pending)


def test_resume_resummary_removes_orphan_page(tmp_path: Path, monkeypatch) -> None:
    # Resuming a session grows the same transcript; re-summarising with a changed
    # title lands at a new filename. The previous page must be removed, not left.
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    titles = iter(["First title before resume", "Second title after resume"])

    def _mock(*a, **k):
        f = _good_fields()
        f["title"] = next(titles)
        return _fake_envelope(f)

    monkeypatch.setattr(sweep, "run_claude", _mock)

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    t = proj / "resume12.jsonl"
    _write_jsonl(t, 6)
    led = SummaryLedger(db_path=tmp_path / "l.db")

    origins = {"resume12": "mbp16"}
    sweep.summarise_one(t, led, model="sonnet", origins=origins)
    sessions_dir = tmp_path / "wiki" / "sessions" / "mbp16m1max"
    assert len(list(sessions_dir.glob("*.md"))) == 1

    # Resume: re-summarise. Title changed -> new filename, old must be gone.
    sweep.summarise_one(t, led, model="sonnet", origins=origins)
    pages = list(sessions_dir.glob("*.md"))
    assert len(pages) == 1
    assert "second-title-after-resume" in pages[0].name
    assert led.get("resume12")["page_path"] == str(pages[0])


def test_acquire_lock_is_mutually_exclusive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "LOCK_PATH", tmp_path / "summariser.lock")
    first = sweep.acquire_lock()
    assert first is not None
    # A second acquire while the first is held must fail.
    assert sweep.acquire_lock() is None
    first.close()
    # Once released, it can be taken again.
    third = sweep.acquire_lock()
    assert third is not None
    third.close()


def test_summarise_one_records_error_on_model_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")

    def _boom(*a, **k):
        raise RuntimeError("claude exploded")

    monkeypatch.setattr(sweep, "run_claude", _boom)

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    transcript = proj / "err12345.jsonl"
    _write_jsonl(transcript, n_turns=6)

    led = SummaryLedger(db_path=tmp_path / "l.db")
    status = sweep.summarise_one(transcript, led, model="sonnet")

    assert status == "error"
    assert led.get("err12345")["status"] == "error"


# --- alert_if_failing -------------------------------------------------------

def _alert(counts, tmp_path: Path, now: float, sent: list, interval: int = 3600) -> bool:
    return sweep.alert_if_failing(
        counts, marker=tmp_path / "alerted", interval_s=interval,
        notify=lambda title, msg: sent.append((title, msg)), now=now,
    )


def test_alert_fires_on_error_only_sweep(tmp_path: Path) -> None:
    sent: list = []
    assert _alert({"error": 5}, tmp_path, 1000.0, sent) is True
    assert len(sent) == 1
    assert "5 session summaries failed" in sent[0][1]
    assert (tmp_path / "alerted").exists()


def test_alert_silent_when_anything_was_handled(tmp_path: Path) -> None:
    sent: list = []
    assert _alert({"error": 2, "written": 1}, tmp_path, 1000.0, sent) is False
    assert _alert({"written": 3}, tmp_path, 1000.0, sent) is False
    assert _alert({}, tmp_path, 1000.0, sent) is False
    assert sent == []
    assert not (tmp_path / "alerted").exists()


def test_alert_rate_limited_by_marker(tmp_path: Path) -> None:
    sent: list = []
    assert _alert({"error": 1}, tmp_path, 1000.0, sent) is True
    assert _alert({"error": 1}, tmp_path, 1000.0 + 1800, sent) is False  # inside interval
    assert _alert({"error": 1}, tmp_path, 1000.0 + 3601, sent) is True   # interval elapsed
    assert len(sent) == 2


# --- workers ----------------------------------------------------------------

def test_sweep_workers_run_concurrently_and_count_all(tmp_path: Path, monkeypatch) -> None:
    import threading

    monkeypatch.setattr(sweep, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(sweep, "hub_session_origins", lambda: {})
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")

    n = 6
    # Every call blocks until all n are in flight: proves the pool is real,
    # and would deadlock (and time out) if the sweep ran them one by one.
    barrier = threading.Barrier(n, timeout=10)

    def _model(*a, **k):
        barrier.wait()
        return _fake_envelope(_good_fields())

    monkeypatch.setattr(sweep, "run_claude", _model)

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    now = time.time()
    for i in range(n):
        t = proj / f"sess{i:04d}.jsonl"
        _write_jsonl(t, 6, text=f"work item {i} on the thing")
        os.utime(t, (now - 3600, now - 3600))

    led = SummaryLedger(db_path=tmp_path / "l.db")
    q = JobQueue(db_path=tmp_path / "q.db")
    counts = sweep.sweep(model="haiku", idle_minutes=30, ledger=led, index_queue=q, workers=n)

    assert sum(counts.values()) == n
    assert counts.get("error", 0) == 0
    assert led.stats().get("written", 0) + led.stats().get("needs-review", 0) == n


def test_sweep_limit_applies_before_the_pool(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(sweep, "hub_session_origins", lambda: {})
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    calls = {"n": 0}

    def _count(*a, **k):
        calls["n"] += 1
        return _fake_envelope(_good_fields())

    monkeypatch.setattr(sweep, "run_claude", _count)

    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    now = time.time()
    for i in range(5):
        t = proj / f"lim{i:05d}.jsonl"
        _write_jsonl(t, 6)
        os.utime(t, (now - 3600, now - 3600))

    led = SummaryLedger(db_path=tmp_path / "l.db")
    q = JobQueue(db_path=tmp_path / "q.db")
    counts = sweep.sweep(model="haiku", idle_minutes=30, ledger=led, index_queue=q,
                         workers=4, limit=2)
    assert sum(counts.values()) == 2
    assert calls["n"] == 2


# --- routines ---------------------------------------------------------------

def _write_routine_jsonl(path: Path, style: str = "new") -> None:
    if style == "new":
        first = {"type": "user", "turnOrigin": "scheduled",
                 "origin": {"kind": "task-notification", "subkind": "scheduled-trigger"},
                 "message": {"role": "user", "content": "<scheduled-task name=\"x\">rebase</scheduled-task>"}}
    else:  # the July format: only the prompt tag marks it
        first = {"type": "user", "promptSource": "sdk",
                 "message": {"role": "user", "content": [{"type": "text", "text": "<scheduled-task name=\"seat\">watch</scheduled-task>"}]}}
    lines = [
        {"type": "queue-operation", "operation": "enqueue"},
        {"type": "attachment", "attachment": {}},
        first,
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "done " * 50}]}},
    ]
    path.write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")


def test_is_routine_transcript_new_and_old_formats(tmp_path: Path) -> None:
    new = tmp_path / "new.jsonl"; _write_routine_jsonl(new, "new")
    old = tmp_path / "old.jsonl"; _write_routine_jsonl(old, "old")
    human = tmp_path / "human.jsonl"; _write_jsonl(human, 3)
    assert sweep.is_routine_transcript(new) is True
    assert sweep.is_routine_transcript(old) is True
    assert sweep.is_routine_transcript(human) is False
    assert sweep.is_routine_transcript(tmp_path / "missing.jsonl") is False


def test_summarise_one_skips_routine_without_calling_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise AssertionError("model must not be called for a routine")

    monkeypatch.setattr(sweep, "run_claude", _boom)
    t = tmp_path / "proj" / "routine1.jsonl"
    t.parent.mkdir()
    _write_routine_jsonl(t)
    led = SummaryLedger(db_path=tmp_path / "l.db")
    status = sweep.summarise_one(t, led, "haiku", index_queue=JobQueue(db_path=tmp_path / "q.db"))
    assert status == "skipped"
    assert calls["n"] == 0
    assert led.get("routine1")["status"] == "skipped"
    assert not list((tmp_path / "wiki").rglob("*.md"))


class _FakeStore:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def delete_page(self, collection: str, file_path: str) -> None:
        self.deleted.append((collection, file_path))


def test_purge_routines_removes_pages_deindexes_and_marks_skipped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(sweep, "WIKI_SESSIONS_ROOT", tmp_path / "wiki")
    proj = tmp_path / "projects" / "-Users-w-Developer"
    proj.mkdir(parents=True)
    routine = proj / "rout0001.jsonl"; _write_routine_jsonl(routine)
    human = proj / "huma0001.jsonl"; _write_jsonl(human, 3)
    gone = proj / "gone0001.jsonl"  # transcript deleted: page must survive

    pages = tmp_path / "wiki" / "sessions" / "mac"
    pages.mkdir(parents=True)

    def _page(sid: str, src: Path) -> Path:
        p = pages / f"{sid}.md"
        p.write_text(f"---\ntype: session\nsession_id: {sid}\n---\n# t\n\n## Source\n\n- Transcript: `{src}`\n")
        return p

    rp = _page("rout0001", routine)
    hp = _page("huma0001", human)
    gp = _page("gone0001", gone)

    led = SummaryLedger(db_path=tmp_path / "l.db")
    led.record("rout0001", str(routine), "h", str(rp), "written", "haiku")
    # huma0001 and gone0001 have no ledger row: path comes from the page's source line.
    store = _FakeStore()

    assert sweep.purge_routines(led, store=store, dry_run=True) == 1
    assert rp.exists()  # dry run touches nothing

    assert sweep.purge_routines(led, store=store) == 1
    assert not rp.exists()
    assert hp.exists() and gp.exists()
    assert store.deleted == [("wiki", str(rp))]
    assert led.get("rout0001")["status"] == "skipped"
    assert led.get("rout0001")["page_path"] is None
    # Idempotent: the page is gone, nothing left to purge.
    assert sweep.purge_routines(led, store=store) == 0
