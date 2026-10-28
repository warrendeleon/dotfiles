#!/usr/bin/env python3
"""Tests for pr-sweep.py. Run: python3 claude/hooks/pr-sweep.test.py"""
import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pr-sweep.py")

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("pr_sweep", HOOK)
ps = importlib.util.module_from_spec(spec)
sys.modules["pr_sweep"] = ps
spec.loader.exec_module(ps)

ME = ps.ME
HEAD = "b" * 40
OLD = "a" * 40
RECENT = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat()
LONG_AGO = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=60)).isoformat()


def user(login, bot=False):
    return {"login": login, "type": "Bot" if bot else "User"}


def review(state, commit=OLD, rid=1, at="2026-10-20T10:00:00Z", login=ME):
    return {"id": rid, "user": user(login), "state": state, "commit_id": commit, "submitted_at": at}


def comment(cid, login, at, reply_to=None, body="text", bot=False):
    return {"id": cid, "in_reply_to_id": reply_to, "user": user(login, bot), "created_at": at,
            "body": body, "path": "src/a.ts", "line": 3, "html_url": f"https://x/{cid}"}


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


def ctx(**kw):
    base = {
        "repo": "ncu-ad-manager",
        "pull": {"state": "open", "user": user("chuan"), "head": {"sha": HEAD}, "base": {"ref": "main"},
                 "requested_reviewers": [], "updated_at": RECENT},
        "commits": [{"author": user("chuan"), "committer": user("web-flow"), "commit": {"author": {"email": "c@x"}}}],
        "reviews": [], "review_comments": [], "issue_comments": [], "timeline": [],
        "state": {"prs": {}, "seen": {}}, "on_ticket": False,
        "patch_changed": lambda old, new: True,
    }
    for k, v in kw.items():
        if k == "pull":
            base["pull"].update(v)
        else:
            base[k] = v
    return base


class Classify(unittest.TestCase):
    def mode(self, **kw):
        return ps.classify(1, ctx(**kw))[0]

    def test_new_when_requested(self):
        self.assertEqual(self.mode(pull={"requested_reviewers": [user(ME)]}), "new")

    def test_new_when_ticket_in_pr_review(self):
        self.assertEqual(self.mode(on_ticket=True), "new")

    def test_nothing_when_not_asked(self):
        self.assertIsNone(self.mode())

    def test_stale_request_is_skipped(self):
        self.assertEqual(self.mode(pull={"requested_reviewers": [user(ME)], "updated_at": LONG_AGO}), "skip")

    def test_own_pr_skipped(self):
        self.assertEqual(self.mode(pull={"user": user(ME), "requested_reviewers": [user(ME)]}), "skip")

    def test_bot_pr_skipped(self):
        self.assertEqual(self.mode(pull={"user": user("dependabot[bot]", bot=True)}, on_ticket=True), "skip")

    def test_committed_to_skipped(self):
        commits = [{"author": user("chuan"), "committer": user("chuan"), "commit": {"author": {"email": "Me@Example.com"}}}]
        saved, ps.MY_EMAILS = ps.MY_EMAILS, {"me@example.com"}
        try:
            self.assertEqual(self.mode(commits=commits, on_ticket=True), "skip")
        finally:
            ps.MY_EMAILS = saved

    def test_closed_skipped(self):
        self.assertEqual(self.mode(pull={"state": "closed"}, on_ticket=True), "skip")

    def test_rereview_after_change_request_and_new_code(self):
        self.assertEqual(self.mode(reviews=[review("CHANGES_REQUESTED")]), "rereview")

    def test_no_rereview_when_only_main_moved(self):
        self.assertIsNone(self.mode(reviews=[review("CHANGES_REQUESTED")], patch_changed=lambda o, n: False))

    def test_rereview_when_old_head_is_gone(self):
        self.assertEqual(self.mode(reviews=[review("CHANGES_REQUESTED")], patch_changed=lambda o, n: None), "rereview")

    def test_standing_approval_needs_a_rerequest(self):
        self.assertIsNone(self.mode(reviews=[review("APPROVED")]))
        self.assertEqual(self.mode(reviews=[review("APPROVED")], pull={"requested_reviewers": [user(ME)]}), "rereview")

    def test_commented_review_is_not_decisive(self):
        self.assertEqual(self.mode(reviews=[review("COMMENTED")], on_ticket=True), "new")

    def test_dismissed_approval_same_patch_is_reapproved(self):
        tl = [{"event": "review_dismissed", "actor": user("chuan"),
               "dismissed_review": {"review_id": 1, "state": "approved", "dismissal_commit_id": HEAD}}]
        self.assertEqual(self.mode(reviews=[review("DISMISSED")], timeline=tl, patch_changed=lambda o, n: False), "reapprove")

    def test_dismissed_approval_new_patch_is_rereviewed(self):
        tl = [{"event": "review_dismissed", "actor": user("chuan"),
               "dismissed_review": {"review_id": 1, "state": "approved", "dismissal_commit_id": HEAD}}]
        self.assertEqual(self.mode(reviews=[review("DISMISSED")], timeline=tl), "rereview")

    def test_change_request_dismissed_by_a_person_is_held(self):
        tl = [{"event": "review_dismissed", "actor": user("peter"),
               "dismissed_review": {"review_id": 1, "state": "changes_requested", "dismissal_commit_id": None}}]
        self.assertEqual(self.mode(reviews=[review("DISMISSED")], timeline=tl), "hold")

    def test_handled_at_this_head_is_not_redone(self):
        st = {"prs": {"ncu-ad-manager#1": {"head": HEAD, "outcome": "held"}}, "seen": {}}
        self.assertIsNone(self.mode(on_ticket=True, state=st))

    def test_handled_at_older_head_is_redone(self):
        st = {"prs": {"ncu-ad-manager#1": {"head": OLD, "outcome": "posted"}}, "seen": {}}
        self.assertEqual(self.mode(on_ticket=True, state=st), "new")

    def test_reply_in_his_thread_makes_a_replies_lane(self):
        rc = [comment(10, ME, "2026-10-20T10:00:00Z"), comment(11, "chuan", "2026-10-21T10:00:00Z", reply_to=10)]
        mode, _, extra = ps.classify(1, ctx(reviews=[review("APPROVED", commit=HEAD)], review_comments=rc))
        self.assertEqual(mode, "replies")
        self.assertEqual(extra["threads"][0]["reply_to"], 10)
        self.assertEqual(extra["threads"][0]["comment_ids"], [11])


class Order(unittest.TestCase):
    def test_reviews_before_replies_on_approved_prs(self):
        lanes = [{"mode": "replies", "last_review": {"state": "APPROVED"}, "threads": [{"waiting_since": "2026-10-01"}]},
                 {"mode": "new", "created_at": "2026-10-20"},
                 {"mode": "replies", "last_review": {"state": "CHANGES_REQUESTED"}, "threads": [{"waiting_since": "2026-10-25"}]},
                 {"mode": "rereview", "last_review": {"state": "CHANGES_REQUESTED", "submitted_at": "2026-10-22"}, "threads": []}]
        got = ps.order_lanes(lanes)
        self.assertEqual([(l["mode"], (l.get("last_review") or {}).get("state")) for l in got],
                         [("rereview", "CHANGES_REQUESTED"), ("replies", "CHANGES_REQUESTED"), ("new", None), ("replies", "APPROVED")])


class Threads(unittest.TestCase):
    def test_bot_and_seen_and_older_comments_are_ignored(self):
        rc = [comment(1, "chuan", "2026-10-19T09:00:00Z"),
              comment(2, ME, "2026-10-20T10:00:00Z", reply_to=1),
              comment(3, "Copilot", "2026-10-21T10:00:00Z", reply_to=1, bot=True),
              comment(4, "chuan", "2026-10-21T11:00:00Z", reply_to=1),
              comment(5, "chuan", "2026-10-21T12:00:00Z", reply_to=1)]
        out = ps.new_threads(rc, [], {"5": {}}, "")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["comment_ids"], [4])

    def test_reply_he_reviewed_past_is_ignored(self):
        rc = [comment(1, ME, "2026-10-14T09:00:00Z"), comment(2, "chuan", "2026-10-15T10:00:00Z", reply_to=1)]
        self.assertEqual(ps.new_threads(rc, [], {}, "2026-10-16T09:30:00Z"), [])
        self.assertEqual(len(ps.new_threads(rc, [], {}, "2026-10-14T09:00:00Z")), 1)

    def test_thread_without_him_is_ignored(self):
        rc = [comment(1, "peter", "2026-10-19T09:00:00Z"), comment(2, "chuan", "2026-10-20T10:00:00Z", reply_to=1)]
        self.assertEqual(ps.new_threads(rc, [], {}, ""), [])

    def test_mention_after_his_last_activity(self):
        ic = [comment(7, "chuan", "2026-10-19T09:00:00Z", body="@warrendeleon old"),
              comment(8, "chuan", "2026-10-22T09:00:00Z", body="@warrendeleon can you look again?"),
              comment(9, "chuan", "2026-10-22T10:00:00Z", body="no mention")]
        out = ps.new_threads([], ic, {}, "2026-10-20T10:00:00Z")
        self.assertEqual([t["reply_to"] for t in out], [8])
        self.assertEqual(out[0]["kind"], "issue")


class Lock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        ps.HOME = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, fn):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(None)

    def test_second_lock_is_busy_until_unlocked(self):
        self.assertEqual(self.run_cmd(ps.cmd_lock), 0)
        self.assertEqual(self.run_cmd(ps.cmd_lock), 3)
        self.run_cmd(ps.cmd_unlock)
        self.assertEqual(self.run_cmd(ps.cmd_lock), 0)

    def test_stale_lock_is_taken_over(self):
        self.run_cmd(ps.cmd_lock)
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=4)).isoformat()
        with open(os.path.join(self.tmp.name, "lock", "since"), "w") as fh:
            fh.write(old)
        self.assertEqual(self.run_cmd(ps.cmd_lock), 0)

    def test_replies_lane_records_comments_not_the_head(self):
        args = type("A", (), {"repo": "nuk-cdn", "pr": 5, "head": HEAD, "outcome": "nothing", "reason": "", "seen": "31", "mode": "replies"})
        with contextlib.redirect_stdout(io.StringIO()):
            ps.cmd_record(args)
        s = ps.load_state()
        self.assertNotIn("nuk-cdn#5", s["prs"])
        self.assertIn("31", s["seen"])

    def test_record_keeps_head_and_seen(self):
        args = type("A", (), {"repo": "nuk-cdn", "pr": 5, "head": HEAD, "outcome": "posted", "reason": "", "seen": "11,12", "mode": "new"})
        with contextlib.redirect_stdout(io.StringIO()):
            ps.cmd_record(args)
        s = ps.load_state()
        self.assertEqual(s["prs"]["nuk-cdn#5"]["head"], HEAD)
        self.assertEqual(set(s["seen"]), {"11", "12"})


class Texts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        write_json(os.path.join(d, "payload.json"),
                   {"commit_id": HEAD, "event": "REQUEST_CHANGES", "body": "One point is open.",
                    "comments": [{"path": "src/a.ts", "line": 4, "side": "RIGHT",
                                  "body": "🔴 **Change requested:** The guard is missing here, so it throws."}]})
        write_json(os.path.join(d, "reply-77.json"), {"body": "Not yet: the guard is still missing at src/a.ts:4."})
        self.a = type("A", (), {"dir": d})

    def tearDown(self):
        self.tmp.cleanup()

    def call(self, fn):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(self.a)

    def texts(self):
        with open(os.path.join(self.tmp.name, "texts.md"), encoding="utf-8") as fh:
            return fh.read()

    def write(self, s):
        with open(os.path.join(self.tmp.name, "texts.md"), "w", encoding="utf-8") as fh:
            fh.write(s)

    def test_round_trip_writes_edits_back(self):
        self.call(ps.cmd_export_text)
        self.write(self.texts().replace("so it throws", "so `run()` throws").replace("Not yet: the", "The"))
        self.assertEqual(self.call(ps.cmd_import_text), 0)
        p = read_json(os.path.join(self.tmp.name, "payload.json"))
        self.assertTrue(p["comments"][0]["body"].endswith("so `run()` throws."))
        self.assertEqual(p["event"], "REQUEST_CHANGES")
        r = read_json(os.path.join(self.tmp.name, "reply-77.json"))
        self.assertTrue(r["body"].startswith("The guard"))

    def test_lost_traffic_light_is_refused(self):
        self.call(ps.cmd_export_text)
        self.write(self.texts().replace("🔴 **Change requested:** ", ""))
        self.assertEqual(self.call(ps.cmd_import_text), 1)
        p = read_json(os.path.join(self.tmp.name, "payload.json"))
        self.assertTrue(p["comments"][0]["body"].startswith("🔴"))

    def test_dropped_section_is_refused(self):
        self.call(ps.cmd_export_text)
        t = self.texts()
        self.write(t[:t.index("<!-- pr-sweep:reply 77 -->")])
        self.assertEqual(self.call(ps.cmd_import_text), 1)


class Concat(unittest.TestCase):
    def test_pages_are_joined(self):
        self.assertEqual(ps._concat_json('[1,2]\n[3]\n'), [1, 2, 3])
        self.assertEqual(ps._concat_json('{"a":1}'), [{"a": 1}])


if __name__ == "__main__":
    unittest.main(verbosity=1)
