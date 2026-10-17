#!/usr/bin/env python3
"""Tests for content-inventory.py. Run: python3 claude/hooks/content-inventory.test.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content-inventory.py")

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("content_inventory", HOOK)
ci = importlib.util.module_from_spec(spec)
sys.modules["content_inventory"] = ci
spec.loader.exec_module(ci)

DOC = """---
title: "A post about 3 caches"
tags:
  - react-native
  - testing
publishDate: 2026-10-20
description: "Short."
---

# A post

The build finishes in 4.2 seconds on React Native 0.76, about 30% faster.

1. Install the package.
2. Run `npm test` in `apps/host`.

See [the docs](https://example.com/docs) and <https://example.com/auto>.
Read https://example.com/bare, then stop.

```ts
const timeout = 1500
```
"""


def of(items, kind):
    return {i["value"] for i in items if i["kind"] == kind}


def missing(orig, edited, html=False):
    return {(m["kind"], m["value"]) for m in ci.check(orig, edited, html)[1]}


class Extract(unittest.TestCase):
    def setUp(self):
        self.items = ci.extract(DOC)

    def test_numbers_in_prose_and_title(self):
        self.assertEqual(of(self.items, "number"), {"3", "4.2", "0.76", "30%"})

    def test_ordered_list_markers_are_not_numbers(self):
        self.assertFalse({"1", "2"} & of(self.items, "number"))

    def test_numbers_inside_code_are_not_prose_numbers(self):
        self.assertNotIn("1500", of(self.items, "number"))

    def test_inline_code(self):
        self.assertEqual(of(self.items, "inline-code"), {"npm test", "apps/host"})

    def test_links(self):
        self.assertEqual(of(self.items, "link"),
                         {"https://example.com/docs", "https://example.com/auto", "https://example.com/bare"})

    def test_fenced_code_keeps_its_info_string(self):
        self.assertEqual(of(self.items, "code"), {"ts\nconst timeout = 1500"})

    def test_only_hands_off_frontmatter(self):
        fm = {i["key"]: i["value"] for i in self.items if i["kind"] == "frontmatter"}
        self.assertEqual(set(fm), {"tags", "publishDate"})

    def test_signed_values_ranges_dates_times_and_versions_are_whole(self):
        got = of(ci.extract("It fell to -12, ranged 10-20, shipped 2026-10-17 at 08:30 as v1.2.3."), "number")
        self.assertEqual(got, {"-12", "10-20", "2026-10-17", "08:30", "v1.2.3"})

    def test_a_hyphenated_word_is_not_a_negative_number(self):
        self.assertEqual(of(ci.extract("A pre-12 build."), "number"), {"12"})

    def test_numbers_in_link_labels_count(self):
        self.assertIn("30%", of(ci.extract("It is [30% faster](https://x.test/a)."), "number"))

    def test_reference_style_wiki_and_html_links(self):
        text = '[guide][g] and [[setup-guide|the setup]] and <a href="./rel/page.md">x</a>\n\n[g]: ./guide.md\n'
        self.assertEqual(of(ci.extract(text), "link"), {"./guide.md", "setup-guide", "./rel/page.md"})

    def test_parentheses_inside_a_link_target(self):
        self.assertEqual(of(ci.extract("See [api](docs/api(v1).md)."), "link"), {"docs/api(v1).md"})

    def test_explicit_targets_keep_their_punctuation_bare_urls_lose_sentence_punctuation(self):
        got = of(ci.extract("Try [it](https://x.test/?q=wow!) or https://x.test/end."), "link")
        self.assertEqual(got, {"https://x.test/?q=wow!", "https://x.test/end"})

    def test_indented_nested_and_pre_code(self):
        text = "Para.\n\n    npm test\n\n- item\n\n    ```sh\n    npm run build\n    ```\n\n<pre><code>npm ci</code></pre>\n"
        got = of(ci.extract(text), "code")
        self.assertIn("\nnpm test", got)
        self.assertIn("sh\nnpm run build", got)
        self.assertIn("\nnpm ci", got)

    def test_inline_code_wrapping_a_line(self):
        self.assertIn("npm run build", of(ci.extract("Run `npm run\nbuild` now."), "inline-code"))

    def test_footnote_labels_are_not_numbers(self):
        self.assertEqual(of(ci.extract("A claim.[^1]\n\n[^1]: The source.\n"), "number"), set())


class Check(unittest.TestCase):
    def test_identical_document_keeps_everything(self):
        self.assertEqual(missing(DOC, DOC), set())

    def test_a_tightened_sentence_that_keeps_the_values_passes(self):
        edited = DOC.replace("The build finishes in 4.2 seconds on React Native 0.76, about 30% faster.",
                             "On React Native 0.76 the build takes 4.2 seconds, 30% faster.")
        self.assertEqual(missing(DOC, edited), set())

    def test_a_dropped_number_is_missing(self):
        self.assertEqual(missing(DOC, DOC.replace(", about 30% faster", "")), {("number", "30%")})

    def test_a_changed_number_is_missing(self):
        self.assertIn(("number", "4.2"), missing(DOC, DOC.replace("4.2", "4")))

    def test_a_number_dropped_from_the_title_is_missing(self):
        self.assertIn(("number", "3"), missing(DOC, DOC.replace("about 3 caches", "about caches")))

    def test_sign_range_date_and_link_label_changes_are_caught(self):
        self.assertIn(("number", "-12"), missing("Down to -12.", "Down to 12."))
        self.assertIn(("number", "10-20"), missing("A 10-20 range.", "A 10-90 range."))
        self.assertIn(("number", "2026-10-17"), missing("On 2026-10-17.", "On 2026-11-18."))
        self.assertIn(("number", "30%"), missing("[30% faster](u)", "[60% faster](u)"))

    def test_a_dropped_link_is_missing(self):
        self.assertEqual(missing(DOC, DOC.replace(" and <https://example.com/auto>", "")),
                         {("link", "https://example.com/auto")})

    def test_reference_wiki_and_html_link_changes_are_caught(self):
        self.assertIn(("link", "./guide.md"), missing("[a][g]\n\n[g]: ./guide.md\n", "[a][g]\n\n[g]: ./other.md\n"))
        self.assertIn(("link", "setup-guide"), missing("See [[setup-guide]].", "See [[setup]]."))
        self.assertIn(("link", "./a.md"), missing('<a href="./a.md">x</a>', '<a href="./b.md">x</a>'))
        self.assertIn(("link", "https://x.test/?q=wow!"), missing("[i](https://x.test/?q=wow!)", "[i](https://x.test/?q=wow)"))

    def test_code_changes_are_caught_in_every_block_form(self):
        self.assertIn(("code", "\nnpm test"), missing("P.\n\n    npm test\n", "P.\n\n    npm publish\n"))
        self.assertIn(("code", "\nnpm ci"), missing("<pre><code>npm ci</code></pre>", "<pre><code>npm i</code></pre>"))
        self.assertTrue(missing("```sh\nnpm test\n```\n", "```bash\nnpm test\n```\n"))

    def test_a_fence_moved_into_a_list_is_kept(self):
        self.assertEqual(missing("```sh\nnpm test\n```\n", "- Run it:\n\n    ```sh\n    npm test\n    ```\n"), set())

    def test_inline_code_moved_into_a_code_block_is_kept(self):
        self.assertEqual(missing("Run `npm test`.", "Run:\n\n```\nnpm test\n```\n"), set())

    def test_a_substring_inside_code_does_not_stand_in_for_cut_inline_code(self):
        self.assertIn(("inline-code", "cat"), missing("Use `cat`.\n\n```\nconcatenate()\n```\n", "Use it.\n\n```\nconcatenate()\n```\n"))

    def test_footnotes_renumbered_pass_and_a_detached_footnote_fails(self):
        orig = "A claim.[^1]\n\n[^1]: The source.\n"
        self.assertEqual(missing(orig, "A claim.[^2]\n\n[^2]: The source.\n"), set())
        self.assertIn(("footnote", "The source."), missing(orig, "A claim.\n\n[^1]: The source.\n"))

    def test_edited_code_is_missing(self):
        self.assertIn(("code", "ts\nconst timeout = 1500"), missing(DOC, DOC.replace("1500\n```", "2000\n```")))

    def test_frontmatter_changes_are_caught_in_both_directions(self):
        self.assertTrue(any(k == "frontmatter" for k, _ in missing(DOC, DOC.replace("  - testing\n", ""))))
        self.assertTrue(any(k == "frontmatter" for k, _ in missing('---\n"draft": true\n---\nx\n', '---\n"draft": false\n---\nx\n')))
        tags = "---\ntags:\n  - a\n  # kept for now\n  - b\n---\nx\n"
        self.assertTrue(missing(tags, tags.replace("  - b\n", "  - c\n")))
        self.assertTrue(any("added" in v for _, v in missing("---\ntitle: x\n---\ny\n", "---\ntitle: x\ndraft: true\n---\ny\n")))

    def test_title_and_description_wording_may_change(self):
        self.assertEqual(missing(DOC, DOC.replace('description: "Short."', 'description: "Shorter."')), set())

    def test_a_number_stated_twice_and_cut_once_is_kept(self):
        doubled = DOC.replace("about 30% faster.", "about 30% faster. That is 30% in total.")
        self.assertEqual(missing(doubled, DOC), set())


class Protected(unittest.TestCase):
    DATA = "| Run | Cold start | Build |\n|---|---|---|\n| debug | 420 ms | 0.76 |\n| release | 380 ms | 0.76 |\n"
    PROSE = "| Rule | Why |\n|---|---|\n| Cut the tail | It adds rhythm and no information |\n"

    def test_value_rows_are_data_rows_and_prose_rows_are_not(self):
        rows = of(ci.extract(self.DATA + "\n" + self.PROSE), "data-row")
        self.assertEqual(rows, {"debug | 420 ms | 0.76", "release | 380 ms | 0.76"})

    def test_a_changed_or_dropped_data_row_is_missing(self):
        self.assertIn(("data-row", "release | 380 ms | 0.76"), missing(self.DATA, self.DATA.replace("| release | 380 ms | 0.76 |\n", "")))
        self.assertIn(("data-row", "debug | 420 ms | 0.76"), missing(self.DATA, self.DATA.replace("debug", "dbg")))

    def test_a_tightened_prose_row_passes(self):
        self.assertEqual(missing(self.PROSE, self.PROSE.replace("It adds rhythm and no information", "Rhythm, no information")), set())

    def test_a_data_table_turned_into_a_sentence_is_missing(self):
        self.assertTrue(missing(self.DATA, "Debug takes 420 ms and release 380 ms on 0.76.\n"))

    def test_html_data_rows(self):
        html = "<table><tr><th>Run</th><th>ms</th></tr><tr><td>debug</td><td>420</td></tr></table>"
        self.assertIn(("data-row", "debug | 420"), missing(html, html.replace("420", "400"), True))

    def test_svg_data_attributes_and_json_data_are_kept_whole(self):
        doc = '<svg viewBox="0 0 10 10"><rect width="4"/></svg>\n<div data-values="3,5,8"></div>\n<script type="application/json">{"a": 1}</script>'
        self.assertEqual(missing(doc, doc), set())
        self.assertTrue(any(k == "chart" for k, _ in missing(doc, doc.replace('width="4"', 'width="5"'))))
        self.assertIn(("chart", "3,5,8"), missing(doc, doc.replace("3,5,8", "3,5")))
        self.assertIn(("chart", '{"a": 1}'), missing(doc, doc.replace('{"a": 1}', '{"a": 2}')))

    def test_a_pipe_in_prose_is_not_a_table(self):
        self.assertEqual(of(ci.extract("Intro.\nIt was 3 | 4 | 5 today.\n"), "data-row"), set())


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", HOOK, *args], capture_output=True, text=True)

    def write(self, d, name, text):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_exit_codes_and_json(self):
        with tempfile.TemporaryDirectory() as d:
            orig = self.write(d, "a.md", DOC)
            r = self.run_cli("check", orig, self.write(d, "b.md", DOC))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = self.run_cli("check", orig, self.write(d, "c.md", DOC.replace(", about 30% faster", "")), "--json")
            self.assertEqual(r.returncode, 1)
            data = json.loads(r.stdout)
            self.assertEqual([m["value"] for m in data["missing"]], ["30%"])
            self.assertEqual(data["total"], len(ci.extract(DOC)))

    def test_text_output_names_each_missing_value(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("check", self.write(d, "a.md", DOC), self.write(d, "c.md", DOC.replace("4.2", "four")))
            self.assertIn("MISSING", r.stdout)
            self.assertIn("4.2", r.stdout)

    def test_htm_files_are_read_as_html(self):
        self.assertTrue(ci.is_html("page.htm") and ci.is_html("page.HTML") and not ci.is_html("page.md"))

    def test_a_missing_file_exits_2(self):
        r = self.run_cli("check", "/nonexistent/a.md", "/nonexistent/b.md")
        self.assertEqual(r.returncode, 2)
        self.assertIn("cannot read", r.stderr)

    def test_bad_usage_exits_2(self):
        self.assertEqual(self.run_cli("nonsense").returncode, 2)

    def test_extract_runs(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("extract", self.write(d, "a.md", DOC), "--json")
            self.assertEqual(r.returncode, 0)
            self.assertIn("number", json.loads(r.stdout)["counts"])

    def test_real_documents_parse_and_match_themselves(self):
        for p in (os.path.expanduser("~/.wiki/personal/writing/revision-passes.md"),
                  os.path.expanduser("~/.wiki/personal/writing/ai-writing-gotchas.md")):
            if not os.path.exists(p):
                self.skipTest("live guides absent")
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            self.assertEqual(ci.check(text, text)[1], [], p)


if __name__ == "__main__":
    unittest.main(verbosity=1)
