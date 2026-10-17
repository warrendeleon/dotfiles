#!/usr/bin/env python3
"""Tests for writing-lint.py. Run: python3 claude/hooks/writing-lint.test.py

The guides under test are small fixture files written to a temporary directory, never the
live wiki. One smoke test reads the live guides and is skipped when they are absent.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "writing-lint.py")
LIVE = os.path.expanduser("~/.wiki/personal/writing")

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("writing_lint", HOOK)
wl = importlib.util.module_from_spec(spec)
sys.modules["writing_lint"] = wl
spec.loader.exec_module(wl)

GOTCHAS = """---
title: "Fixture avoid list"
---

# Fixture avoid list

## Key Points

| Name | Link |
|---|---|
| a table the lint does not know | skipped and reported |

### Constructions

| Banned | Replacement | Why |
|---|---|---|
| "It's not X, but Y" (e.g. "A Rolex is not just made — it is engineered.") | State the positive | tell |

### Expressions

| Overused | Replacement | Why |
|---|---|---|
| In order to | to | house |
| Cutting-edge | latest | house |
| A testament to... | proof of | tell |
| Mission-critical | necessary | house |

### Marketing compounds (added during audit)

| Banned | Replacement | Why |
|---|---|---|
| mission-critical | say what fails without it | house |

### Words

| Overused | Replacement | Why |
|---|---|---|
| Key (as an adjective) | main | tell |
| Intricate, intricacies | complex | tell |
| Leverage | use | tell (provisional) |
| Emphasise | stress | tell |

### Era vocabulary

| Era | Words |
|---|---|
| 2023 on | delve/dig, vibrant, plus the coverage phrases in the other table |
| Mid 2024 | showcasing, plus a long run of explanatory words that is prose and not a term at all |

### Stock phrases

| Phrase | Replacement | Rule owner |
|---|---|---|
| plays a key / pivotal / vital role in | what it does | [[accuracy]] |
| ..., highlighting / underscoring X (a closing clause) | cut the clause | [[plain]] |
| Despite its ..., X faces challenges; Despite these challenges | state the limit | [[skim]] |
| Certainly or Of course | delete | [[uk]] |

### Punctuation

| Banned | Replacement | Why |
|---|---|---|
| Em-dash (—) anywhere in prose | Colon, comma or full stop | tell |

### Another avoid list

| Avoid | Instead |
|---|---|
| out of the box | ready-made |

```text
| Banned | Replacement |
|---|---|
| fenced | never read |
```
"""

REVISION = r"""---
title: "Fixture revision passes"
---

# Revision passes

## Key Points

- A decoy: `grep -nE 'decoy' FILE` outside the leftovers section is never read.

### Leftovers search

Run on the final artefact.

```bash
grep -nE '\[(Your|Insert|Link)[^]]*\]|INSERT_|[[:digit:]]{4}-(xx|XX)|utm_source=|[Aa]s an AI|\<TODO\>' FILE
```

A hit is a pointer, not a finding: read it in context.

### Another section

```bash
grep -nE 'decoy' FILE
```
"""


def table_guide(rows, header="| Overused | Replacement | Why |"):
    """A one-table avoid list: rows are (term, replacement, tag)."""
    body = "\n".join("| %s | %s | %s |" % r for r in rows)
    return "### Fixture\n\n%s\n|---|---|---|\n%s\n" % (header, body)


def terms_of(cell):
    terms, skipped = wl.terms_from_cell(cell)
    return [t["text"] for t in terms], skipped


def hits_for(text, rows):
    guide = wl.parse_gotchas(table_guide(rows))
    return wl.find_term_hits(wl.Doc(text), guide["terms"])


class ParseCells(unittest.TestCase):
    def test_separators_split_cells(self):
        cases = [
            ("Intricate, intricacies", ["Intricate", "intricacies"]),
            ("delve/dig; vibrant", ["delve", "dig", "vibrant"]),
            ("Alternatively or instead", ["Alternatively", "instead"]),
            ("a b, c d; e f", ["a b, c d", "e f"]),
            ("Hustle and bustle", ["Hustle and bustle"]),
            ("Core competency", ["Core competency"]),
        ]
        for cell, want in cases:
            with self.subTest(cell=cell):
                self.assertEqual(terms_of(cell)[0], want)

    def test_slash_alternatives_share_the_surrounding_words(self):
        self.assertEqual(terms_of("plays a key / pivotal / vital role in")[0],
                         ["plays a key role in", "plays a pivotal role in", "plays a vital role in"])

    def test_ellipses_and_placeholders(self):
        cases = [
            ("A testament to...", ["A testament to"]),
            ("..., highlighting / underscoring X (a closing clause)", ["highlighting", "underscoring"]),
            ("Would you like..., let me know", ["Would you like", "let me know"]),
            ("Despite its ..., X faces challenges", ["Despite its ..., ... faces challenges"]),
            ("X", []),
            ("...", []),
            ("should be treated as X rather than Y", ["should be treated as ... rather than"]),
        ]
        for cell, want in cases:
            with self.subTest(cell=cell):
                got, skipped = terms_of(cell)
                self.assertEqual(got, want)
                self.assertEqual(skipped, [], "placeholders are dropped, not reported as prose")

    def test_semicolon_outranks_comma_so_a_pattern_keeps_its_comma(self):
        got, _ = terms_of("Despite its ..., X faces challenges; Despite these challenges")
        self.assertEqual(got, ["Despite its ..., ... faces challenges", "Despite these challenges"])

    def test_quotes_backticks_bold_and_glosses_are_stripped(self):
        cases = [
            ('"It\'s not X, but Y" (e.g. "A Rolex is not just made — it is engineered.")',
             ["It's not ..., but"]),
            ("`code term`", ["code term"]),
            ('"quoted"', ["quoted"]),
            ("**bold**", ["bold"]),
            ("Key (as an adjective)", ["Key"]),
            ('Boasts (meaning "has")', ["Boasts"]),
            ('Matters ("why this matters")', ["Matters"]),
            ("several sources (for one or two), such as (before a complete list)",
             ["several sources", "such as"]),
            ("rich (heritage, history), profound", ["rich", "profound"]),
        ]
        for cell, want in cases:
            with self.subTest(cell=cell):
                self.assertEqual(terms_of(cell)[0], want)

    def test_symbol_in_parentheses_is_the_term(self):
        terms, _ = wl.terms_from_cell("Em-dash (—) anywhere in prose")
        self.assertEqual([(t["text"], t["symbol"]) for t in terms], [("—", True)])

    def test_prose_cells_are_skipped_and_reported(self):
        cases = [
            "plus the coverage and attribution phrases in the stock-phrase table",
            "with shorter sentences of 8 to 20 words and heavier use of commas and full stops",
            "see the judgement clause",
            "e.g. a long explanation",
            "one two three four five six seven eight nine",
        ]
        for cell in cases:
            with self.subTest(cell=cell):
                got, skipped = terms_of(cell)
                self.assertEqual(got, [])
                self.assertEqual(len(skipped), 1)
                self.assertTrue(skipped[0]["reason"].startswith("prose"))

    def test_eight_words_is_still_a_term_and_nine_is_prose(self):
        self.assertEqual(len(terms_of("one two three four five six seven eight")[0]), 1)
        self.assertEqual(terms_of("one two three four five six seven eight nine")[0], [])


class ParseTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = wl.parse_gotchas(GOTCHAS)
        cls.by_text = {}
        for t in cls.guide["terms"]:
            cls.by_text.setdefault(t.text, []).append(t)

    def test_terms_per_table_heading(self):
        self.assertEqual(dict(self.guide["by_table"]), {
            "Constructions": 1, "Expressions": 4, "Marketing compounds (added during audit)": 1,
            "Words": 5, "Era vocabulary": 4, "Stock phrases": 9, "Punctuation": 1,
            "Another avoid list": 1})

    def test_replacement_and_tag_columns(self):
        t = self.by_text["Emphasise"][0]
        self.assertEqual((t.table, t.tag, t.replacement), ("Words", "tell", "stress"))
        self.assertEqual(self.by_text["In order to"][0].tag, "house")

    def test_provisional_qualifier_stays_on_the_tag(self):
        self.assertEqual(self.by_text["Leverage"][0].tag, "tell (provisional)")

    def test_table_without_a_tag_column(self):
        t = self.by_text["Of course"][0]
        self.assertEqual((t.tag, t.replacement), (None, "delete"))

    def test_table_without_a_replacement_column_reads_terms_from_the_second_column(self):
        for word in ("delve", "dig", "vibrant", "showcasing"):
            t = self.by_text[word][0]
            self.assertEqual((t.table, t.tag, t.replacement), ("Era vocabulary", None, None), word)
        self.assertNotIn("2023 on", self.by_text)

    def test_prose_in_a_term_cell_is_skipped_and_reported(self):
        reported = [s["text"] for s in self.guide["skipped_cells"]]
        self.assertTrue(any(s.startswith("plus the coverage") for s in reported))
        self.assertTrue(any(s.startswith("plus a long run") for s in reported))
        self.assertNotIn("plus the coverage phrases in the other table", self.by_text)

    def test_a_table_is_found_by_structure_not_by_heading(self):
        self.assertIn("out of the box", self.by_text)
        self.assertEqual(self.by_text["out of the box"][0].replacement, "ready-made")

    def test_table_with_no_term_column_is_skipped_and_reported(self):
        self.assertEqual([t["heading"] for t in self.guide["skipped_tables"]], ["Key Points"])
        self.assertNotIn("a table the lint does not know", self.by_text)

    def test_table_inside_a_fence_is_ignored(self):
        self.assertNotIn("fenced", self.by_text)

    def test_heading_is_the_nearest_one_above(self):
        self.assertEqual(self.by_text["Certainly"][0].table, "Stock phrases")
        self.assertEqual(self.by_text["mission-critical"][0].table, "Marketing compounds (added during audit)")

    def test_em_dash_row_is_a_density_term_not_a_hit_source(self):
        t = self.by_text["—"][0]
        self.assertTrue(t.density_only)
        self.assertEqual(hits_for("a — b", [("Em-dash (—) anywhere", "colon", "tell")]), [])

    def test_table_without_outer_pipes_and_with_alignment_colons(self):
        guide = wl.parse_gotchas("### Loose\n\nBanned | Replacement\n:--- | ---:\nfoo bar | baz\n")
        t = guide["terms"][0]
        self.assertEqual((t.text, t.replacement, t.tag, t.table), ("foo bar", "baz", None, "Loose"))

    def test_tag_column_is_found_by_its_cells_when_the_header_is_unfamiliar(self):
        guide = wl.parse_gotchas("### Odd\n\n| Banned | Fix | Kind |\n|---|---|---|\n| foo | bar | house |\n| baz | qux | tell |\n")
        self.assertEqual([(t.text, t.replacement, t.tag) for t in guide["terms"]],
                         [("foo", "bar", "house"), ("baz", "qux", "tell")])

    def test_a_prose_column_is_not_mistaken_for_the_tag_column(self):
        guide = wl.parse_gotchas("### Odd\n\n| Banned | Fix | Note |\n|---|---|---|\n| foo | bar | this one is overused in blog posts |\n")
        self.assertEqual(guide["terms"][0].tag, None)

    def test_a_table_with_a_replacement_column_but_no_term_header_uses_its_first_column(self):
        guide = wl.parse_gotchas("### Odd\n\n| Cliche | Say instead |\n|---|---|\n| foo | bar |\n")
        self.assertEqual([(t.text, t.replacement) for t in guide["terms"]], [("foo", "bar")])

    def test_header_without_a_separator_row_is_not_a_table(self):
        with self.assertRaises(wl.GuideError):
            wl.parse_gotchas("### X\n\n| Banned | Replacement |\n| fenced | never |\n")

    def test_a_term_column_that_yields_nothing_fails(self):
        with self.assertRaises(wl.GuideError) as cm:
            wl.parse_gotchas("### Empty\n\n| Banned | Replacement |\n|---|---|\n| ... | x |\n")
        self.assertIn("Empty", str(cm.exception))

    def test_no_tables_fails(self):
        with self.assertRaises(wl.GuideError):
            wl.parse_gotchas("# Title\n\nJust prose, no tables.\n")

    def test_escaped_pipe_and_missing_cells(self):
        guide = wl.parse_gotchas("### X\n\n| Banned | Replacement | Why |\n|---|---|---|\n| a \\| b | c |\n")
        t = guide["terms"][0]
        self.assertEqual((t.text, t.replacement, t.tag), ("a | b", "c", None))


class Matching(unittest.TestCase):
    ROWS = [("Key (as an adjective)", "main", "tell"), ("Emphasise", "stress", "tell")]

    def texts(self, text, rows=None):
        return [h["text"] for h in hits_for(text, rows or self.ROWS)]

    def test_word_boundaries_and_case(self):
        self.assertEqual(self.texts("Key Points and the KEY idea"), ["Key", "KEY"])
        for miss in ("a keyboard", "the monkey", "keys", "keyed", "turnkey"):
            with self.subTest(miss=miss):
                self.assertEqual(self.texts(miss), [])

    def test_a_listed_term_is_a_pointer_even_in_its_literal_sense(self):
        self.assertEqual(self.texts("a cache key"), ["key"])

    def test_key_points_does_not_match_when_key_is_not_listed(self):
        self.assertEqual(self.texts("Key Points", [("Emphasise", "stress", "tell")]), [])

    def test_ise_and_ize_are_one_word(self):
        cases = [
            ([("Emphasise", "x", "tell")], "we emphasize it, and EMPHASISE it", 2),
            ([("Optimization", "x", "house")], "optimisation and optimization", 2),
            ([("emphasising", "x", "tell")], "emphasizing and emphasising", 2),
            ([("Prioritise", "x", "tell")], "prioritize, prioritised and prioritising", 1),
            ([("Realisation", "x", "house")], "realization", 1),
        ]
        for rows, text, n in cases:
            with self.subTest(text=text):
                self.assertEqual(len(hits_for(text, rows)), n)

    def test_ise_equivalence_does_not_loosen_the_word_boundary(self):
        self.assertEqual(self.texts("emphasize, emphasized and emphasizedly"), ["emphasize"])
        self.assertEqual(self.texts("rise", [("Emphasise", "x", "tell")]), [])

    def test_space_and_hyphen_are_one_separator(self):
        rows = [("Deep dive", "x", "tell"), ("Cutting-edge", "x", "house")]
        self.assertEqual(self.texts("a deep-dive and a Deep dive, cutting edge and cutting-edge", rows),
                         ["deep-dive", "Deep dive", "cutting edge", "cutting-edge"])

    def test_phrase_matches_across_one_line_wrap_and_reports_its_first_line(self):
        hits = hits_for("one\ntwo\nin order\nto go on", [("In order to", "to", "house")])
        self.assertEqual([(h["line"], h["text"]) for h in hits], [(3, "in order to")])

    def test_phrase_matches_across_a_blockquote_wrap(self):
        hits = hits_for("> in order\n> to go", [("In order to", "to", "house")])
        self.assertEqual([h["text"] for h in hits], ["in order to"])

    def test_phrase_does_not_cross_a_paragraph_break(self):
        self.assertEqual(hits_for("in order\n\nto go", [("In order to", "to", "house")]), [])

    def test_inline_code_between_words_does_not_join_them(self):
        self.assertEqual(hits_for("in `x` order to", [("In order to", "to", "house")]), [])

    def test_placeholder_construction(self):
        rows = [('"It\'s not X, but Y"', "positive", "tell")]
        self.assertEqual([h["text"] for h in hits_for("It's not just a tool, but a mindset.", rows)],
                         ["It's not just a tool, but"])
        self.assertEqual(hits_for("It's not here. Later, but it is.", rows), [])
        self.assertEqual(hits_for("It is not just a tool.", rows), [])

    def test_ellipsis_in_the_middle_of_a_phrase(self):
        rows = [("Despite its ..., X faces challenges", "state the limit", "tell")]
        text = "Despite its size, the product faces challenges."
        self.assertEqual([h["text"] for h in hits_for(text, rows)], [text[:-1]])

    def test_apostrophes_match_straight_and_curly(self):
        rows = [("It's worth noting that", "note", "tell")]
        self.assertEqual(len(hits_for("It’s worth noting that x and It's worth noting that y", rows)), 2)

    def test_slash_expansion_matches_each_alternative(self):
        rows = [("plays a key / pivotal role in", "x", None)]
        self.assertEqual(len(hits_for("it plays a pivotal role in it; it plays a key role in it", rows)), 2)

    def test_a_term_in_two_tables_is_one_hit_with_the_richer_row_as_primary(self):
        guide = wl.parse_gotchas(GOTCHAS)
        hits = wl.find_term_hits(wl.Doc("a mission-critical system"), guide["terms"])
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["table"], hits[0]["replacement"]), ("Expressions", "necessary"))
        self.assertEqual(hits[0]["also"], ["Marketing compounds (added during audit)"])

    def test_symbol_terms_other_than_the_em_dash_match_literally(self):
        self.assertEqual([h["text"] for h in hits_for("Great! Really!", [("Exclamation (!)", "full stop", "house")])],
                         ["!", "!"])

    def test_line_numbers(self):
        hits = hits_for("one\ntwo emphasise\nthree\nfour key", self.ROWS)
        self.assertEqual([(h["line"], h["text"]) for h in hits], [(2, "emphasise"), (4, "key")])


class Skipping(unittest.TestCase):
    ROWS = [("Key", "main", "tell")]

    def lines(self, text):
        return [h["line"] for h in hits_for(text, self.ROWS)]

    def test_frontmatter_is_skipped_and_lines_stay_right(self):
        text = "---\ntitle: key\ntags: [key]\n---\nprose key\n"
        self.assertEqual(self.lines(text), [5])

    def test_a_thematic_break_without_a_closing_line_is_not_frontmatter(self):
        self.assertEqual(self.lines("---\nkey\n"), [2])

    def test_fenced_code_is_skipped(self):
        text = "key one\n```js\nconst key = 1;\n```\nkey two\n~~~\nkey in tildes\n~~~\nkey three\n"
        self.assertEqual(self.lines(text), [1, 5, 9])

    def test_a_longer_closing_fence_and_an_unclosed_fence(self):
        self.assertEqual(self.lines("````\n```\nkey\n```\n````\nkey after\n"), [6])
        self.assertEqual(self.lines("key before\n```\nkey inside, never closed\n"), [1])

    def test_inline_code_is_skipped(self):
        text = "use `key` here, ``a `key` b`` there, and key itself\n"
        self.assertEqual(self.lines(text), [1])
        self.assertEqual([h["text"] for h in hits_for(text, self.ROWS)], ["key"])

    def test_inline_code_may_wrap_a_line_but_not_a_paragraph(self):
        self.assertEqual(self.lines("see `foo\nkey bar` end\nkey"), [3])
        self.assertEqual(self.lines("an unmatched ` tick\n\nkey after a break ` tick"), [3])

    def test_urls_are_skipped(self):
        text = "see https://example.com/key-points?x=key and <https://key.example/key> ok\nplain key\n"
        self.assertEqual(self.lines(text), [2])

    def test_a_trailing_parenthesis_is_not_part_of_the_url(self):
        text = "(see https://example.com/page) key\n"
        self.assertEqual(self.lines(text), [1])

    def test_markdown_link_targets_are_skipped_but_link_text_is_not(self):
        text = "[docs](../key/notes.md) and [key docs](x.md) and [[key-page]] and [[page|key alias]]\n"
        self.assertEqual([h["text"] for h in hits_for(text, self.ROWS)], ["key", "key"])

    def test_html_comments_are_skipped_single_and_multi_line(self):
        text = "a <!-- key --> b\n<!--\nkey\n-->\nkey out\n"
        self.assertEqual(self.lines(text), [5])

    def test_the_same_word_in_prose_does_hit(self):
        self.assertEqual(self.lines("key\n"), [1])


class Leftovers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found = wl.parse_revision(REVISION)
        cls.rx = cls.found["regex"]

    def hits(self, text):
        return [(h["line"], h["text"], h["region"]) for h in wl.find_leftovers(wl.Doc(text), self.rx)]

    def test_pattern_is_the_one_in_the_leftovers_section(self):
        self.assertTrue(self.found["pattern"].startswith(r"\[(Your|Insert|Link)[^]]*\]|INSERT_|"))
        self.assertNotIn("decoy", self.found["pattern"])

    def test_pattern_applies_as_a_regular_expression(self):
        cases = [
            ("Dear [Your Name],", "[Your Name]"),
            ("[Insert date here]", "[Insert date here]"),
            ("INSERT_HERE", "INSERT_"),
            ("2025-xx and 2025-XX", "2025-xx"),
            ("click?utm_source=chatgpt.com", "utm_source="),
            ("I am, as an AI model", "as an AI"),
            ("see the TODO list", "TODO"),
        ]
        for text, want in cases:
            with self.subTest(text=text):
                self.assertEqual(self.hits(text)[0][1], want)

    def test_pattern_is_case_sensitive_and_respects_word_edges(self):
        for text in ("as an ai", "TODOS", "[your name]", "a [Name] tag"):
            with self.subTest(text=text):
                self.assertEqual(self.hits(text), [])

    def test_hits_say_where_they_sit(self):
        text = ("Dear [Your Name]\n"
                "See https://example.com/?utm_source=chatgpt.com now\n"
                "```text\nTODO [Link]\n```\n"
                "and `[Insert]` inline\n")
        self.assertEqual(self.hits(text), [
            (1, "[Your Name]", "prose"), (2, "utm_source=", "URL"),
            (4, "TODO", "fenced code"), (4, "[Link]", "fenced code"), (6, "[Insert]", "inline code")])

    def test_posix_bracket_expressions_translate(self):
        cases = [
            (r"[[:digit:]]{4}", "in 2026", "2026"),
            (r"[^]]*x", "ab]cx", "cx"),
            (r"[]a]+", "x]a]y", "]a]"),
            (r"[[:alpha:]_]+", "12ab_cd34", "ab_cd"),
            (r"[[:upper:][:digit:]]+", "abCD12ef", "CD12"),
            (r"\<foo\>", "a foo b", "foo"),
            (r"a[\\]b", "a\\b", "a\\b"),
            (r"[a&&b]", "&", "&"),
        ]
        for pattern, text, want in cases:
            with self.subTest(pattern=pattern):
                self.assertEqual(re.search(wl.posix_ere_to_python(pattern), text).group(0), want)

    def test_unknown_posix_class_and_unterminated_bracket_fail(self):
        for bad in (r"[[:nope:]]", r"[abc"):
            with self.subTest(bad=bad):
                with self.assertRaises(wl.GuideError):
                    wl.posix_ere_to_python(bad)

    def test_line_continuations_and_flags(self):
        text = "### Leftovers search\n\n```sh\ngrep -nEi \\\n  'foo|bar' FILE\n```\n"
        found = wl.parse_revision(text)
        self.assertEqual(found["pattern"], "foo|bar")
        self.assertTrue(found["regex"].search("FOO"))

    def test_grep_without_dash_e_fails(self):
        with self.assertRaises(wl.GuideError):
            wl.parse_revision("### Leftovers search\n\n```bash\ngrep -n 'foo' FILE\n```\n")


class EmDash(unittest.TestCase):
    PROSE = "alpha " * 97 + "beta — gamma — delta"

    def stats(self, text):
        return wl.emdash_stats(wl.Doc(text))

    def test_density_is_per_thousand_words(self):
        s = self.stats(self.PROSE)
        self.assertEqual((s["count"], s["words"], s["per_1000"]), (2, 100, 20.0))

    def test_reference_rows_are_excluded_from_both_counts(self):
        text = (self.PROSE + "\n\n"
                "- [[plain-sentence-construction]] — sentence-level companion guide\n"
                "- [Revision passes](revision-passes.md) — what editing breaks\n"
                "- **Gotchas** — the avoid-list\n"
                "- `lint` — the checker\n"
                "- term — a definition that\n  wraps onto a second line — with a dash\n"
                "1. Node.js — the runtime\n")
        s = self.stats(text)
        self.assertEqual((s["count"], s["words"], s["reference_rows_excluded"]), (2, 100, 6))

    def test_a_bullet_that_is_prose_still_counts(self):
        s = self.stats("- This sentence is too long to be a term — so it counts\n- Fixed, then shipped — counts too\n")
        self.assertEqual((s["count"], s["reference_rows_excluded"]), (2, 0))

    def test_code_comments_and_frontmatter_are_excluded(self):
        text = "---\ntitle: a — b\n---\nreal — dash\n```\n— — —\n```\n`—` and <!-- — -->\n"
        self.assertEqual(self.stats(text)["count"], 1)

    def test_a_table_cell_holding_only_the_mark_is_an_empty_value_not_a_dash(self):
        text = self.PROSE + "\n\n| Finding | Human | Machine |\n|---|---|---|\n| a | — | — |\n| b | 1 — 2 | — |\n"
        s = self.stats(text)
        self.assertEqual((s["count"], s["empty_cells_excluded"]), (3, 3))

    def test_no_prose_means_zero_not_a_division_error(self):
        s = self.stats("```\ncode only\n```\n")
        self.assertEqual((s["count"], s["words"], s["per_1000"]), (0, 0, 0.0))


def write(directory, name, text):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class Acronyms(unittest.TestCase):
    def found(self, text):
        return [h["text"] for h in wl.find_acronyms(wl.Doc(text))]

    def test_an_acronym_not_spelled_out_is_flagged_once(self):
        self.assertEqual(self.found("The TLS page failed. The TLS page failed again."), ["TLS"])

    def test_either_expansion_form_passes(self):
        self.assertEqual(self.found("The Times Literary Supplement (TLS) failed, then TLS failed."), [])
        self.assertEqual(self.found("SWC (the Speedy Web Compiler) builds it."), [])

    def test_common_acronyms_and_single_capitals_pass(self):
        self.assertEqual(self.found("A US reader opens the URL and the API answers. I said A."), [])

    def test_a_heading_is_not_the_first_use(self):
        self.assertEqual(self.found("# TLS fails\n\nThe Times Literary Supplement (TLS) fails."), [])
        self.assertEqual(self.found("# TLS fails\n\nThe TLS homepage fails."), ["TLS"])

    def test_code_links_and_plurals(self):
        self.assertEqual(self.found("Run `GPP_CHECK` on [it](http://x.test/TCF) for IDs."), [])
        self.assertEqual(self.found("Two CMPs answered."), ["CMPs"])


class LongParagraphs(unittest.TestCase):
    def found(self, text):
        return [h["text"] for h in wl.find_long_paragraphs(wl.Doc(text))]

    def test_a_paragraph_over_the_limit_is_flagged(self):
        self.assertEqual(self.found("word " * 230), ["230 words"])

    def test_short_paragraphs_tables_and_code_pass(self):
        long_table = "| a | b |\n|---|---|\n" + ("| x " * 60 + "|\n") * 5
        self.assertEqual(self.found(("word " * 150 + "\n\n") * 3 + long_table + "```\n" + "code " * 300 + "\n```\n"), [])

    def test_a_list_counts_each_item_not_the_whole_list(self):
        short_items = "Intro line.\n" + "".join("- item %d " % i + "word " * 40 + "\n" for i in range(8))
        self.assertEqual(self.found(short_items), [])
        long_item = "- short item\n- " + "word " * 230 + "\n- another short item\n"
        self.assertEqual(self.found(long_item), ["230 words"])
        self.assertEqual(wl.find_long_paragraphs(wl.Doc(long_item))[0]["line"], 2)

    def test_a_list_item_continued_on_the_next_line_counts_as_one(self):
        self.assertEqual(self.found("1. " + "word " * 120 + "\n   " + "word " * 100 + "\n2. short\n"), ["221 words"])

    def test_the_lint_reports_both_pointers(self):
        with tempfile.TemporaryDirectory() as d:
            for name, text in ((wl.GOTCHAS, GOTCHAS), (wl.REVISION, REVISION)):
                with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                    fh.write(text)
            p = os.path.join(d, "doc.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("The TLS page. " + "word " * 210 + "\n")
            kinds = {h["kind"] for h in wl.lint([p], d)["files"][0]["hits"]}
            self.assertTrue({"acronym", "paragraph"} <= kinds)


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.guides = os.path.join(self.tmp.name, "guides")
        os.mkdir(self.guides)
        write(self.guides, "ai-writing-gotchas.md", GOTCHAS)
        write(self.guides, "revision-passes.md", REVISION)
        self.doc = write(self.tmp.name, "post.md",
                         "# A post\n\nWe emphasise the key point — in order to be clear.\n"
                         "Dear [Your Name]\n- [[page]] — the description\n")

    def run_cli(self, *args, env=None):
        e = dict(os.environ)
        e.update(env or {})
        return subprocess.run([sys.executable, HOOK, *args], capture_output=True, text=True, env=e)

    def test_plain_output(self):
        r = self.run_cli("--guides", self.guides, self.doc)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertIn("pointers to read in context, not findings", lines[0])
        hit = re.compile(r'^.+post\.md:\d+: ".+" — .+$')
        hits = [l for l in lines if hit.match(l)]
        self.assertIn('%s:3: "emphasise" — Words [tell] → stress' % self.doc, hits)
        self.assertIn('%s:3: "key" — Words [tell] → main' % self.doc, hits)
        self.assertIn('%s:3: "in order to" — Expressions [house] → to' % self.doc, hits)
        self.assertIn('%s:4: "[Your Name]" — leftovers' % self.doc, hits)
        summary = "\n".join(lines)
        self.assertIn("summary: 4 hits in 1 files", summary)
        self.assertIn("Words: 2 (tell 2)", summary)
        self.assertIn("leftovers: 1", summary)
        self.assertIn("em-dash density per 1,000 words of prose:", summary)
        self.assertRegex(summary, r"post\.md: \d+\.\d \(1 em-dashes in \d+ words; 1 reference rows left out\)")

    def test_a_run_with_no_hits_is_still_exit_0_with_a_summary(self):
        clean = write(self.tmp.name, "clean.md", "A plain sentence about nothing in particular.\n")
        r = self.run_cli("--guides", self.guides, clean)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("summary: 0 hits in 1 files", r.stdout)
        self.assertIn("em-dash density", r.stdout)

    def test_json_carries_the_same_data(self):
        r = self.run_cli("--guides", self.guides, "--json", self.doc)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("not findings", data["note"])
        self.assertEqual(data["summary"]["hits"], 4)
        self.assertEqual(data["summary"]["leftovers"], 1)
        self.assertEqual(data["terms_by_table"]["Words"], 5)
        self.assertEqual(data["files"][0]["emdash"]["count"], 1)
        by_text = {h["text"]: h for h in data["files"][0]["hits"]}
        self.assertEqual(by_text["emphasise"]["tag"], "tell")
        self.assertEqual(by_text["[Your Name]"]["kind"], "leftovers")
        self.assertEqual([t["heading"] for t in data["skipped_tables"]], ["Key Points"])

    def test_guides_flag_equals_form_and_several_files(self):
        other = write(self.tmp.name, "other.md", "no hits here\n")
        r = self.run_cli("--guides=" + self.guides, self.doc, other)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("hits in 2 files", r.stdout)

    def test_default_guides_directory_is_under_the_wiki(self):
        home = os.path.join(self.tmp.name, "home")
        target = os.path.join(home, ".wiki", "personal", "writing")
        os.makedirs(target)
        write(target, "ai-writing-gotchas.md", GOTCHAS)
        write(target, "revision-passes.md", REVISION)
        r = self.run_cli(self.doc, env={"HOME": home})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("in order to", r.stdout)

    def test_the_tool_holds_no_copy_of_the_guides(self):
        changed = GOTCHAS.replace("| In order to | to | house |", "| Zebra crossing | pelican | house |")
        write(self.guides, "ai-writing-gotchas.md", changed)
        zebra = write(self.tmp.name, "zebra.md", "a zebra crossing, and in order to\n")
        r = self.run_cli("--guides", self.guides, zebra)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"zebra crossing" — Expressions [house] → pelican', r.stdout)
        self.assertNotIn('"in order to"', r.stdout)

    def test_help_exits_0(self):
        r = self.run_cli("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("writing-lint.py", r.stdout)


class NegativeControls(unittest.TestCase):
    """Every control must exit 2, print nothing to stdout and say why on stderr."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.guides = os.path.join(self.tmp.name, "guides")
        os.mkdir(self.guides)
        self.doc = write(self.tmp.name, "post.md", "We emphasise the key point.\n")

    def run_with(self, gotchas=GOTCHAS, revision=REVISION, extra=()):
        for name, text in (("ai-writing-gotchas.md", gotchas), ("revision-passes.md", revision)):
            path = os.path.join(self.guides, name)
            if text is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                write(self.guides, name, text)
        return subprocess.run([sys.executable, HOOK, "--guides", self.guides, *extra, self.doc],
                              capture_output=True, text=True)

    def test_positive_control_the_fixtures_alone_run_clean(self):
        r = self.run_with()
        self.assertEqual(r.returncode, 0, r.stderr)

    def assert_fails(self, r, message):
        self.assertEqual(r.returncode, 2, "stdout=%r stderr=%r" % (r.stdout, r.stderr))
        self.assertEqual(r.stdout, "", "a failed run must not print a clean-looking report")
        self.assertIn(message, r.stderr)

    def test_missing_gotchas_file(self):
        self.assert_fails(self.run_with(gotchas=None), "guide file missing")

    def test_missing_revision_passes_file(self):
        self.assert_fails(self.run_with(revision=None), "guide file missing")

    def test_missing_guides_directory(self):
        r = subprocess.run([sys.executable, HOOK, "--guides", os.path.join(self.tmp.name, "nowhere"), self.doc],
                           capture_output=True, text=True)
        self.assert_fails(r, "guide file missing")

    def test_gotchas_file_with_no_tables(self):
        self.assert_fails(self.run_with(gotchas="# Gotchas\n\nProse only, no tables.\n"), "no avoid-list tables")

    def test_gotchas_file_with_only_tables_that_list_no_terms(self):
        text = "### Sources\n\n| Name | Link |\n|---|---|\n| a | b |\n"
        self.assert_fails(self.run_with(gotchas=text), "no avoid-list tables")

    def test_gotchas_table_with_a_term_column_and_no_terms(self):
        text = "### Broken\n\n| Banned | Replacement |\n|---|---|\n| ... | x |\n"
        self.assert_fails(self.run_with(gotchas=text), "yielded no terms")

    def test_revision_passes_without_a_leftovers_section(self):
        self.assert_fails(self.run_with(revision="# Revision passes\n\nNothing about leftovers.\n"),
                          "no 'Leftovers search' section")

    def test_leftovers_section_without_a_bash_block(self):
        text = "### Leftovers search\n\nOnly prose here.\n\n### Next\n\n```bash\ngrep -nE 'x' F\n```\n"
        self.assert_fails(self.run_with(revision=text), "no bash block with a grep -E pattern")

    def test_leftovers_block_without_a_grep(self):
        text = "### Leftovers search\n\n```bash\necho hello\n```\n"
        self.assert_fails(self.run_with(revision=text), "no bash block with a grep -E pattern")

    def test_leftovers_pattern_that_does_not_compile(self):
        text = "### Leftovers search\n\n```bash\ngrep -nE '(unclosed' FILE\n```\n"
        self.assert_fails(self.run_with(revision=text), "does not compile")

    def test_unreadable_input_file(self):
        self.run_with()
        r = subprocess.run([sys.executable, HOOK, "--guides", self.guides, os.path.join(self.tmp.name, "missing.md")],
                           capture_output=True, text=True)
        self.assert_fails(r, "input file cannot be read")

    def test_usage_errors(self):
        for args in ([], ["--bogus", self.doc], ["--guides"]):
            with self.subTest(args=args):
                r = subprocess.run([sys.executable, HOOK, *args], capture_output=True, text=True)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, "")
                self.assertIn("usage", r.stderr)

    def test_json_mode_fails_the_same_way(self):
        r = self.run_with(gotchas=None, extra=("--json",))
        self.assert_fails(r, "guide file missing")


@unittest.skipUnless(os.path.exists(os.path.join(LIVE, "ai-writing-gotchas.md")), "live guides not present")
class LiveGuides(unittest.TestCase):
    def test_parser_finds_the_avoid_list_and_the_leftovers_pattern(self):
        guides = wl.load_guides(LIVE)
        self.assertGreaterEqual(len(guides["terms"]), 100)
        self.assertGreaterEqual(len(guides["by_table"]), 5)
        self.assertTrue(guides["leftovers"]["pattern"])
        self.assertTrue(guides["leftovers"]["regex"].search("Dear [Your Name]"))

    def test_cli_runs_on_the_live_guides(self):
        with tempfile.TemporaryDirectory() as d:
            doc = write(d, "x.md", "A plain sentence.\n")
            r = subprocess.run([sys.executable, HOOK, doc], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not findings", r.stdout)


if __name__ == "__main__":
    unittest.main()
