"""Unit tests for the session summariser (no model calls except a mocked one)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import summariser


def _write_jsonl(path: Path, turns: list[tuple[str, str]]) -> None:
    """Write a minimal Claude Code transcript: list of (role, text)."""
    lines = []
    for role, text in turns:
        if role == "user":
            lines.append({"type": "user", "message": {"role": "user", "content": text}})
        else:
            lines.append({
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
            })
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")


# --- build_input ------------------------------------------------------------

def test_build_input_missing_file_returns_empty(tmp_path: Path) -> None:
    text, n = summariser.build_input(tmp_path / "nope.jsonl")
    assert text == ""
    assert n == 0


def test_build_input_joins_turns(tmp_path: Path) -> None:
    p = tmp_path / "s.jsonl"
    _write_jsonl(p, [("user", "fix the bug"), ("assistant", "fixed it")])
    text, n = summariser.build_input(p)
    assert n == 1  # one user+assistant turn
    assert "fix the bug" in text
    assert "fixed it" in text


def test_build_input_truncates_long_sessions(tmp_path: Path) -> None:
    p = tmp_path / "big.jsonl"
    big = "x" * 200_000
    _write_jsonl(p, [("user", big), ("assistant", "y" * 200_000)])
    text, _ = summariser.build_input(p)
    assert len(text) <= summariser.MAX_INPUT_CHARS + len(summariser.TRUNCATION_MARKER)
    assert summariser.TRUNCATION_MARKER in text


# --- has_content ------------------------------------------------------------

def test_has_content() -> None:
    assert summariser.has_content(50_000) is True
    assert summariser.has_content(500) is True     # single-turn but real content
    assert summariser.has_content(100) is False    # near-empty, skipped


# --- strip_fences -----------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ('```json\n{"a": 1}\n```', '{"a": 1}'),
    ('```\n{"a": 1}\n```', '{"a": 1}'),
    ('{"a": 1}', '{"a": 1}'),
    ('   {"a": 1}   ', '{"a": 1}'),
])
def test_strip_fences(raw: str, expected: str) -> None:
    assert summariser.strip_fences(raw) == expected


# --- parse_summary ----------------------------------------------------------

def _valid_payload() -> dict:
    return {
        "title": "Fix the indexer leak",
        "tags": ["rag", "memory"],
        "request": "Stop the embedder leaking memory.",
        "investigated": ["traced MPS allocator"],
        "learned": ["call empty_cache per batch"],
        "completed": ["added empty_cache", "verified RSS flat"],
        "next_steps": ["watch for regressions"],
    }


def test_parse_summary_valid() -> None:
    fields = summariser.parse_summary(json.dumps(_valid_payload()))
    assert fields["title"] == "Fix the indexer leak"
    assert fields["completed"] == ["added empty_cache", "verified RSS flat"]
    assert fields["tags"] == ["rag", "memory"]


def test_parse_summary_strips_fences() -> None:
    fields = summariser.parse_summary("```json\n" + json.dumps(_valid_payload()) + "\n```")
    assert fields["request"].startswith("Stop the embedder")


def test_parse_summary_coerces_string_to_list() -> None:
    payload = _valid_payload()
    payload["completed"] = "did one thing"
    fields = summariser.parse_summary(json.dumps(payload))
    assert fields["completed"] == ["did one thing"]


def test_parse_summary_missing_field_raises() -> None:
    payload = _valid_payload()
    del payload["title"]
    with pytest.raises(ValueError, match="missing required field"):
        summariser.parse_summary(json.dumps(payload))


def test_parse_summary_hollow_raises() -> None:
    payload = _valid_payload()
    payload["completed"] = []
    payload["next_steps"] = []
    # HollowSummary (a ValueError subclass) marks a clean skip, not an error.
    with pytest.raises(summariser.HollowSummary):
        summariser.parse_summary(json.dumps(payload))


def test_parse_summary_prose_refusal_is_hollow() -> None:
    # The model replying in prose ("this is a blog post, not a session") is a
    # decline, treated as a clean skip rather than a retryable error.
    with pytest.raises(summariser.HollowSummary):
        summariser.parse_summary("I can't summarise this; it's a blog post, not a session.")


def test_parse_summary_malformed_json_raises() -> None:
    # Starts like JSON but is broken: a genuine malformed output, not a decline.
    with pytest.raises(ValueError) as exc:
        summariser.parse_summary('{"title": "x", "request":')
    assert not isinstance(exc.value, summariser.HollowSummary)


def test_parse_summary_not_object_raises() -> None:
    with pytest.raises(ValueError, match="not an object"):
        summariser.parse_summary("[1, 2, 3]")


# --- lint -------------------------------------------------------------------

def test_lint_clean_text() -> None:
    assert summariser.lint("Fixed the bug. Added a test. Verified it passes.") == []


def test_lint_catches_em_dash() -> None:
    assert any("em-dash" in v for v in summariser.lint("This works — mostly."))


def test_lint_catches_spaced_en_dash() -> None:
    assert any("en-dash" in v for v in summariser.lint("This works – mostly."))


def test_lint_catches_banned_words() -> None:
    v = summariser.lint("However, we leverage a robust approach.")
    assert any("however" in x for x in v)
    assert any("leverage" in x for x in v)
    assert any("robust" in x for x in v)


def test_lint_catches_banned_phrase() -> None:
    assert any("it's important to note" in v for v in summariser.lint("It's important to note this."))


def test_lint_catches_attribution() -> None:
    assert any("attribution" in v for v in summariser.lint("This was AI-generated."))


def test_lint_word_boundary_no_false_positive() -> None:
    # "ensured" should not match the whole-word "ensure"; "thus" must be whole-word.
    assert summariser.lint("The harness embeds thusly named files.") == []


# --- slugify ----------------------------------------------------------------

def test_slugify_basic() -> None:
    assert summariser.slugify("Fix the Indexer Leak!") == "fix-the-indexer-leak"


def test_slugify_truncates_on_word_boundary() -> None:
    slug = summariser.slugify("a " * 80, max_len=20)
    assert len(slug) <= 20
    assert not slug.endswith("-")


def test_slugify_fallback() -> None:
    assert summariser.slugify("!!!") == "session"


# --- machine_folder ---------------------------------------------------------

def test_machine_folder_known_aliases() -> None:
    assert summariser.machine_folder("mbp16") == "mbp16m1max"
    assert summariser.machine_folder("mbp14M5Max") == "mbp14m5max"
    assert summariser.machine_folder("Warrens-MacBook-Air-M1") == "mbairm1"


def test_machine_folder_unknown_slugifies() -> None:
    assert summariser.machine_folder("Some New Mac") == "some-new-mac"


# --- parse_date_from_turns --------------------------------------------------

def test_parse_date_from_turns_uses_last() -> None:
    # 12:00Z stays the same calendar day in essentially every timezone.
    turns = [
        {"text": "a", "metadata": {"timestamp": "2026-04-15T12:00:00Z"}},
        {"text": "b", "metadata": {"timestamp": "2026-05-25T12:00:00Z"}},
    ]
    assert summariser.parse_date_from_turns(turns) == "2026-05-25"


def test_parse_date_from_turns_none_when_absent() -> None:
    assert summariser.parse_date_from_turns([{"text": "a", "metadata": {}}]) is None


def test_parse_date_from_turns_skips_unparseable() -> None:
    turns = [
        {"text": "a", "metadata": {"timestamp": "2026-05-25T12:00:00Z"}},
        {"text": "b", "metadata": {"timestamp": "not-a-date"}},
    ]
    # Reversed scan meets the bad value first, skips it, uses the valid one.
    assert summariser.parse_date_from_turns(turns) == "2026-05-25"


# --- summarise_request ------------------------------------------------------

def test_summarise_request_first_sentence() -> None:
    out = summariser.summarise_request("Do the thing. Then more detail follows here.")
    assert out == "Do the thing."


def test_summarise_request_no_midword_cut() -> None:
    text = "Verify dotfiles match the laptop and prepare the repo for sharing by fixing drift " * 3
    out = summariser.summarise_request(text, cap=40)
    assert len(out) <= 43  # cap + ellipsis
    assert not out[:-3].endswith(" ")
    assert out.endswith("...")


def test_summarise_request_short_passes() -> None:
    assert summariser.summarise_request("Short request") == "Short request"


# --- render_page ------------------------------------------------------------

def test_render_page_structure() -> None:
    page = summariser.render_page(
        summariser.parse_summary(json.dumps(_valid_payload())),
        date="2026-06-07",
        domain="personal",
        project="-Users-w-Developer-dotfiles",
        session_id="abc123",
        model="sonnet",
        needs_review=False,
        transcript_path="/x/abc123.jsonl",
    )
    assert "status: auto" in page
    assert "type: session" in page
    assert "session_id: abc123" in page
    assert "project: -Users-w-Developer-dotfiles" in page
    assert "source_model: sonnet" in page
    assert "## Request" in page
    assert "## Next steps" in page
    assert "# Fix the indexer leak" in page


def test_render_page_needs_review_status() -> None:
    page = summariser.render_page(
        summariser.parse_summary(json.dumps(_valid_payload())),
        date="2026-06-07", domain="hl", project="p", session_id="s",
        model="haiku", needs_review=True, transcript_path="/x/s.jsonl",
    )
    assert "status: needs-review" in page


def test_render_page_escapes_quotes_in_title() -> None:
    payload = _valid_payload()
    payload["title"] = 'The "quoted" title'
    page = summariser.render_page(
        summariser.parse_summary(json.dumps(payload)),
        date="2026-06-07", domain="personal", project="p", session_id="s",
        model="haiku", needs_review=False, transcript_path="/x/s.jsonl",
    )
    # Frontmatter title must not contain a raw double quote that breaks YAML.
    title_line = [l for l in page.splitlines() if l.startswith("title:")][0]
    assert title_line == "title: \"The 'quoted' title\""


# --- run_claude (mocked subprocess) ----------------------------------------

def test_run_claude_parses_envelope(monkeypatch, tmp_path: Path) -> None:
    envelope = {
        "type": "result", "subtype": "success", "is_error": False,
        "result": '{"ok": true}', "usage": {"output_tokens": 5},
        "total_cost_usd": 0.001,
    }

    class _Proc:
        returncode = 0
        stdout = json.dumps(envelope)
        stderr = ""

    def _fake_run(*args, **kwargs):
        return _Proc()

    monkeypatch.setattr(summariser.subprocess, "run", _fake_run)
    out = summariser.run_claude("hello", workdir=tmp_path)
    assert out["result"] == '{"ok": true}'


def test_run_claude_raises_on_error_envelope(monkeypatch, tmp_path: Path) -> None:
    class _Proc:
        returncode = 0
        stdout = json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True})
        stderr = ""

    monkeypatch.setattr(summariser.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(RuntimeError, match="error envelope"):
        summariser.run_claude("hello", workdir=tmp_path)


def test_run_claude_raises_on_nonzero_exit(monkeypatch, tmp_path: Path) -> None:
    class _Proc:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(summariser.subprocess, "run", lambda *a, **k: _Proc())
    with pytest.raises(RuntimeError, match="exited 1"):
        summariser.run_claude("hello", workdir=tmp_path)


def test_lint_allows_term_definition_list_items() -> None:
    """`- term — definition` is house convention (Related and Sources lists)."""
    text = (
        "## Related\n\n"
        "- [[skim-layer]] — the page-level guide\n"
        "- [[revision-passes]] — guide 6, the revision altitude\n"
        "- `~/path/to/file.md` (machine: mbp14M5Max)\n"
    )
    assert not any("em-dash" in v for v in summariser.lint(text))


def test_lint_still_catches_em_dash_inside_a_list_item() -> None:
    """A bullet that stitches two clauses is not a gloss and stays a violation."""
    text = "- The build passed on the first run — nobody expected that to happen.\n"
    assert any("em-dash" in v for v in summariser.lint(text))


def test_lint_catches_em_dash_in_prose_after_a_list() -> None:
    text = "- [[a]] — one\n\nThis sentence works — mostly.\n"
    assert any("em-dash" in v for v in summariser.lint(text))


def test_lint_catches_second_em_dash_in_a_list_item() -> None:
    text = "- [[a]] — one — and another clause hung off the end\n"
    assert any("em-dash" in v for v in summariser.lint(text))


def test_lint_requires_markup_on_a_gloss_term() -> None:
    """A short verb phrase is not a label, even though it is short."""
    assert any("em-dash" in v for v in summariser.lint("- added the gate — and tests\n"))


def test_lint_allows_a_qualified_code_term() -> None:
    text = "- Middleware `cloudflare-or-lan` — routes by source address\n"
    assert not any("em-dash" in v for v in summariser.lint(text))
