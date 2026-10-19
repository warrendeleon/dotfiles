#!/usr/bin/env python3
"""Check that an edit kept every protected value of a document.

    content-inventory.py extract FILE [--json]
    content-inventory.py check ORIGINAL EDITED [--json]
    content-inventory.py removed ORIGINAL EDITED

removed lists every prose sentence of the original that the edit cut or changed, each with what
now stands in its place, for a reader to find where its content lives in the edit. Code, tables,
charts and styles are left to check.

The tightening pass in the revision guide (~/.wiki/personal/writing/revision-passes.md,
"Tighten without losing content") lets an editor cut length on its own judgement as long as
nothing the document carries is lost. Claims, reasons and caveats need a reader to check. The
values this script checks must survive byte for byte, so a mechanical comparison settles them:

    code         fenced, indented and <pre> code blocks, compared by content without the
                 indentation of the container, with the fence's info string
    inline-code  every `inline code` span, including spans that wrap a line
    link         every link target, exactly as written: inline and reference-style Markdown
                 links and images, [[wiki links]], <autolinks>, href and src attributes, and
                 bare URLs (trailing sentence punctuation removed from bare URLs only)
    number       every number in the prose and in the title and description: signed values,
                 decimals, percentages, ranges, dates, times and versions, outside code, URLs,
                 footnote labels and the markers of ordered lists
    footnote     every footnote the body references, by its text, so renumbering passes and a
                 footnote cut from its claim does not
    data-row     every table row, Markdown or HTML, whose cells are mostly values (numbers,
                 dates, versions, percentages, inline code, yes/no marks): raw data stays whole
    chart        every <svg> block, every data-* attribute value and every JSON data block
                 (<script type="application/json">), byte for byte
    frontmatter  the publishing fields an edit must not touch (tags, publishDate, slug,
                 campaign, series, heroImage, heroAlt, locale, draft, relatedPosts), compared in
                 both directions so an added field counts too

A value counts as kept when the edited file still contains it anywhere. That is a backstop,
not proof that every claim survived: two values swapped between their labels still pass, and
claims, qualifiers and reasons have no mechanical check. The fresh reader in the edit-doc
workflow owns those.

Exit 0 when every value is kept, 1 when any is missing (each one is printed), 2 when the
script cannot run (a file is missing or unreadable).
"""
import difflib
import html as htmllib
import json
import re
import sys

HANDS_OFF = ("tags", "publishDate", "slug", "campaign", "series", "heroImage", "heroAlt",
             "locale", "draft", "relatedPosts")
CONTENT_FIELDS = ("title", "description")

FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`]*?)\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
INLINE = re.compile(r"(`+)(?!`)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", re.S)
MD_LINK = re.compile(r"!?\[((?:[^\[\]\n]|\[[^\]\n]*\])*)\]\(\s*(?:<([^>\n]+)>|((?:[^()\s]|\([^()\s]*\))+))"
                     r"(?:\s+(?:\"[^\"\n]*\"|'[^'\n]*'))?\s*\)")
REF_DEF = re.compile(r"^ {0,3}\[(?!\^)[^\]\n]+\]:[ \t]*<?([^\s>]+)>?", re.M)
WIKILINK = re.compile(r"\[\[([^\]|#\n]+)(?:#[^\]|\n]*)?(?:\|([^\]\n]*))?\]\]")
AUTOLINK = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
HTML_ATTR = re.compile(r"""(?i)\b(?:href|src)\s*=\s*["']([^"']+)["']""")
BARE_URL = re.compile(r"https?://[^\s<>\"'`\]]+")
PRE = re.compile(r"(?is)<pre\b[^>]*>(.*?)</pre\s*>")
SCRIPT_STYLE = re.compile(r"(?is)<(script|style)\b.*?</\1\s*>")
TAG = re.compile(r"</?[A-Za-z][^>\n]*>")
FOOT_DEF = re.compile(r"^\[\^([^\]\n]+)\]:[ \t]*(.*)$", re.M)
FOOT_REF = re.compile(r"\[\^([^\]\n]+)\](?!:)")
LIST_MARKER = re.compile(r"^(\s*)\d+[.)](?=\s)", re.M)
NUMBER = re.compile(r"(?<![\w.,:/])v?-?\d+(?:[.,:/\-]\d+)*%?(?![\w])")
SENTENCE_END = ".,;:!?'\"»”’"
SVG = re.compile(r"(?is)<svg\b.*?</svg\s*>")
DATA_ATTR = re.compile(r"""(?i)\bdata-[\w-]+\s*=\s*(?:"([^"]*)"|'([^']*)')""")
JSON_SCRIPT = re.compile(r"""(?is)<script\b[^>]*type\s*=\s*["']application/(?:ld\+)?json["'][^>]*>(.*?)</script\s*>""")
HTML_ROW = re.compile(r"(?is)<tr\b[^>]*>(.*?)</tr\s*>")
HTML_CELL = re.compile(r"(?is)<t[dh]\b[^>]*>(.*?)</t[dh]\s*>")
MD_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
VALUE_CELL = re.compile(r"[\s~≈<>±+−–—-]*(?:v?-?\d+(?:[.,:/\-]\d+)*%?\s*[A-Za-zµ°%/]{0,6}\.?[\s,;–—-]*)+")
MARKS = {"", "—", "–", "-", "n/a", "N/A", "yes", "no", "Yes", "No", "✓", "✗", "✔", "✖", "x", "X", "true", "false"}


class InventoryError(Exception):
    pass


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise InventoryError(f"cannot read {path}: {e.strerror or e}")


def is_html(path):
    return path.lower().endswith((".html", ".htm"))


# ---------------------------------------------------------------- frontmatter

def split_frontmatter(text):
    """Return (frontmatter lines, body, number of lines the frontmatter used)."""
    if not text.startswith("---\n"):
        return [], text, 0
    end = text.find("\n---", 4)
    if end == -1:
        return [], text, 0
    block = text[4:end]
    rest = text[end + 4:]
    nl = rest.find("\n")
    body = rest[nl + 1:] if nl != -1 else ""
    return block.split("\n"), body, block.count("\n") + 2


KEY = re.compile(r"""^["']?([A-Za-z][\w-]*)["']?\s*:""")


def frontmatter_fields(lines):
    """The raw text of every top-level key, with its indented, list and comment lines."""
    fields, key = {}, None
    for line in lines:
        m = KEY.match(line)
        if m:
            key = m.group(1)
            fields[key] = [line.rstrip()]
        elif key and (line.startswith((" ", "\t", "-", "#")) or not line.strip()):
            fields[key].append(line.rstrip())
        else:
            key = None
    return {k: "\n".join(v).strip() for k, v in fields.items()}


def field_value(raw):
    return raw.split(":", 1)[1].strip().strip("\"'") if ":" in raw else ""


# ---------------------------------------------------------------- body

def blank_span(text, start, end):
    """Replace text[start:end] with spaces, keeping its line breaks so line numbers hold."""
    return text[:start] + re.sub(r"[^\n]", " ", text[start:end]) + text[end:]


def dedent(lines, n):
    out = []
    for line in lines:
        k = 0
        while k < n and k < len(line) and line[k] == " ":
            k += 1
        out.append(line[k:])
    return out


def code_blocks(body):
    """Pull fenced and indented code out of the body: (items, body with code blanked)."""
    lines = body.split("\n")
    items, out = [], []
    i, last_text = 0, ""
    while i < len(lines):
        line = lines[i]
        m = FENCE.match(line)
        if m:
            indent, marker, info = len(m.group(1).expandtabs(4)), m.group(2), m.group(3)
            close = re.compile(r"^\s*" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*$")
            start, content = i, []
            i += 1
            while i < len(lines) and not close.match(lines[i]):
                content.append(lines[i])
                i += 1
            items.append({"kind": "code", "value": info + "\n" + "\n".join(dedent(content, indent)), "line": start + 1})
            out += [""] * (i - start + (1 if i < len(lines) else 0))
            i += 1
            last_text = ""
            continue
        prev_blank = i > 0 and not lines[i - 1].strip()
        indented = re.match(r"^( {4,}|\t)\S", line)
        if indented and (prev_blank or i == 0) and not LIST_ITEM.match(last_text) and not re.match(r"^\s", last_text):
            start, block = i, []
            while i < len(lines) and (re.match(r"^( {4,}|\t)", lines[i]) or not lines[i].strip()):
                block.append(lines[i])
                i += 1
            while block and not block[-1].strip():
                block.pop()
                i -= 1
            items.append({"kind": "code", "value": "\n" + "\n".join(dedent([b.expandtabs(4) for b in block], 4)), "line": start + 1})
            out += [""] * (i - start)
            continue
        out.append(line)
        if line.strip():
            last_text = line
        i += 1
    return items, "\n".join(out)


def cell_is_value(cell):
    c = re.sub(r"[*_]", "", cell).strip()
    if c.startswith("`") and c.endswith("`") and len(c) > 1:
        return True
    return c in MARKS or VALUE_CELL.fullmatch(c) is not None


def data_row(cells):
    """A row whose non-empty cells are mostly values, normalised to "a | b | c"; else None."""
    cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
    filled = [c for c in cells if c]
    if len(filled) < 2:
        return None
    values = sum(1 for c in filled if cell_is_value(c))
    return " | ".join(cells) if values * 2 >= len(filled) else None


def md_rows(prose):
    """Markdown table rows, skipping header and separator rows: (line index, cells)."""
    lines, rows = prose.split("\n"), []
    for i, line in enumerate(lines):
        if "|" not in line or MD_SEPARATOR.match(line):
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        prev = lines[i - 1] if i > 0 else ""
        if MD_SEPARATOR.match(nxt):
            continue                      # a header row
        if "|" not in prev and not MD_SEPARATOR.match(prev):
            continue                      # a stray pipe in prose, not a table row
        body = line.strip()
        if body.startswith("|"):
            body = body[1:]
        if body.endswith("|"):
            body = body[:-1]
        rows.append((i, [c for c in re.split(r"(?<!\\)\|", body)]))
    return rows


def line_of(text, pos, offset):
    return text.count("\n", 0, pos) + 1 + offset


def extract(text, html=False):
    """Every protected value in a document, as dicts with kind, value and line."""
    items = []
    fm_lines, body, offset = split_frontmatter(text)
    fields = frontmatter_fields(fm_lines)
    for key in HANDS_OFF:
        if key in fields:
            items.append({"kind": "frontmatter", "value": fields[key], "line": 1, "key": key})
    for key in CONTENT_FIELDS:
        if key in fields:
            for m in NUMBER.finditer(field_value(fields[key])):
                items.append({"kind": "number", "value": m.group(0), "line": 1})

    code, prose = code_blocks(body)
    for it in code:
        it["line"] += offset
    items += code
    for m in JSON_SCRIPT.finditer(prose):
        items.append({"kind": "chart", "value": m.group(1).strip(), "line": line_of(prose, m.start(), offset)})
    for m in SVG.finditer(prose):
        items.append({"kind": "chart", "value": m.group(0), "line": line_of(prose, m.start(), offset)})
    for m in DATA_ATTR.finditer(prose):
        items.append({"kind": "chart", "value": m.group(1) if m.group(1) is not None else m.group(2), "line": line_of(prose, m.start(), offset)})
    for m in HTML_ROW.finditer(prose):
        row = data_row([TAG.sub("", c) for c in HTML_CELL.findall(m.group(1))])
        if row:
            items.append({"kind": "data-row", "value": row, "line": line_of(prose, m.start(), offset)})
    prose = SVG.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)
    prose = SCRIPT_STYLE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)
    for m in list(PRE.finditer(prose)):
        content = TAG.sub("", m.group(1))
        items.append({"kind": "code", "value": "\n" + content.strip("\n"), "line": line_of(prose, m.start(), offset)})
    prose = PRE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)

    for i, cells in md_rows(prose):
        row = data_row(cells)
        if row:
            items.append({"kind": "data-row", "value": row, "line": i + 1 + offset})
    for m in INLINE.finditer(prose):
        items.append({"kind": "inline-code", "value": m.group(2).replace("\n", " ").strip(), "line": line_of(prose, m.start(), offset)})
    prose = INLINE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)

    defs = {m.group(1): m.group(2).strip() for m in FOOT_DEF.finditer(prose)}
    refs = {m.group(1) for m in FOOT_REF.finditer(FOOT_DEF.sub("", prose))}
    for label, body_text in defs.items():
        if label in refs:
            items.append({"kind": "footnote", "value": body_text, "line": 1})

    def link(value, pos):
        items.append({"kind": "link", "value": value, "line": line_of(prose, pos, offset)})

    for m in REF_DEF.finditer(prose):
        link(m.group(1), m.start())
    prose = REF_DEF.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)
    for m in HTML_ATTR.finditer(prose):
        link(m.group(1), m.start())
    for m in MD_LINK.finditer(prose):
        link(m.group(2) or m.group(3), m.start())
    prose = MD_LINK.sub(lambda m: " " + m.group(1) + " " * (len(m.group(0)) - len(m.group(1)) - 1), prose)
    for m in WIKILINK.finditer(prose):
        link(m.group(1).strip(), m.start())
    prose = WIKILINK.sub(lambda m: " " + (m.group(2) or "") + " " * max(0, len(m.group(0)) - len(m.group(2) or "") - 1), prose)
    for m in AUTOLINK.finditer(prose):
        link(m.group(1), m.start())
    prose = AUTOLINK.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)
    for m in BARE_URL.finditer(prose):
        url = m.group(0).rstrip(SENTENCE_END)
        while url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1]
        link(url, m.start())
    prose = BARE_URL.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), prose)

    prose = TAG.sub(lambda m: " " * len(m.group(0)), prose)
    prose = FOOT_REF.sub(lambda m: " " * len(m.group(0)), prose)
    prose = FOOT_DEF.sub(lambda m: " " * (len(m.group(0)) - len(m.group(2))) + m.group(2), prose)
    prose = LIST_MARKER.sub(lambda m: m.group(1) + " " * (len(m.group(0)) - len(m.group(1))), prose)
    for m in NUMBER.finditer(prose):
        items.append({"kind": "number", "value": m.group(0), "line": line_of(prose, m.start(), offset)})
    return items


# ---------------------------------------------------------------- check

def values(items, kind):
    return {it["value"] for it in items if it["kind"] == kind}


def check(original_text, edited_text, html=False):
    """Values of the original that the edited text no longer carries."""
    before = extract(original_text, html)
    after = extract(edited_text, html)
    code_after = values(after, "code")
    code_blob = "\n".join(code_after)
    inline_after = values(after, "inline-code")
    links_after = values(after, "link")
    numbers_after = values(after, "number")
    notes_after = values(after, "footnote")
    rows_after = values(after, "data-row")
    charts_after = values(after, "chart")
    fm_before = {it["key"]: it["value"] for it in before if it["kind"] == "frontmatter"}
    fm_after = {it["key"]: it["value"] for it in after if it["kind"] == "frontmatter"}
    missing, seen = [], set()

    def add(it):
        sig = (it["kind"], it["value"], it.get("key"))
        if sig not in seen:
            seen.add(sig)
            missing.append(it)

    for it in before:
        k, v = it["kind"], it["value"]
        if k == "frontmatter":
            kept = fm_after.get(it["key"]) == v
        elif k == "code":
            kept = v in code_after
        elif k == "inline-code":
            kept = v in inline_after or re.search(r"(?<![\w-])" + re.escape(v) + r"(?![\w-])", code_blob) is not None
        elif k == "link":
            kept = v in links_after
        elif k == "footnote":
            kept = v in notes_after
        elif k == "data-row":
            kept = v in rows_after
        elif k == "chart":
            kept = v in charts_after
        else:
            kept = v in numbers_after
        if not kept:
            add(it)
    for key, v in fm_after.items():
        if key not in fm_before:
            add({"kind": "frontmatter", "value": f"{key} added: {v}", "line": 1, "key": key})
    # An original that writes each paragraph on one line loses a paragraph break when an edit
    # runs two of them together (a lost blank line renders them as one paragraph).
    if not html and not joined_lines(original_text):
        for n, line in joined_lines(edited_text):
            add({"kind": "paragraph-break", "value": f"no blank line before: {line[:70]}", "line": n})
    return before, missing


def joined_lines(text):
    """Prose lines that follow another prose line with no blank line between them, as (line, text).

    Code fences, frontmatter, headings, tables, quotes, HTML, list items and indented lines are
    not prose here, so only two plain paragraphs run together count."""
    joined, prev, fence = [], False, None
    lines = text.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        start = end + 1 if end is not None else 0
    for i in range(start, len(lines)):
        line = lines[i]
        m = re.match(r"\s*(`{3,}|~{3,})", line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            prev = False
            continue
        if m:
            fence, prev = m.group(1), False
            continue
        prose = bool(line.strip()) and not re.match(r"(\s|#|\||>|<|[-*+]\s|\d{1,3}[.)]\s)", line)
        if prose and prev:
            joined.append((i + 1, line))
        prev = prose
    return joined


def prose_sentences(text, html=False):
    """The prose of a document as sentences, without code, tables, charts or frontmatter."""
    if html:
        text = re.sub(r"(?is)<(script|style|svg|table|pre)\b.*?</\1>", " ", text)
        text = re.sub(r"(?i)<(br|/p|/li|/h\d|/div|/td|/th|/dd|/dt|/caption|/figcaption)\b[^>]*>", "\n", text)
        text = htmllib.unescape(re.sub(r"<[^>]+>", "", text))
    else:
        text = split_frontmatter(text)[1] if text.startswith("---") else text
        text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "\n", text)
        text = "\n".join("" if re.match(r"\s*\|", l) else l for l in text.split("\n"))
        text = re.sub(r"\n(?![ \t]*(\n|[-*+] |\d{1,3}[.)] |#|>))", " ", text)
    out = []
    for para in text.split("\n"):
        para = " ".join(para.split())
        if para:
            out += re.split(r"(?<=[.!?:])\s+(?=[A-Z(\u201c\"'`])", para)
    return out


def removed(original_text, edited_text, html=False):
    """(cut or changed sentences of the original, what stands in their place) pairs."""
    a, b = prose_sentences(original_text, html), prose_sentences(edited_text, html)
    pairs = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            pairs.append((a[i1:i2], b[j1:j2]))
    return pairs


# ---------------------------------------------------------------- cli

def summarise(items):
    counts = {}
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    return counts


def show(value):
    one = value.replace("\n", "⏎")
    return one if len(one) <= 80 else one[:77] + "..."


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    try:
        if len(argv) == 2 and argv[0] == "extract":
            path = argv[1]
            items = extract(read(path), is_html(path))
            if as_json:
                print(json.dumps({"file": path, "items": items, "counts": summarise(items)}, ensure_ascii=False))
            else:
                for it in items:
                    print(f"{path}:{it['line']}: {it['kind']}: {show(it['value'])}")
                print(f"{len(items)} item(s): {json.dumps(summarise(items))}")
            return 0
        if len(argv) == 3 and argv[0] == "removed":
            orig, edited = argv[1], argv[2]
            pairs = removed(read(orig), read(edited), is_html(orig))
            for n, (cut, now) in enumerate(pairs, 1):
                print(f"## {n}")
                for s in cut:
                    print(f"  - {s}")
                for s in now:
                    print(f"  + {s}")
            print(f"{len(pairs)} passage(s) cut or changed")
            return 0
        if len(argv) == 3 and argv[0] == "check":
            orig, edited = argv[1], argv[2]
            before, missing = check(read(orig), read(edited), is_html(orig))
            if as_json:
                print(json.dumps({"original": orig, "edited": edited, "total": len(before),
                                  "missing": missing, "counts": summarise(before)}, ensure_ascii=False))
            else:
                for it in missing:
                    print(f"MISSING {orig}:{it['line']}: {it['kind']}: {show(it['value'])}")
                print(f"{len(before)} value(s) checked; {len(missing)} distinct value(s) missing")
            return 1 if missing else 0
    except InventoryError as e:
        print(f"content-inventory: {e}", file=sys.stderr)
        return 2
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
