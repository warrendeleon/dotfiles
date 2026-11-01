#!/usr/bin/env python3
"""Tests for memory-guard.py. Run: python3 claude/hooks/memory-guard.test.py"""
import json
import os
import subprocess
import sys
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory-guard.py")
MEM = os.path.expanduser("~/.claude/projects/-Users-someone-Developer/memory")


def run(tool_name, file_path, content=""):
    event = {"tool_name": tool_name, "tool_input": {"file_path": file_path, "content": content}}
    out = subprocess.run([sys.executable, HOOK], input=json.dumps(event), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["hookSpecificOutput"] if out.stdout.strip() else None


def memory(kind, body="A rule."):
    return f"---\nname: x\ndescription: \"x\"\nmetadata:\n  type: {kind}\n---\n\n{body}\n"


class MemoryGuard(unittest.TestCase):
    def test_allows_a_working_rule(self):
        self.assertIsNone(run("Write", f"{MEM}/feedback_x.md", memory("feedback")))

    def test_allows_the_index(self):
        self.assertIsNone(run("Write", f"{MEM}/MEMORY.md", "- [x](x.md) — hook"))

    def test_allows_a_trigger_that_points_into_the_wiki(self):
        self.assertIsNone(run("Write", f"{MEM}/project_x.md", memory("project", "Before X, read `~/.wiki/personal/x.md`.")))
        self.assertIsNone(run("Write", f"{MEM}/reference_x.md", memory("reference", "See /Users/someone/.wiki/personal/homelab/x.md.")))

    def test_refuses_a_fact_with_no_wiki_pointer(self):
        decision = run("Write", f"{MEM}/reference_x.md", memory("reference", "The archive lives at ~/Developer/x."))
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("no ~/.wiki/ pointer", decision["permissionDecisionReason"])

    def test_refuses_user_facts_and_missing_types(self):
        self.assertEqual(run("Write", f"{MEM}/user_x.md", memory("user"))["permissionDecision"], "deny")
        self.assertEqual(run("Write", f"{MEM}/x.md", "---\nname: x\n---\nA fact.")["permissionDecision"], "deny")

    def test_refuses_a_file_with_no_frontmatter(self):
        decision = run("Write", f"{MEM}/x.md", "Just a fact.")
        self.assertIn("no frontmatter", decision["permissionDecisionReason"])

    def test_reads_a_quoted_type_and_a_tilde_path(self):
        self.assertIsNone(run("Write", "~/.claude/projects/p/memory/feedback_y.md", memory("'feedback'")))

    def test_ignores_edits_and_other_paths(self):
        self.assertIsNone(run("Edit", f"{MEM}/reference_x.md"))
        self.assertIsNone(run("Write", os.path.expanduser("~/.wiki/personal/x.md"), "A fact."))
        self.assertIsNone(run("Write", f"{MEM}/notes.txt", "A fact."))

    def test_ignores_malformed_input(self):
        out = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout, "")


if __name__ == "__main__":
    unittest.main()
