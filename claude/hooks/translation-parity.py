#!/usr/bin/env python3
"""Structural and executable parity between an English blog article and one translation.

Usage: translation-parity.py <en.md> <locale.md>
Exit 0 when every class matches; 1 otherwise. Prints one line per class.
Translated comments are reported separately and never fail the run. A numbers diff lists the
exact counters, so a number written out in words (post 15: "un segundo y medio") can be judged.
Broken deliberately on 3 Oct 2026 with eight negative controls (a heading removed, an executable
token changed, a version swapped, a link changed, a translated comment changed, a paragraph
removed, a Mermaid edge removed, a bold removed): each failed in its own class and the comment
change failed none.
4 Oct 2026 (post 17): a comment trailing a shell command now counts as a comment; Mermaid labels of
every node shape are dropped and every arrow type splits an edge, so every node id and edge is
compared (a filter used to drop all lowercase ids); "32-byte" counts like "32 bytes". Broken again
with five controls (a node id renamed, an edge removed, the command before a trailing comment
changed, a hyphen-joined number changed, an ==> edge retargeted): each failed in its own class.
"""
import re
import sys
from collections import Counter

EN_ONLY = {'publishDate', 'draft', 'heroImgPrompt', 'heroPalette', 'heroBgColor', 'companionTag'}
TRANSLATED = {'title', 'description', 'heroAlt', 'locale', 'status'}


def split(text):
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    return m.group(1), m.group(2)


def frontmatter(fm):
    out = {}
    for line in fm.splitlines():
        if line.startswith('#') or not line.strip():
            continue
        k, _, v = line.partition(':')
        out[k.strip()] = v.strip()
    return out


def blocks(body):
    """Yield ('fence', lang, lines) and ('prose', line) in order."""
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.startswith('```'):
            lang = l[3:].strip()
            j = i + 1
            while j < len(lines) and not lines[j].startswith('```'):
                j += 1
            yield ('fence', lang, lines[i + 1:j])
            i = j + 1
        else:
            yield ('prose', l, None)
            i += 1


def strip_comments(lang, lines):
    code, comments = [], []
    in_block = False
    for l in lines:
        s = l.strip()
        if lang == 'mermaid':
            code.append(l)
            continue
        if lang in ('sh', ''):
            if s.startswith('#!'):
                code.append(l)
            elif s.startswith('#'):
                comments.append(l)
            else:
                # A comment after the command, set off by two spaces (post 17:
                # `sign-version-map.mjs ios 2.0.0   # or the next number`), translates like a
                # comment on its own line; the command before it stays executable.
                m = re.match(r'^(.*?\S)\s{2,}(#\s.*)$', l)
                if m and lang == 'sh':
                    code.append(m.group(1))
                    comments.append(m.group(2))
                else:
                    code.append(l)
            continue
        # js / ts / groovy / tsx
        if in_block:
            comments.append(l)
            if '*/' in s:
                in_block = False
            continue
        if s.startswith('/**') or s.startswith('/*'):
            comments.append(l)
            if '*/' not in s:
                in_block = True
            continue
        if s.startswith('//'):
            comments.append(l)
            continue
        if s.startswith('{/*'):
            comments.append(l)
            if '*/}' not in s:
                in_block = True
            continue
        code.append(l)
    return code, comments


def mermaid_structure(lines):
    """Node ids, edge pairs and edge count; labels are the translated part."""
    ids, edges = set(), []
    for l in lines:
        s = l.strip()
        if not s or s.startswith('flowchart') or s.startswith('sequenceDiagram') or s.startswith('%%'):
            continue
        # drop labels: ["..."], (["..."]), [("...")], (("...")), ("..."), {"..."} and |edge labels|
        bare = re.sub(r'\(\["[^"]*"\]\)|\[\("[^"]*"\)\]|\(\("[^"]*"\)\)|\("[^"]*"\)|\["[^"]*"\]|\{"[^"]*"\}'
                      r'|\|"[^"]*"\||\|[^|]*\|', '', s)
        bare = re.sub(r'--\s*[^-\s][^-]*?\s*-->', '-->', bare)
        # every arrow: -->, -.->, ==>, <-->, ---
        parts = re.split(r'\s*<?(?:-\.+-|-{2,}|={2,})>?\s*', bare)
        parts = [p.strip() for p in parts if p.strip()]
        # Edge labels ("-- yes -->", |label|) are already gone, so every remaining part is a node id,
        # a "subgraph id" line or the "end" keyword. Until 4 Oct 2026 a filter dropped every
        # lowercase word here, which hid most node ids (fetch, refuse, store) from the comparison.
        parts = [p for p in parts if p not in ('end', 'direction TD', 'direction LR')]
        for p in parts:
            ids.add(p)
        if len(parts) >= 2:
            for a, b in zip(parts, parts[1:]):
                edges.append((a, b))
    return ids, edges


def analyse(text):
    fm, body = split(text)
    r = {'fm': frontmatter(fm)}
    fences, code_tokens, comments, mermaid, code_langs = [], [], [], [], []
    prose = []
    for b in blocks(body):
        if b[0] == 'fence':
            lang, lines = b[1], b[2]
            fences.append(lang)
            if lang == 'mermaid':
                mermaid.append(mermaid_structure(lines))
            else:
                c, k = strip_comments(lang, lines)
                code_langs.append(lang)
                code_tokens.append('\n'.join(x.rstrip() for x in c))
                comments.append(k)
        else:
            prose.append(b[1])
    r['headings'] = [l for l in prose if re.match(r'^#{1,6} ', l)]
    r['heading_levels'] = [len(h.split(' ')[0]) for h in r['headings']]
    r['fences'] = fences
    r['code'] = code_tokens
    # the language of each non-Mermaid fence, so a report names the fence it indexes
    r['code_langs'] = code_langs
    r['comments'] = comments
    r['mermaid'] = mermaid
    ptext = '\n'.join(prose)
    # paragraphs: blank-line separated runs of prose that are not headings, tables, html or list items
    paras = [p for p in re.split(r'\n\s*\n', ptext) if p.strip()]
    r['paragraphs'] = [p for p in paras if not re.match(r'^(#{1,6} |\||<|- |\d+\. )', p.strip())]
    r['list_items'] = [l for l in prose if re.match(r'^(- |\d+\. )', l)]
    r['table_rows'] = [l for l in prose if l.startswith('|')]
    r['links'] = re.findall(r'\]\(([^)]+)\)', ptext)
    r['images'] = re.findall(r'src="([^"]+)"', ptext)
    r['alts'] = re.findall(r'alt="([^"]*)"', ptext)
    r['bold'] = len(re.findall(r'\*\*[^*]+\*\*', ptext))
    r['italic'] = len(re.findall(r'(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)', ptext))
    r['callouts'] = re.findall(r'class="callout ([a-z-]+)"', ptext)
    r['codespans'] = re.findall(r'`([^`\n]+)`', ptext)
    # "32-byte" counts like "32 bytes"; "1-2" and "post-02" still do not split into numbers.
    nums = re.findall(r'(?<![\w./-])\d+(?:\.\d+)*(?!\w)(?!-\d)', ptext)
    r['numbers'] = Counter(nums)
    r['emdash'] = sum(1 for l in prose if '—' in l and not l.startswith('- ['))
    return r


def main():
    en = analyse(open(sys.argv[1], encoding='utf8').read())
    tr = analyse(open(sys.argv[2], encoding='utf8').read())
    ok = True

    def check(name, a, b, detail=None):
        nonlocal ok
        same = a == b
        ok = ok and same
        print(f"{'OK ' if same else 'FAIL'} {name}: en={a if not isinstance(a, list) or len(a) < 4 else len(a)} tr={b if not isinstance(b, list) or len(b) < 4 else len(b)}")
        if not same and detail:
            detail()

    check('frontmatter shared fields', {k: v for k, v in en['fm'].items() if k not in EN_ONLY | TRANSLATED},
          {k: v for k, v in tr['fm'].items() if k not in EN_ONLY | TRANSLATED},
          lambda: print('   en', {k: v for k, v in en['fm'].items() if k not in EN_ONLY | TRANSLATED}, '\n   tr', {k: v for k, v in tr['fm'].items() if k not in EN_ONLY | TRANSLATED}))
    check('en-only fields absent in locale', set(), set(tr['fm']) & EN_ONLY)
    check('translated fields present', TRANSLATED - {'locale', 'status'} <= set(tr['fm']), True)
    check('heading count', len(en['headings']), len(tr['headings']))
    check('heading levels', en['heading_levels'], tr['heading_levels'])
    check('paragraph count', len(en['paragraphs']), len(tr['paragraphs']),
          lambda: [print('   en:', p[:70]) for p in en['paragraphs']] if abs(len(en['paragraphs']) - len(tr['paragraphs'])) > 3 else None)
    check('list items', len(en['list_items']), len(tr['list_items']))
    check('table rows', len(en['table_rows']), len(tr['table_rows']))
    check('fence count and langs', en['fences'], tr['fences'])
    for i, (a, b) in enumerate(zip(en['code'], tr['code'])):
        if a != b:
            ok = False
            print(f'FAIL executable tokens differ in fence #{i + 1} ({en["code_langs"][i]})')
            al, bl = a.splitlines(), b.splitlines()
            for j, (x, y) in enumerate(zip(al, bl)):
                if x != y:
                    print(f'   line {j + 1}\n   en: {x}\n   tr: {y}')
                    break
            if len(al) != len(bl):
                print(f'   line counts en={len(al)} tr={len(bl)}')
    else:
        print(f'OK  executable tokens in {len(en["code"])} non-mermaid fences')
    changed = sum(1 for a, b in zip(en['comments'], tr['comments']) if a != b)
    same_len = all(len(a) == len(b) for a, b in zip(en['comments'], tr['comments']))
    print(f'INFO translated comments: {changed} fences differ in comment text; comment line counts {"match" if same_len else "DIFFER"}')
    if not same_len:
        for i, (a, b) in enumerate(zip(en['comments'], tr['comments'])):
            if len(a) != len(b):
                print(f'   fence #{i + 1} ({en["code_langs"][i]}): comment lines en={len(a)} tr={len(b)} (reflow is fine)')
    check('mermaid diagrams', len(en['mermaid']), len(tr['mermaid']))
    for i, (a, b) in enumerate(zip(en['mermaid'], tr['mermaid'])):
        check(f'mermaid #{i + 1} node ids', a[0], b[0], lambda: print('   en-tr', a[0] - b[0], 'tr-en', b[0] - a[0]))
        check(f'mermaid #{i + 1} edges', a[1], b[1])
    check('link destinations', en['links'], tr['links'],
          lambda: print('   en-tr', [l for l in en['links'] if l not in tr['links']], '\n   tr-en', [l for l in tr['links'] if l not in en['links']]))
    check('image paths', en['images'], tr['images'])
    check('alt count', len(en['alts']), len(tr['alts']))
    check('callouts', en['callouts'], tr['callouts'])
    check('bold count', en['bold'], tr['bold'])
    check('italic count', en['italic'], tr['italic'])
    check('code spans', Counter(en['codespans']), Counter(tr['codespans']),
          lambda: print('   en-tr', Counter(en['codespans']) - Counter(tr['codespans']), '\n   tr-en', Counter(tr['codespans']) - Counter(en['codespans'])))
    check('numbers (order-insensitive)', en['numbers'], tr['numbers'],
          lambda: print('   en-tr', en['numbers'] - tr['numbers'], '\n   tr-en', tr['numbers'] - en['numbers']))
    print(f'INFO prose em-dash lines: en={en["emdash"]} tr={tr["emdash"]}')
    print('RESULT', 'OK' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
