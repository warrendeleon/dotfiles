#!/bin/bash
# PreToolUse gate: an agent is launched with a model and an effort chosen for its
# task, and a long command never blocks the conversation.
#
# Warren has had to say "use agents with the right model and effort" and "use an
# agent, I don't want the conversation blocked" in dozens of sessions (June to
# November 2026). An agent launched with neither field inherits the parent's model
# at full effort, so a page fetch or a file search runs on the most expensive
# setting. A foreground command with a long timeout holds the turn, and he cannot
# ask anything until it ends.
#
# What it refuses (exit 2, reason on stderr):
#   Agent, Task   a launch with no `model` or no `effort`;
#                 a second launch on Fable, or at an effort above high, in one
#                 session. The first is mine to spend on the rare task Opus at high
#                 effort cannot do; after that Warren's latest message has to ask for
#                 it by name (14 Nov 2026: "Fable should be always extremely limited
#                 as it consumes lots of tokens", then "rare case, yes");
#                 a fork while the session itself runs on Fable, because a fork
#                 inherits the parent's model. Any other fork is exempt.
#   Workflow      a run whose args or inline script put an agent on Fable or at an
#                 effort above high, when Warren's latest message does not ask for it by
#                 name. A workflow fans out, so it gets no free launch.
#   Bash          a foreground command whose timeout is over three minutes. It goes
#                 to the background (run_in_background) or to a background agent.
#
# It cannot judge whether the choice is right. It makes the choice explicit and puts
# the table in front of the call, which is the step that was being skipped.
set -uo pipefail
input=$(cat)
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT="$input" HOOKS_DIR="$HOOKS_DIR" python3 - <<'PY'
import json, os, re, sys

sys.path.insert(0, os.environ["HOOKS_DIR"])
from lib_transcript import _records, human_turns

try:
    call = json.loads(os.environ["INPUT"])
except Exception:
    sys.exit(0)
tool = call.get("tool_name", "")
inp = call.get("tool_input", {}) or {}

TABLE = """  Haiku or Sonnet, low      mechanical work: fetching a page, searching files, renaming,
                            reformatting, running a command and reporting its output
  Sonnet, medium            drafting from checked facts, summarising, research across sources,
                            routine code changes with a clear spec, most skill runs
  Opus, high                bug hunting, security review, design review, architecture: only
                            where a wrong answer costs more than the tokens
  Fable, or effort above    the rare task Opus at high effort cannot do: one launch a session,
  high                      more only when Warren asks for it by name"""
RULE = (
    "Pick the cheapest row that can do the task. An agent that will run a skill is chosen for the work\n"
    "that skill does, and its brief names the skill and only the reference files the task needs.\n"
)
transcript = call.get("transcript_path") or ""


def warren_named(pattern):
    turns = human_turns(transcript) if transcript else []
    return bool(turns) and bool(re.search(pattern, turns[-1], re.I))


def session_model():
    model = ""
    for rec in _records(transcript) or []:
        if rec.get("type") == "assistant" and not rec.get("isSidechain"):
            model = (rec.get("message") or {}).get("model") or model
    return model.lower()


def top_tier(args):
    return "fable" in str(args.get("model")).lower() or str(args.get("effort")).lower() in ("xhigh", "max")


def earlier_top_tier():
    """Top-tier agent launches already made in this session, the current call left out."""
    current = call.get("tool_use_id")
    seen = 0
    for rec in _records(transcript) or []:
        if rec.get("type") != "assistant" or rec.get("isSidechain"):
            continue
        for block in (rec.get("message") or {}).get("content") or []:
            if not (isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in ("Agent", "Task")):
                continue
            if block.get("id") and block.get("id") == current:
                continue
            if top_tier(block.get("input") or {}):
                seen += 1
    return seen


def refuse(reason):
    sys.stderr.write(
        f"agent gate: {reason}\n{RULE}{TABLE}\n"
        "Do not ask Warren which to use and do not tell him the gate fired: choose and carry on.\n"
    )
    sys.exit(2)


if tool in ("Agent", "Task"):
    if (inp.get("subagent_type") or "") == "fork":
        if "fable" in session_model() and not warren_named(r"\bfable\b|\bfork\b"):
            refuse("a fork inherits this session's model, which is Fable. Launch a fresh agent with a brief instead.")
        sys.exit(0)
    missing = [f for f in ("model", "effort") if not inp.get(f)]
    if missing:
        refuse(f"this agent has no {' and no '.join(missing)}, so it would inherit the parent's at full cost.")
    if top_tier(inp) and not warren_named(r"\b(fable|xhigh|max(imum)? effort|ultrathink)\b") and earlier_top_tier() >= 1:
        refuse("this session has already spent its one launch on Fable or above high effort. Use Opus at high effort.")
    sys.exit(0)

if tool == "Workflow":
    # A workflow fans out, so one override puts many agents on the top tier: no free launch here.
    def values(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from values(v)
        elif isinstance(x, list):
            for v in x:
                yield from values(v)
        elif isinstance(x, str):
            yield x.strip().lower()

    in_args = any("fable" in v or v in ("xhigh", "max") for v in values(inp.get("args")) if len(v) < 40)
    in_script = re.search(r"""model:\s*['"][^'"]*fable|effort:\s*['"](xhigh|max)['"]""", str(inp.get("script") or ""), re.I)
    if (in_args or in_script) and not warren_named(r"\b(fable|xhigh|max(imum)? effort|ultrathink)\b"):
        refuse("this workflow would run its agents on Fable or above high effort. Leave the workflow's own models in place.")
    sys.exit(0)

if tool == "Bash":
    if inp.get("run_in_background"):
        sys.exit(0)
    try:
        timeout = float(inp.get("timeout") or 0)
    except (TypeError, ValueError):
        timeout = 0
    if timeout <= 180000:
        sys.exit(0)
    sys.stderr.write(
        f"agent gate: a foreground command with a {int(timeout / 60000)}-minute timeout holds the conversation.\n"
        "Run it with run_in_background: true, or hand the job to a background agent, and keep answering Warren\n"
        "meanwhile. Shorten the timeout only if the command really finishes within three minutes.\n"
    )
    sys.exit(2)

sys.exit(0)
PY
