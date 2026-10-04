#!/usr/bin/env python3
"""Tests for ledger-from-run.py. Run: python3 claude/hooks/ledger-from-run.test.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger-from-run.py")


def journal_lines():
    oracle = {"type": "started", "key": "k0", "label": "oracles r1"}
    oracle_r = {"type": "result", "key": "k0", "result": {"ran": ["x"], "findings": []}}
    critic = {"type": "started", "key": "k1", "label": "discover:parity r1"}
    critic_r = {"type": "result", "key": "k1", "result": {"ledger": [
        {"claim": "a", "location": "f.md:1", "check": "read"}], "findings": []}}
    return "\n".join(json.dumps(x) for x in (oracle, oracle_r, critic, critic_r)) + "\n"


class LedgerFromRun(unittest.TestCase):
    def run_hook(self, result_text):
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "journal.jsonl")
            open(j, "w").write(journal_lines())
            r = os.path.join(d, "task.output")
            open(r, "w").write(result_text)
            out = subprocess.run([sys.executable, HOOK, j, "--types", "parity", "--result", r],
                                 capture_output=True, text=True, check=True)
            return json.loads(out.stdout)

    def test_refuted_from_bare_result(self):
        final = {"clean": False, "refuted": [{"location": "f.md:2", "claim": "b", "reason": "wording"}]}
        self.assertEqual(self.run_hook(json.dumps(final))["refuted"][0]["claim"], "b")

    def test_refuted_from_harness_wrapped_output(self):
        final = {"clean": False, "refuted": [{"location": "f.md:2", "claim": "b", "reason": "wording"}]}
        wrapped = {"summary": "s", "agentCount": 1, "result": final}
        self.assertEqual(self.run_hook(json.dumps(wrapped))["refuted"][0]["claim"], "b")


if __name__ == "__main__":
    unittest.main()
