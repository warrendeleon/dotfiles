#!/usr/bin/env python3
"""Find text that other files quote from a document, and report any an edit removed.

    inbound-quotes.py find ORIGINAL --in PATH [--in PATH ...] [--self FILE] [--min-words N] [--json]
    inbound-quotes.py check ORIGINAL EDITED --in PATH [--in PATH ...] [--min-words N] [--json]

An edit touches one file, and other files can quote it: a later post that repeats a sentence
of an earlier one in quotation marks, a wiki page that cites a rule word for word. Cut or
reword that sentence and the quote no longer matches its source, which no check of the edited
file alone can see (18 Oct 2026: post 17 of the Module Federation series quotes post 15's
"The chunks are guarded; the map is naked."). This script reads every other file under the
--in paths, takes each quoted span in them, and keeps the spans that appear in ORIGINAL.

    find    prints each such span with the file and line that quote it.
    check   prints the spans that appear in ORIGINAL but no longer in EDITED.

A quoted span is text inside double quotes (straight or curly) or a blockquote line, in the
body of the file: front matter is skipped. An ellipsis inside a quote splits it into parts,
and each part is checked on its own. A part of fewer than --min-words space-separated words
(default 5) is ignored, so a quoted word, a slug or a path never counts. Matching ignores case, punctuation, markdown emphasis and spacing. A --in path is a
file, or a directory searched for .md, .mdx, .txt and .html files; fenced code blocks in those
files are skipped. ORIGINAL, EDITED, --self (the live file ORIGINAL is a backup of) and
anything under ~/.claude/edit-doc are never searched.

Exit 0 when nothing is missing (find exits 0 whatever it prints), 1 when check reports a
missing span, 2 when the script cannot run (a file is missing or unreadable, or no --in).
"""
import json
import os
import re
import sys

EXTENSIONS = (".md", ".mdx", ".txt", ".html")
SKIP_DIRS = {"node_modules", ".git", "dist", ".astro", "__pycache__", ".next", "build"}
MAX_BYTES = 2_000_000
MAX_FILES = 20_000
DEFAULT_MIN_WORDS = 5

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
STRAIGHT = re.compile(r'"([^"]+)"')
CURLY = re.compile(r"“([^”]+)”")
ELLIPSIS = re.compile(r"\[?\s*(?:\.{3}|…)\s*\]?")
WORD = re.compile(r"[\w']+")


class QuoteError(Exception):
    pass


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise QuoteError(f"cannot read {path}: {e}")


def words(text):
    text = text.lower().replace("’", "'").replace("‘", "'")
    return [w.strip("_'") for w in WORD.findall(text) if w.strip("_'")]


def haystack(text):
    return " " + " ".join(words(text)) + " "


def spans(text):
    """Yield (line, quoted text) for every quote in a file, outside fenced code."""
    lines = text.split("\n")
    first = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                first = i + 1
                break
    fence = None
    paragraph, start = [], 0
    out = []

    def flush():
        nonlocal paragraph, start
        if paragraph:
            joined = " ".join(p.strip() for p in paragraph)
            block = [p for p in paragraph if p.lstrip().startswith(">")]
            if len(block) == len(paragraph):
                out.append((start, " ".join(p.lstrip()[1:].strip() for p in paragraph)))
            else:
                for rx in (STRAIGHT, CURLY):
                    for m in rx.finditer(joined):
                        out.append((start, m.group(1)))
        paragraph, start = [], 0

    for n, line in enumerate(lines, 1):
        if n <= first:
            continue
        m = FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            flush()
            fence = m.group(1)
            continue
        if not line.strip():
            flush()
            continue
        if not paragraph:
            start = n
        paragraph.append(line)
    flush()
    return out


def parts(quote, min_words):
    return [p.strip() for p in ELLIPSIS.split(quote) if len(p.split()) >= min_words and words(p)]


def files_under(roots, skip):
    seen, found = set(), []
    for root in roots:
        if os.path.isfile(root):
            candidates = [root]
        elif os.path.isdir(root):
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                candidates += [os.path.join(dirpath, f) for f in sorted(filenames) if f.endswith(EXTENSIONS)]
        else:
            raise QuoteError(f"--in path does not exist: {root}")
        for c in candidates:
            real = os.path.realpath(c)
            if real in seen or real in skip or real.startswith(skip_prefix()):
                continue
            try:
                if os.path.getsize(real) > MAX_BYTES:
                    continue
            except OSError:
                continue
            seen.add(real)
            found.append(c)
            if len(found) > MAX_FILES:
                raise QuoteError(f"more than {MAX_FILES} files under the --in paths; narrow them")
    return found


def skip_prefix():
    return os.path.realpath(os.path.expanduser("~/.claude/edit-doc")) + os.sep


def quoted_from(original_text, roots, skip, min_words):
    """Every quoted part, in the other files, that appears in the original."""
    hay = haystack(original_text)
    hits = []
    for path in files_under(roots, skip):
        try:
            text = read(path)
        except QuoteError:
            continue
        for line, quote in spans(text):
            for part in parts(quote, min_words):
                if " " + " ".join(words(part)) + " " in hay:
                    hits.append({"file": path, "line": line, "quote": part})
    return hits


def find(original, roots, min_words, own=()):
    skip = {os.path.realpath(original)} | {os.path.realpath(o) for o in own}
    return quoted_from(read(original), roots, skip, min_words)


def check(original, edited, roots, min_words, own=()):
    edited_text = read(edited)
    skip = {os.path.realpath(original), os.path.realpath(edited)} | {os.path.realpath(o) for o in own}
    hits = quoted_from(read(original), roots, skip, min_words)
    hay = haystack(edited_text)
    missing = [h for h in hits if " " + " ".join(words(h["quote"])) + " " not in hay]
    return hits, missing


def show(quote):
    one = " ".join(quote.split())
    return one if len(one) <= 100 else one[:97] + "..."


def parse(argv):
    roots, own, min_words, rest, i = [], [], DEFAULT_MIN_WORDS, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--in" and i + 1 < len(argv):
            roots.append(os.path.expanduser(argv[i + 1]))
            i += 2
        elif a == "--self" and i + 1 < len(argv):
            own.append(os.path.expanduser(argv[i + 1]))
            i += 2
        elif a == "--min-words" and i + 1 < len(argv):
            try:
                min_words = int(argv[i + 1])
            except ValueError:
                raise QuoteError("--min-words takes a whole number")
            i += 2
        else:
            rest.append(a)
            i += 1
    return rest, roots, own, min_words


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    try:
        rest, roots, own, min_words = parse(argv)
        if rest and rest[0] in ("find", "check") and not roots:
            raise QuoteError("give at least one --in PATH to search")
        if len(rest) == 2 and rest[0] == "find":
            hits = find(rest[1], roots, min_words, own)
            if as_json:
                print(json.dumps({"original": rest[1], "quoted": hits}, ensure_ascii=False))
            else:
                for h in hits:
                    print(f"{h['file']}:{h['line']}: \"{show(h['quote'])}\"")
                print(f"{len(hits)} quoted span(s) in other files appear in {rest[1]}")
            return 0
        if len(rest) == 3 and rest[0] == "check":
            hits, missing = check(rest[1], rest[2], roots, min_words, own)
            if as_json:
                print(json.dumps({"original": rest[1], "edited": rest[2], "total": len(hits), "missing": missing}, ensure_ascii=False))
            else:
                for h in missing:
                    print(f"MISSING {h['file']}:{h['line']} quotes \"{show(h['quote'])}\"")
                print(f"{len(hits)} quoted span(s) in other files; {len(missing)} no longer in {rest[2]}")
            return 1 if missing else 0
    except QuoteError as e:
        print(f"inbound-quotes: {e}", file=sys.stderr)
        return 2
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
