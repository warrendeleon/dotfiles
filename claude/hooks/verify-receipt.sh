#!/bin/bash
# PreToolUse gate: a deliverable does not go out without a verification receipt.
#
# Blocks (exit 2, reason on stderr) when the tool call would send, post, publish
# or copy a deliverable that has no clean receipt in ~/.claude/receipts/ whose
# sha256 still matches the file. Receipts are written by write-receipt.sh, the
# last stage of the review-loop workflow.
#
# Covered:
#   Bash        gh pr review / gh pr comment / gh api ...reviews|comments
#               cp, mv, rsync into a Google Drive folder
#   SendUserFile files[]
#   Artifact     publish (action absent or "publish") with file_path
#
# Only deliverable file types are gated: .md .html .pdf .txt .docx .rtf.
# Images, code, data and everything else pass through. An inline review body
# (-b / --body / -f body=) is refused outright: the body must come from a
# receipted file.
#
# The point of a receipt is that a document asserting facts has had those facts
# checked. An .html file that is an application - a design canvas, a mockup, a
# dashboard - asserts nothing to check, and holding it back helps no one. So an
# .html file is gated only when it reads as a document: prose with no script.
# Everything else in the list is gated on sight.
set -uo pipefail
input=$(cat)
RECEIPTS="$HOME/.claude/receipts" INPUT="$input" python3 - <<'PY'
import glob, hashlib, json, os, re, shlex, sys

try:
    call = json.loads(os.environ["INPUT"])
except Exception:
    sys.exit(0)
tool = call.get("tool_name", "")
inp = call.get("tool_input", {}) or {}
GATED = (".md", ".html", ".pdf", ".txt", ".docx", ".rtf")

TAGS = re.compile(r"(?is)<(script|style)\b.*?</\1\s*>|<[^>]+>")


def is_document(path):
    """True when an .html file is prose to be checked rather than a page to be run."""
    if not path.lower().endswith(".html"):
        return True
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return True
    prose = re.sub(r"\s+", " ", TAGS.sub(" ", text)).strip()
    runs = re.search(r"(?i)<script\b", text) is not None
    # A report is mostly words; an application is mostly code. Either signal alone is
    # weak, so a file only escapes the gate when it both runs and reads as code.
    return not (runs and len(prose) < 4000)


def receipt_for(path):
    p = os.path.realpath(os.path.expanduser(path))
    if not os.path.isfile(p):
        return None, "missing"
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    best = None
    for f in sorted(glob.glob(os.path.join(os.environ["RECEIPTS"], "*.json")), reverse=True):
        try:
            r = json.load(open(f))
        except Exception:
            continue
        for t in r.get("targets", []):
            if t.get("path") == p:
                if t.get("sha256") == h and r.get("clean"):
                    return f, "ok"
                best = best or ("stale" if t.get("sha256") != h else "not clean")
    return None, best or "none"

def deny(paths, why):
    lines = ["verify-receipt: blocked. " + why]
    for p, st in paths:
        lines.append(f"  - {p}: {st}")
    lines.append("Run the review-loop workflow on the deliverable (profile delivery, pr-review or blog); its last stage writes the receipt. A receipt goes stale when the file changes.")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)

paths = []
# Relative paths are the tool's, not this hook's: resolve them from the session's folder.
base = call.get("cwd") or os.getcwd()
if tool == "Bash":
    cmd = inp.get("command", "") or ""
    try:
        toks = shlex.split(cmd)
    except Exception:
        toks = cmd.split()
    # A command that starts by changing folder names its files from there. On 7 Oct 2026
    # a review payload passed by a relative path after `cd <scratchpad> &&` was refused as
    # missing, although a clean receipt existed, because it was resolved from the session's folder.
    if len(toks) > 2 and toks[0] == "cd" and toks[2] == "&&":
        base = os.path.join(base, os.path.expanduser(toks[1]))
    joined = " ".join(toks)
    # A pull request review is read from the diff. Checking the branch out into a shared
    # working tree collides with every other session using that checkout (two sessions did
    # exactly that on 10 September 2026). If files are really needed, use a worktree.
    if re.search(r"\bgh\s+pr\s+checkout\b", joined):
        print("verify-receipt: blocked. Do not `gh pr checkout` into a shared checkout. Review from `gh pr diff <n> --repo <owner/name>` and `gh api repos/<owner/name>/contents/<path>?ref=<sha>`. If you need the files on disk, create a worktree first: `git worktree add ../<repo>-pr-<n> && cd there && gh pr checkout <n>`.", file=sys.stderr)
        sys.exit(2)
    is_review = re.search(r"\bgh\s+pr\s+(review|comment)\b", joined) or re.search(r"\bgh\s+api\b.*\b(reviews|comments)\b", joined)
    if is_review:
        if re.search(r"(^|\s)(-b|--body)(\s|=)", joined) or re.search(r"\s-[fF]\s+body=", joined) or re.search(r"\s--raw-field\s+body=", joined):
            deny([], "an inline review or comment body cannot be receipted; write it to a file, run the review loop, then use --body-file / --input.")
        for i, t in enumerate(toks):
            if t in ("--body-file", "-F", "--input") and i + 1 < len(toks):
                v = toks[i + 1]
                v = v.split("=@", 1)[1] if "=@" in v else v
                paths.append(v)
            elif t.startswith("--body-file=") or t.startswith("--input="):
                paths.append(t.split("=", 1)[1])
    elif re.match(r"^\s*(cp|mv|rsync)\b", cmd) and "My Drive" in cmd:
        srcs = [t for t in toks[1:] if not t.startswith("-") and "My Drive" not in t]
        paths.extend(s for s in srcs if s.lower().endswith(GATED))
elif tool == "SendUserFile":
    paths.extend(f for f in (inp.get("files") or []) if str(f).lower().endswith(GATED))
elif tool == "Artifact":
    if inp.get("action") in (None, "", "publish") and inp.get("file_path"):
        paths.append(inp["file_path"])

if not paths:
    sys.exit(0)
paths = [os.path.join(base, os.path.expanduser(str(p))) for p in paths]
paths = [p for p in paths if is_document(os.path.realpath(os.path.expanduser(p)))]
if not paths:
    sys.exit(0)
results = [(p, receipt_for(p)[1]) for p in paths]
bad = [(p, st) for p, st in results if st != "ok"]
if bad:
    deny(bad, "no clean verification receipt for the file(s) below.")
sys.exit(0)
PY
