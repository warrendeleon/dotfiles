#!/usr/bin/env python3
"""Point a reviewer at places the house writing guides list. Pointers, never findings.

    writing-lint.py [--guides DIR] [--json] FILE [FILE ...]

Reads Markdown or text files and prints where they contain a term from the avoid-list tables
of ai-writing-gotchas.md, a hit of the leftovers search in revision-passes.md, and the
em-dash density per 1,000 words. A hit is a pointer to read in context, not a finding: the
judgement clause in the avoid-list keeps a banned word used in its literal technical sense,
and the revision guide says the same of the leftovers search. Nothing is rewritten or decided.

The guides are read at run time from ~/.wiki/personal/writing (or --guides DIR) and never
copied here, so the lint cannot drift from them.

Output (plain text): a one-line header, one line per hit, then a summary.

    file:line: "matched text" — <table heading> [tag] → <replacement>
    file:line: "matched text" — leftovers

where the separator is an em-dash and the arrow is U+2192. --json prints the same data as JSON. Exit 0 when the run succeeds, with or without hits. Exit 2 when it cannot run: a
guide file is missing, no avoid-list table parses, a table with a term column yields no
terms, the leftovers pattern is missing or does not compile, an input file cannot be read, or
the usage is wrong. A lint that silently finds nothing is worse than one that fails.

How the guides are parsed (by structure, never by line number or heading list):
- A table is a header row, a separator row and the rows after it, outside fenced code. Its
  heading is the nearest heading above it.
- The term column is the first column headed like a list of terms (Banned, Overused, Phrase,
  Idiom, Words, ...). A table with a replacement-like column (Replacement, Instead, ...) and
  no such header uses its first column. Any other table is skipped and reported.
- The replacement column is the first column headed like one. The tag column is a column
  headed Why or Tag, or one whose cells are nearly all tell or house, with an optional
  qualifier such as "(provisional)".
- A cell lists several terms separated by ";" (which outranks ","), ",", " or " and "/". A comma
  straight after a spaced ellipsis ("Despite its ..., X faces") belongs to the phrase.
  "plays a key / pivotal / role in" expands to one term per alternative around the shared
  words. Quotes, backticks, bold marks and parenthetical glosses are dropped, a trailing or
  leading ellipsis is dropped, an ellipsis or a bare X, Y or Z inside a term matches any few
  words, and a cell such as "Em-dash (the mark itself) anywhere in prose" takes the symbol
  in the parentheses.
- A piece is explanatory prose, not a term, when it runs past 8 words or starts with plus,
  see, e.g., i.e., etc. or including. Skipped pieces are listed in the JSON.

How terms match: case-insensitive on word boundaries, -ise/-ize and -isation/-ization
as one word, a space and a hyphen as one separator, one line wrap allowed inside a phrase.
Frontmatter, fenced code, inline code, URLs, link targets and HTML comments are skipped.
The leftovers pattern runs on the raw file, as the guide's grep does, because its classes live
in URLs and code; a hit outside prose says where it sits. The em-dash term of the Punctuation
table is counted as a density, not listed hit by hit. The density leaves out reference rows
("[[page]] — description", "term — definition": a list item whose part before the dash is a
link or at most 5 words with no sentence punctuation), their wrapped lines, and table cells
holding only the mark; the words of those rows are left out of the count too.
"""
import bisect
import json
import os
import re
import shlex
import sys
from collections import OrderedDict

HEADER = ("writing-lint: pointers to read in context, not findings. "
          "A hit marks a place to look; nothing is rewritten or decided.")
GOTCHAS = "ai-writing-gotchas.md"
REVISION = "revision-passes.md"
MASK = "\x00"
MAX_TERM_WORDS = 8
PROSE_LEADS = {"plus", "see", "e.g.", "i.e.", "etc.", "including"}
TERM_HEADERS = {"banned", "overused", "avoid", "avoided", "term", "terms", "word", "words",
                "phrase", "phrases", "idiom", "idioms", "expression", "expressions",
                "construction", "constructions", "vocabulary", "pattern", "patterns"}
REPLACEMENT_HEADERS = {"replacement", "replacements", "instead", "use", "use instead",
                       "say instead", "alternative", "alternatives", "fix", "prefer", "rewrite"}
TAG_HEADERS = {"why", "tag", "tags"}
TAG_RE = re.compile(r"^(tell|house)(?:\s*\(([^)]*)\))?$", re.I)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
GLUE = r"[ \t]*\n[ \t]*(?:>[ \t]*)*"
SEP = r"(?:" + GLUE + r"|[ \t]+|-)"
GAP = r"(?:(?!\n[ \t]*\n)[^.!?;]){1,80}?"
ISE_RE = re.compile(r"^([a-z]*[a-z])i[sz](e|es|ed|er|ers|ing|ings|ation|ations|ability)$", re.I)
WORD_RE = re.compile(r"\w+(?:['’-]\w+)*")
POSIX_CLASSES = {
    "alpha": "a-zA-Z", "digit": "0-9", "alnum": "a-zA-Z0-9", "upper": "A-Z", "lower": "a-z",
    "space": r" \t\n\r\f\v", "blank": r" \t", "punct": r"!-/:-@\[-`{-~", "xdigit": "0-9A-Fa-f",
    "word": r"\w", "cntrl": r"\x00-\x1f\x7f", "print": " -~", "graph": "!-~",
}


class GuideError(Exception):
    """A guide file is missing or does not have the shape the lint expects."""


# ---------------------------------------------------------------- guide: avoid-list tables

def fenced_flags(lines):
    """True for every line that opens, closes or sits inside a fenced code block."""
    flags, fence = [False] * len(lines), None
    for i, line in enumerate(lines):
        m = FENCE_RE.match(line)
        if fence is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence = (m.group(1)[0], len(m.group(1)))
                flags[i] = True
        else:
            flags[i] = True
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip():
                fence = None
    return flags


def split_row(line):
    """Cells of a Markdown table row; \\| is a literal pipe and a pipe inside backticks stays."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, in_code, i = [], [], False, 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if c == "`":
            in_code = not in_code
        if c == "|" and not in_code:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def is_separator(line):
    s = line.strip()
    return "-" in s and "|" in s and re.fullmatch(r"[\s|:\-]+", s) is not None


def find_tables(text):
    """Every table outside fenced code: dicts of heading, line, header and rows."""
    lines = text.split("\n")
    fenced = fenced_flags(lines)
    tables, heading, i = [], "(no heading)", 0
    while i < len(lines):
        if fenced[i]:
            i += 1
            continue
        h = HEADING_RE.match(lines[i])
        if h:
            heading = h.group(2)
            i += 1
            continue
        if "|" in lines[i] and i + 1 < len(lines) and not fenced[i + 1] and is_separator(lines[i + 1]):
            header, rows, j = split_row(lines[i]), [], i + 2
            while j < len(lines) and not fenced[j] and lines[j].strip() and "|" in lines[j]:
                rows.append(split_row(lines[j]))
                j += 1
            tables.append({"heading": heading, "line": i + 1, "header": header, "rows": rows})
            i = j
            continue
        i += 1
    return tables


def norm_header(h):
    return re.sub(r"[*`]", "", h).strip().lower()


def classify_columns(header, rows):
    """(term, replacement, tag) column indexes, or None when no column lists terms."""
    names = [norm_header(h) for h in header]
    term = next((i for i, n in enumerate(names) if n in TERM_HEADERS), None)
    repl = next((i for i, n in enumerate(names) if n in REPLACEMENT_HEADERS and i != term), None)
    if term is None and repl is not None and repl != 0:
        term = 0
    if term is None:
        return None
    tag = None
    for i, n in enumerate(names):
        if i in (term, repl):
            continue
        cells = [r[i] for r in rows if i < len(r) and r[i].strip()]
        if cells and (n in TAG_HEADERS or sum(1 for c in cells if TAG_RE.match(c)) >= 0.8 * len(cells)):
            tag = i
            break
    return term, repl, tag


QUOTES = {'"': '"', "“": "”", "`": "`"}


def split_top(s, sep):
    """Split on sep outside quotes, backticks and parentheses."""
    straight_ok, tick_ok = s.count('"') % 2 == 0, s.count("`") % 2 == 0
    out, cur, depth, close = [], [], 0, None
    for ch in s:
        if close:
            cur.append(ch)
            if ch == close:
                close = None
            continue
        if ch == "“" or (ch == '"' and straight_ok) or (ch == "`" and tick_ok):
            close = QUOTES[ch]
            cur.append(ch)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        if ch == sep and depth == 0 and not (sep == "," and re.search(r"\s(?:\.\.\.|…)$", "".join(cur))):
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def strip_parens(s):
    prev = None
    while prev != s:
        prev, s = s, re.sub(r"\s*\([^()]*\)", "", s)
    return s.replace("(", "").replace(")", "")


def strip_decor(s):
    s = re.sub(r"\*\*|__|`|\"|“|”", "", s).strip()
    if len(s) > 2 and s[0] == s[-1] == "'":
        s = s[1:-1]
    return s.strip()


def expand_slashes(phrase):
    """'plays a key / pivotal role in' -> one phrase per alternative, keeping the shared words."""
    m = re.search(r"\S+(?:\s*/\s*\S+)+", phrase)
    if not m:
        return [phrase]
    items = re.split(r"\s*/\s*", m.group(0))
    out = []
    for item in items:
        out.extend(expand_slashes(phrase[:m.start()] + item + phrase[m.end():]))
    return list(OrderedDict.fromkeys(out))


def prose_reason(text):
    words = re.sub(r"\s*/\s*", "/", text).split()
    if len(words) > MAX_TERM_WORDS:
        return "prose: longer than %d words" % MAX_TERM_WORDS
    if words and words[0].lower().rstrip(",:") in PROSE_LEADS:
        return "prose: starts with '%s'" % words[0]
    return None


def canon_word(w):
    w = w.lower().replace("’", "'")
    m = ISE_RE.match(w)
    return m.group(1) + "iz" + m.group(2) if m else w


def word_rx(word):
    m = ISE_RE.match(word)
    if m:
        return re.escape(m.group(1)) + "i[sz]" + m.group(2)
    return "['’]".join(re.escape(p) for p in re.split(r"['’]", word))


def lit_rx(lit):
    """Regex for a literal run: words (-ise/-ize), separators (space, hyphen, line wrap), punctuation."""
    out = []
    for tok in re.split(r"([ \t\n]+|-+)", lit):
        if not tok:
            continue
        if re.fullmatch(r"[ \t\n]+|-+", tok):
            out.append(SEP)
            continue
        for piece in re.split(r"([A-Za-z]+(?:['’][A-Za-z]+)*)", tok):
            if not piece:
                continue
            if piece[0].isalpha():
                out.append(word_rx(piece))
            else:
                out.append("".join("['’]" if ch in "'’" else re.escape(ch) for ch in piece))
    return "".join(out)


def build_regex(parts):
    pieces = []
    for p in parts:
        rx = lit_rx(p)
        if p[:1].isalnum():
            rx = r"(?<!\w)" + rx
        if p[-1:].isalnum():
            rx += r"(?!\w)"
        pieces.append(rx)
    return re.compile(GAP.join(pieces), re.I)


def norm_key(parts):
    return "|".join(" ".join(canon_word(w) for w in re.split(r"[\s-]+", p) if w) for p in parts)


def finalize(phrase):
    """A cleaned phrase -> (text, parts), or a skip reason string."""
    t = re.sub(r"\s+", " ", phrase).replace("…", "...").strip()
    t = re.sub(r"(?<![\w'’-])[XYZ](?![\w'’-])", "...", t)
    t = t.strip(" .,;:!?-")
    parts = [p.strip() for p in t.split("...")]
    parts = [p for p in parts if p]
    if sum(c.isalnum() for p in parts for c in p) < 2:
        return "placeholder only"
    return t, parts


def terms_from_cell(cell):
    """(terms, skipped) for one term cell. A term is {text, parts, symbol}."""
    terms, skipped = [], []
    segs = split_top(cell.strip(), ";")
    if len(segs) == 1:
        segs = split_top(cell.strip(), ",")
    for seg in segs:
        seg = seg.strip()
        if not seg:
            continue
        sym = re.search(r"\(\s*([^\w\s()]+)\s*\)", seg)
        if sym and set(sym.group(1)) - set(".…"):
            terms.append({"text": sym.group(1), "parts": [sym.group(1)], "symbol": True})
            continue
        body = strip_parens(seg)
        quoted = re.fullmatch(r"\s*[\"“`].*[\"”`]\s*", body, re.S) is not None
        body = strip_decor(body)
        if not body:
            continue
        why = prose_reason(body)
        if why:
            skipped.append({"text": seg, "reason": why})
            continue
        alts = [body] if quoted else re.split(r"\s+or\s+", body, flags=re.I)
        for alt in alts:
            why = prose_reason(alt)
            if why:
                skipped.append({"text": alt, "reason": why})
                continue
            for phrase in expand_slashes(alt):
                res = finalize(phrase)
                if isinstance(res, str):
                    if re.search(r"[A-Za-z0-9]", re.sub(r"(?<![\w'’-])[XYZ](?![\w'’-])", "", phrase)):
                        skipped.append({"text": phrase, "reason": res})
                else:
                    terms.append({"text": res[0], "parts": res[1], "symbol": False})
    return terms, skipped


class Term:
    __slots__ = ("text", "key", "regex", "table", "tag", "replacement", "density_only", "order")

    def __init__(self, text, parts, symbol, table, tag, replacement, order):
        self.text, self.table, self.tag, self.replacement, self.order = text, table, tag, replacement, order
        self.density_only = symbol and text == "—"
        if symbol:
            self.key = text
            self.regex = re.compile(re.escape(text))
        else:
            self.key = norm_key(parts)
            self.regex = build_regex(parts)


def parse_gotchas(text):
    """Parse the avoid-list tables. Returns dict(terms, by_table, skipped_tables, skipped_cells)."""
    tables = find_tables(text)
    terms, by_table, skipped_tables, skipped_cells = [], OrderedDict(), [], []
    for t in tables:
        cols = classify_columns(t["header"], t["rows"])
        if cols is None:
            skipped_tables.append({"heading": t["heading"], "header": t["header"]})
            continue
        ti, ri, gi = cols
        found = 0
        for row in t["rows"]:
            if ti >= len(row) or not row[ti].strip():
                continue
            repl = re.sub(r"\s+", " ", row[ri].replace("**", "")).strip() if ri is not None and ri < len(row) else ""
            tagm = TAG_RE.match(row[gi]) if gi is not None and gi < len(row) else None
            tag = re.sub(r"\s+", " ", row[gi]).strip().lower() if tagm else None
            cell_terms, cell_skipped = terms_from_cell(row[ti])
            skipped_cells.extend(dict(s, table=t["heading"]) for s in cell_skipped)
            for ct in cell_terms:
                terms.append(Term(ct["text"], ct["parts"], ct["symbol"], t["heading"], tag, repl or None, len(terms)))
                found += 1
        if not found:
            raise GuideError("%s: the table under '%s' (line %d) has a term column but yielded no terms"
                             % (GOTCHAS, t["heading"], t["line"]))
        by_table[t["heading"]] = by_table.get(t["heading"], 0) + found
    if not terms:
        raise GuideError("%s: no avoid-list tables found (expected a header row, a separator row "
                         "and rows, with a column headed Banned, Overused, Phrase, Idiom, Words or similar)"
                         % GOTCHAS)
    return {"terms": terms, "by_table": by_table, "skipped_tables": skipped_tables,
            "skipped_cells": skipped_cells}


# ---------------------------------------------------------------- guide: leftovers pattern

def posix_ere_to_python(p):
    """Translate a POSIX extended regular expression, as grep -E reads it, to Python's re."""
    out, i, n = [], 0, len(p)
    while i < n:
        c = p[i]
        if c == "\\" and i + 1 < n:
            d = p[i + 1]
            if d in "<>":
                out.append(r"\b")
            elif d in "wWsSdDbB" or d.isdigit():
                out.append("\\" + d)
            else:
                out.append(re.escape(d))
            i += 2
            continue
        if c == "[":
            j, neg, items, first = i + 1, False, [], True
            if j < n and p[j] == "^":
                neg, j = True, j + 1
            closed = False
            while j < n:
                ch = p[j]
                if ch == "]" and not first:
                    closed = True
                    break
                if ch == "[" and j + 1 < n and p[j + 1] in ":.=":
                    kind = p[j + 1]
                    end = p.find(kind + "]", j + 2)
                    if end != -1:
                        name = p[j + 2:end]
                        if kind == ":":
                            if name not in POSIX_CLASSES:
                                raise GuideError("%s: unknown POSIX class [:%s:] in the leftovers pattern" % (REVISION, name))
                            items.append(POSIX_CLASSES[name])
                        else:
                            items.append(re.escape(name))
                        j, first = end + 2, False
                        continue
                items.append("\\" + ch if ch in "\\[]&~|^" else ch)
                first = False
                j += 1
            if not closed:
                raise GuideError("%s: unterminated bracket expression in the leftovers pattern" % REVISION)
            out.append("[" + ("^" if neg else "") + "".join(items) + "]")
            i = j + 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def grep_pattern(tokens):
    """(pattern, ignore_case) from a tokenised grep -E command, or None when it is not one."""
    extended = icase = False
    pattern, i = None, 1
    while i < len(tokens):
        t = tokens[i]
        if t.startswith("--regexp="):
            pattern = t.split("=", 1)[1]
        elif t == "--extended-regexp":
            extended = True
        elif t == "--ignore-case":
            icase = True
        elif t.startswith("-") and not t.startswith("--") and len(t) > 1:
            extended = extended or "E" in t
            icase = icase or "i" in t
            if t.endswith("e") and i + 1 < len(tokens):
                pattern, i = tokens[i + 1], i + 1
        elif t.startswith("--"):
            pass
        elif pattern is None:
            pattern = t
        i += 1
        if pattern is not None:
            break
    if tokens[0] == "egrep":
        extended = True
    return (pattern, icase) if pattern is not None and extended else None


def parse_revision(text):
    """The leftovers regex from the bash block of the 'Leftovers search' section."""
    lines = text.split("\n")
    fenced = fenced_flags(lines)
    start = level = None
    for i, line in enumerate(lines):
        h = HEADING_RE.match(line) if not fenced[i] else None
        if h and "leftovers search" in h.group(2).lower():
            start, level = i, len(h.group(1))
            break
    if start is None:
        raise GuideError("%s: no 'Leftovers search' section found" % REVISION)
    end = len(lines)
    for i in range(start + 1, len(lines)):
        h = HEADING_RE.match(lines[i]) if not fenced[i] else None
        if h and len(h.group(1)) <= level:
            end = i
            break
    blocks, i = [], start + 1
    while i < end:
        m = FENCE_RE.match(lines[i])
        if m and fenced[i]:
            ch, size, info, body = m.group(1)[0], len(m.group(1)), m.group(2).strip().lower(), []
            i += 1
            while i < end:
                c = FENCE_RE.match(lines[i])
                if c and c.group(1)[0] == ch and len(c.group(1)) >= size and not c.group(2).strip():
                    break
                body.append(lines[i])
                i += 1
            if info.split(" ")[0] in ("bash", "sh", "shell", "zsh", ""):
                blocks.append("\n".join(body))
        i += 1
    for block in blocks:
        for cmd in re.sub(r"\\\n\s*", " ", block).split("\n"):
            cmd = cmd.strip().lstrip("$ ").strip()
            if not re.match(r"(?:e?grep)\b", cmd):
                continue
            try:
                tokens = shlex.split(cmd)
            except ValueError as e:
                raise GuideError("%s: cannot read the grep command in 'Leftovers search': %s" % (REVISION, e))
            got = grep_pattern(tokens)
            if got is None:
                raise GuideError("%s: the grep in 'Leftovers search' is not a grep -E command with a pattern" % REVISION)
            pattern, icase = got
            try:
                regex = re.compile(posix_ere_to_python(pattern), re.I if icase else 0)
            except re.error as e:
                raise GuideError("%s: the leftovers pattern does not compile: %s" % (REVISION, e))
            return {"pattern": pattern, "regex": regex}
    raise GuideError("%s: no bash block with a grep -E pattern in the 'Leftovers search' section" % REVISION)


def read_guide(path):
    if not os.path.isfile(path):
        raise GuideError("guide file missing: %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError) as e:
        raise GuideError("cannot read guide file %s: %s" % (path, e))


def load_guides(guides_dir):
    avoid = parse_gotchas(read_guide(os.path.join(guides_dir, GOTCHAS)))
    avoid["leftovers"] = parse_revision(read_guide(os.path.join(guides_dir, REVISION)))
    return avoid


# ---------------------------------------------------------------- the document under review

class Doc:
    """A text with the regions the lint skips blanked out, line numbers kept."""

    def __init__(self, text):
        self.text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
        self.spans = []
        self.masked = self._mask()
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", self.text)]

    def line_of(self, pos):
        return bisect.bisect_right(self.line_starts, pos)

    def region_at(self, pos):
        for s, e, kind in self.spans:
            if s <= pos < e:
                return kind
        return "prose"

    def _mask(self):
        text = self.text
        buf = list(text)

        def blank(s, e, kind):
            self.spans.append((s, e, kind))
            buf[s:e] = [ch if ch == "\n" else MASK for ch in buf[s:e]]

        fm = re.match(r"---[ \t]*\n", text)
        if fm:
            close = re.compile(r"^(?:---|\.\.\.)[ \t]*$", re.M).search(text, fm.end())
            if close:
                blank(0, close.end(), "frontmatter")
        lines = text.split("\n")
        flags, offsets, pos = fenced_flags(lines), [], 0
        for line in lines:
            offsets.append(pos)
            pos += len(line) + 1
        i = 0
        while i < len(lines):
            if flags[i]:
                j = i
                while j + 1 < len(lines) and flags[j + 1]:
                    j += 1
                blank(offsets[i], offsets[j] + len(lines[j]), "fenced code")
                i = j + 1
            else:
                i += 1
        for m in re.finditer(r"<!--.*?-->", "".join(buf), re.S):
            blank(m.start(), m.end(), "HTML comment")
        for m in re.finditer(r"(?<!`)(`+)(?!`)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", "".join(buf), re.S):
            blank(m.start(), m.end(), "inline code")
        for m in re.finditer(r"(?<=\])\((?=[^\s)])[^)\n]*\)", "".join(buf)):
            blank(m.start(), m.end(), "link target")
        for m in re.finditer(r"(?:https?|ftp)://[^\s<>\"\x00]+", "".join(buf)):
            url = m.group(0)
            while url and (url[-1] in ".,;:!?'" or (url[-1] in ")]" and url.count(url[-1]) > url.count("(" if url[-1] == ")" else "["))):
                url = url[:-1]
            blank(m.start(), m.start() + len(url), "URL")
        for m in re.finditer(r"\[\[([^\]|\n]+)", "".join(buf)):
            blank(m.start(1), m.end(1), "link target")
        return "".join(buf)


def collapse(s):
    return re.sub(r"\s*\n\s*(?:>\s*)*", " ", s)


def find_term_hits(doc, terms):
    """Term hits, one per matched place and term; a term listed in several tables is merged."""
    grouped = OrderedDict()
    for t in terms:
        if t.density_only:
            continue
        for m in t.regex.finditer(doc.masked):
            if m.end() > m.start():
                grouped.setdefault((m.start(), m.end(), t.key), []).append(t)
    hits = []
    for (start, end, _), ts in sorted(grouped.items(), key=lambda kv: kv[0][:2]):
        ts = sorted(ts, key=lambda t: (t.replacement is None, t.order))
        primary = ts[0]
        also = []
        for t in ts[1:]:
            if t.table != primary.table and t.table not in also:
                also.append(t.table)
        hits.append({"line": doc.line_of(start), "start": start, "text": collapse(doc.text[start:end]),
                     "kind": "term", "term": primary.text, "table": primary.table, "tag": primary.tag,
                     "replacement": primary.replacement, "also": also, "region": "prose"})
    return hits


# Acronyms a technical reader already holds; every other one is spelled out on first use
# (ai-writing-gotchas.md, "Spell Out Acronyms and Tool Names").
COMMON_ACRONYMS = {"UK", "US", "EU", "URL", "URLs", "API", "APIs", "HTML", "CSS", "JS", "JSON", "PDF",
                   "ID", "IDs", "HTTP", "HTTPS", "SDK", "UI", "UTC", "OK", "TV", "AM", "PM", "FAQ"}
ACRONYM_RE = re.compile(r"(?<![\w./-])([A-Z][A-Z0-9]{1,5}s?)(?![\w/-])")
LONG_PARAGRAPH = 200


def find_acronyms(doc):
    """The first use of each acronym that is not spelled out where it first appears."""
    hits, seen = [], set()
    for m in ACRONYM_RE.finditer(doc.masked):
        acr = m.group(1)
        base = acr[:-1] if acr.endswith("s") and acr[:-1].isupper() else acr
        if base in seen or acr in COMMON_ACRONYMS or base in COMMON_ACRONYMS or not re.search(r"[A-Z].*[A-Z]", base):
            continue
        seen.add(base)
        line_start = doc.text.rfind("\n", 0, m.start()) + 1
        line_end = doc.text.find("\n", m.end())
        line = doc.text[line_start:line_end if line_end != -1 else len(doc.text)]
        if re.match(r"\s*#", line):
            seen.discard(base)              # a heading is not a first use; wait for the prose
            continue
        if re.search(r"\(\s*" + re.escape(base) + r"s?\s*\)", line) or re.search(re.escape(acr) + r"\s*\([^)]*[a-z][^)]*\)", line):
            continue                        # "Full Name (ACR)" or "ACR (full name)"
        hits.append({"line": doc.line_of(m.start()), "start": m.start(), "text": acr, "kind": "acronym",
                     "table": "acronym not spelled out at first use", "tag": "house", "replacement": None,
                     "also": [], "region": "prose"})
    return hits


def find_long_paragraphs(doc):
    """Prose paragraphs over LONG_PARAGRAPH words: one mechanism per paragraph (guide 1)."""
    hits = []
    for m in re.finditer(r"(?:^|\n\s*\n)((?:[^\n]+\n?)+)", doc.masked):
        block = m.group(1)
        lines = [l for l in block.split("\n") if l.strip(MASK + " \t")]
        if not lines or any(re.match(r"\s*(\||#|>)", l) for l in lines):
            continue
        n = len(WORD_RE.findall(block))
        if n > LONG_PARAGRAPH:
            start = m.start(1)
            hits.append({"line": doc.line_of(start), "start": start, "text": "%d words" % n, "kind": "paragraph",
                         "table": "paragraph over %d words" % LONG_PARAGRAPH, "tag": "house", "replacement": None,
                         "also": [], "region": "prose"})
    return hits


def find_leftovers(doc, regex):
    hits = []
    for lineno, line in enumerate(doc.text.split("\n"), 1):
        for m in regex.finditer(line):
            if m.end() > m.start():
                region = doc.region_at(doc.line_starts[lineno - 1] + m.start())
                hits.append({"line": lineno, "start": doc.line_starts[lineno - 1] + m.start(),
                             "text": m.group(0), "kind": "leftovers", "table": "leftovers", "tag": None,
                             "replacement": None, "also": [], "region": region})
    return hits


LIST_ITEM_RE = re.compile(r"^\s{0,6}(?:[-*+]|\d{1,3}[.)])\s+(?P<body>\S.*)$")


def is_reference_row(line):
    """A list item shaped '[[page]] — description' or 'term — definition'."""
    m = LIST_ITEM_RE.match(line)
    d = re.match(r"^(?P<term>.+?)\s+—\s+\S", m.group("body")) if m else None
    if not d:
        return False
    core = re.sub(r"^(?:\*\*|__|\*|_)+|(?:\*\*|__|\*|_)+$", "", d.group("term").strip()).strip()
    if re.fullmatch(r"\[\[[^\]]+\]\]|\[[^\]]+\]\([^)]*\)", core):
        return True
    core = core.strip("`")
    return 0 < len(core.split()) <= 5 and not re.search(r"[!?;:,]|\.$", core)


def emdash_stats(doc):
    """Em-dashes per 1,000 words of prose. Reference rows are left out of both counts."""
    buf = list(doc.masked)
    raw, offsets, pos = doc.text.split("\n"), [], 0
    for line in raw:
        offsets.append(pos)
        pos += len(line) + 1
    rows, i = 0, 0
    while i < len(raw):
        masked_line = doc.masked[offsets[i]:offsets[i] + len(raw[i])]
        if masked_line.strip(MASK + " \t") and is_reference_row(raw[i]):
            rows += 1
            j = i
            while j + 1 < len(raw) and raw[j + 1].strip() and raw[j + 1][0] in " \t" and not LIST_ITEM_RE.match(raw[j + 1]):
                j += 1
            buf[offsets[i]:offsets[j] + len(raw[j])] = [MASK] * (offsets[j] + len(raw[j]) - offsets[i])
            i = j + 1
        else:
            i += 1
    # A table cell holding only the mark is an empty-value marker, not punctuation in a sentence.
    prose, null_cells = re.subn(r"(?<=\|)([ \t]*)—([ \t]*)(?=\|)", lambda m: m.group(1) + MASK + m.group(2),
                               "".join(buf))
    count, words = prose.count("—"), len(WORD_RE.findall(prose))
    return {"count": count, "words": words, "per_1000": round(1000.0 * count / words, 1) if words else 0.0,
            "reference_rows_excluded": rows, "empty_cells_excluded": null_cells}


# ---------------------------------------------------------------- run and report

def lint(files, guides_dir):
    guides = load_guides(guides_dir)
    results = []
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError as e:
            raise GuideError("input file cannot be read: %s: %s" % (path, e.strerror or e))
        doc = Doc(raw)
        hits = (find_term_hits(doc, guides["terms"]) + find_leftovers(doc, guides["leftovers"]["regex"])
                + find_acronyms(doc) + find_long_paragraphs(doc))
        hits.sort(key=lambda h: (h["line"], h["start"], h["kind"]))
        for h in hits:
            del h["start"]
        results.append({"file": path, "hits": hits, "emdash": emdash_stats(doc)})
    by_table = OrderedDict()
    leftovers = 0
    for r in results:
        for h in r["hits"]:
            if h["kind"] == "leftovers":
                leftovers += 1
                continue
            if h["kind"] in ("acronym", "paragraph"):
                by_table.setdefault(h["table"], {"hits": 0, "by_tag": OrderedDict()})
                by_table[h["table"]]["hits"] += 1
                by_table[h["table"]]["by_tag"]["house"] = by_table[h["table"]]["by_tag"].get("house", 0) + 1
                continue
            entry = by_table.setdefault(h["table"], {"hits": 0, "by_tag": OrderedDict()})
            entry["hits"] += 1
            entry["by_tag"][h["tag"] or "untagged"] = entry["by_tag"].get(h["tag"] or "untagged", 0) + 1
    return {
        "note": HEADER,
        "guides": {"dir": guides_dir, "avoid_list": os.path.join(guides_dir, GOTCHAS),
                   "leftovers": os.path.join(guides_dir, REVISION)},
        "terms_loaded": len(guides["terms"]),
        "terms_by_table": guides["by_table"],
        "skipped_tables": guides["skipped_tables"],
        "skipped_cells": guides["skipped_cells"],
        "leftovers_pattern": guides["leftovers"]["pattern"],
        "files": results,
        "summary": {"hits": sum(len(r["hits"]) for r in results), "by_table": by_table, "leftovers": leftovers},
    }


def hit_line(path, h):
    line = '%s:%d: "%s" — %s' % (path, h["line"], h["text"], h["table"])
    if h["tag"]:
        line += " [%s]" % h["tag"]
    if h["replacement"]:
        line += " → %s" % h["replacement"]
    if h["also"]:
        line += " (also: %s)" % "; ".join(h["also"])
    if h["region"] != "prose":
        line += " (in %s)" % h["region"]
    return line


def render_text(result):
    out = [HEADER]
    for r in result["files"]:
        out.extend(hit_line(r["file"], h) for h in r["hits"])
    s = result["summary"]
    out.append("")
    out.append("summary: %d hits in %d files (%d terms from %d tables)"
               % (s["hits"], len(result["files"]), result["terms_loaded"], len(result["terms_by_table"])))
    for table, e in s["by_table"].items():
        out.append("  %s: %d (%s)" % (table, e["hits"], ", ".join("%s %d" % kv for kv in e["by_tag"].items())))
    if s["leftovers"]:
        out.append("  leftovers: %d" % s["leftovers"])
    if result["skipped_tables"]:
        out.append("  tables with no term column, skipped: " + "; ".join(t["heading"] for t in result["skipped_tables"]))
    if result["skipped_cells"]:
        out.append("  cell pieces skipped as prose or placeholders: %d (listed in --json)" % len(result["skipped_cells"]))
    out.append("em-dash density per 1,000 words of prose:")
    for r in result["files"]:
        e = r["emdash"]
        left_out = "%d reference rows" % e["reference_rows_excluded"]
        if e["empty_cells_excluded"]:
            left_out += ", %d empty table cells" % e["empty_cells_excluded"]
        out.append("  %s: %s (%d em-dashes in %d words; %s left out)"
                   % (r["file"], e["per_1000"], e["count"], e["words"], left_out))
    return "\n".join(out)


def default_guides_dir():
    return os.path.expanduser("~/.wiki/personal/writing")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(__doc__)
        return 0
    as_json, guides_dir = False, None
    if "--json" in args:
        args.remove("--json")
        as_json = True
    for a in list(args):
        if a.startswith("--guides="):
            guides_dir = a.split("=", 1)[1]
            args.remove(a)
    if "--guides" in args:
        i = args.index("--guides")
        if i + 1 >= len(args):
            print("writing-lint: usage error: --guides needs a directory", file=sys.stderr)
            return 2
        guides_dir = args[i + 1]
        del args[i:i + 2]
    unknown = [a for a in args if a.startswith("--")]
    if unknown or not args:
        print("writing-lint: usage error: %s\nusage: writing-lint.py [--guides DIR] [--json] FILE [FILE ...]"
              % ("unknown option " + unknown[0] if unknown else "no input file"), file=sys.stderr)
        return 2
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        result = lint(args, guides_dir or default_guides_dir())
    except GuideError as e:
        print("writing-lint: cannot run: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False) if as_json else render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
