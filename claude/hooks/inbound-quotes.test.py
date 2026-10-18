#!/usr/bin/env python3
"""Tests for inbound-quotes.py. Run: python3 claude/hooks/inbound-quotes.test.py"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inbound-quotes.py")

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("inbound_quotes", HOOK)
iq = importlib.util.module_from_spec(spec)
sys.modules["inbound_quotes"] = iq
spec.loader.exec_module(iq)

SOURCE = """---
title: "The source post"
---

The chunks are guarded; the map is naked. Post 17 closes that.

A dead tab is honest, and it is not a working app. Nothing else loads.
"""

EDITED = """---
title: "The source post"
---

Post 17 closes that.

A dead tab is honest about the failure, and it is still not a working app.
"""


class Workspace(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.docs = os.path.join(self.root, "docs")
        os.makedirs(self.docs)
        self.original = self.write("original.md", SOURCE)
        self.edited = self.write("edited.md", EDITED)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text, folder=None):
        path = os.path.join(folder or self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def doc(self, name, text):
        return self.write(name, text, self.docs)

    def check(self, **kw):
        return iq.check(self.original, self.edited, [self.docs], kw.get("min_words", 5), kw.get("own", ()))

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, HOOK, *args], capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr


class Quotes(Workspace):
    def test_a_quote_the_edit_removed_is_reported_with_its_file_and_line(self):
        self.doc("later.md", 'Intro.\n\nPost 15 said it in eight words: "The chunks are guarded; the map is naked."\n')
        hits, missing = self.check()
        self.assertEqual(len(hits), 1)
        self.assertEqual([(os.path.basename(m["file"]), m["line"]) for m in missing], [("later.md", 3)])

    def test_a_quote_the_edit_kept_is_found_but_not_missing(self):
        self.doc("later.md", 'It said "Post 17 closes that and more." once.\n')
        hits, missing = self.check()
        self.assertEqual(len(hits), 0)
        self.doc("kept.md", 'It said "Post 17 closes that. A dead tab is honest" once.\n')
        self.assertEqual(self.check()[1], [])

    def test_a_reworded_quote_is_missing(self):
        self.doc("later.md", 'See "A dead tab is honest, and it is not a working app."\n')
        _, missing = self.check()
        self.assertEqual(len(missing), 1)

    def test_matching_ignores_case_punctuation_emphasis_and_curly_quotes(self):
        self.doc("later.md", "It was “THE CHUNKS are *guarded* — the map is naked”, they said.\n")
        _, missing = self.check()
        self.assertEqual(len(missing), 1)

    def test_a_blockquote_counts(self):
        self.doc("later.md", "> The chunks are guarded;\n> the map is naked.\n")
        _, missing = self.check()
        self.assertEqual([m["line"] for m in missing], [1])

    def test_a_quote_that_wraps_over_lines_counts(self):
        self.doc("later.md", 'Post 15 wrote "The chunks are\nguarded; the map\nis naked." in full.\n')
        _, missing = self.check()
        self.assertEqual(len(missing), 1)

    def test_an_ellipsis_splits_a_quote_and_each_part_is_checked(self):
        self.doc("later.md", 'See "The chunks are guarded; the map is naked ... Post 17 closes that. A dead tab is honest" there.\n')
        hits, missing = self.check()
        self.assertEqual(len(hits), 2)
        self.assertEqual([m["quote"] for m in missing], ["The chunks are guarded; the map is naked"])


class Filters(Workspace):
    def test_short_spans_slugs_and_paths_are_ignored(self):
        self.doc("later.md", 'See "naked" and "the map is naked" and "/images/blog/the-map-is-naked-now.webp".\n')
        self.assertEqual(self.check()[0], [])

    def test_min_words_is_a_setting(self):
        self.doc("later.md", 'See "the map is naked" here.\n')
        self.assertEqual(self.check()[0], [])
        self.assertEqual(len(self.check(min_words=4)[1]), 1)

    def test_front_matter_and_fenced_code_in_other_files_are_skipped(self):
        self.doc("later.md", '---\ndescription: "The chunks are guarded; the map is naked."\n---\n\n```\nsay "The chunks are guarded; the map is naked."\n```\n')
        self.assertEqual(self.check()[0], [])

    def test_the_original_the_edited_file_and_self_are_never_searched(self):
        text = 'Said "The chunks are guarded; the map is naked."\n'
        live = self.write("live.md", text, self.docs)
        self.assertEqual(len(self.check()[1]), 1)
        self.assertEqual(self.check(own=[live])[1], [])
        hits, _ = iq.check(self.original, self.edited, [self.root], 5, ())
        self.assertTrue(all(os.path.basename(h["file"]) not in ("original.md", "edited.md") for h in hits))

    def test_the_backup_directory_is_never_searched(self):
        backup = os.path.expanduser("~/.claude/edit-doc")
        self.assertTrue(iq.skip_prefix().startswith(os.path.realpath(backup)))

    def test_only_text_files_and_not_dependency_folders(self):
        text = 'Said "The chunks are guarded; the map is naked."\n'
        self.write("node_modules/pkg/readme.md", text, self.docs)
        self.write("data.json", text, self.docs)
        self.assertEqual(self.check()[0], [])

    def test_a_direct_file_path_works_and_a_missing_path_is_an_error(self):
        one = self.doc("one.md", 'Said "The chunks are guarded; the map is naked."\n')
        self.assertEqual(len(iq.check(self.original, self.edited, [one], 5)[1]), 1)
        with self.assertRaises(iq.QuoteError):
            iq.check(self.original, self.edited, [os.path.join(self.root, "nope")], 5)


class Cli(Workspace):
    def setUp(self):
        super().setUp()
        self.doc("later.md", 'Said "The chunks are guarded; the map is naked."\n')

    def test_check_exits_1_on_a_missing_quote_and_prints_it(self):
        code, out, _ = self.run_cli("check", self.original, self.edited, "--in", self.docs)
        self.assertEqual(code, 1)
        self.assertIn("MISSING", out)
        self.assertIn("the map is naked", out)

    def test_check_exits_0_when_the_edit_kept_everything(self):
        code, out, _ = self.run_cli("check", self.original, self.original, "--in", self.docs)
        self.assertEqual(code, 0)
        self.assertIn("0 no longer in", out)

    def test_find_lists_the_quotes_and_exits_0(self):
        code, out, _ = self.run_cli("find", self.original, "--in", self.docs)
        self.assertEqual(code, 0)
        self.assertIn("later.md:1", out)

    def test_json_output(self):
        code, out, _ = self.run_cli("check", self.original, self.edited, "--in", self.docs, "--json")
        data = json.loads(out)
        self.assertEqual((code, data["total"], len(data["missing"])), (1, 1, 1))

    def test_exit_2_without_in_or_with_an_unreadable_file_or_wrong_usage(self):
        self.assertEqual(self.run_cli("check", self.original, self.edited)[0], 2)
        self.assertEqual(self.run_cli("check", self.original, os.path.join(self.root, "none.md"), "--in", self.docs)[0], 2)
        self.assertEqual(self.run_cli("bogus")[0], 2)
        self.assertEqual(self.run_cli("check", self.original, self.edited, "--in", self.docs, "--min-words", "x")[0], 2)


if __name__ == "__main__":
    unittest.main()
