#!/usr/bin/env python3
"""The deterministic half of the hourly pull request review sweep.

The pr-review-sweep scheduled task runs this; the agents in
claude/workflows/pr-review-sweep.js do the reading and the writing.

  pr-sweep.py lock                     take the run lock; exit 3 while another run holds it
  pr-sweep.py unlock
  pr-sweep.py discover --run-dir D     find what needs Warren's review and write D/discover.json
  pr-sweep.py check-head --repo R --pr N --head SHA [--kind review|reply]
                                       exit 0 only while the PR is open at SHA (and, for a review,
                                       has no approval or change request of his at SHA)
  pr-sweep.py record --repo R --pr N --head SHA --outcome posted|held|nothing [--mode M] [--reason T] [--seen ID,...]
  pr-sweep.py export-text D            the drafted texts of one lane as D/texts.md, for tighten
  pr-sweep.py import-text D            write D/texts.md back into D/payload.json and D/reply-*.json

A PR is a lane for the review workflow when it needs a new review, a re-review or
an answer in one of his threads; a dismissed approval whose own patch is unchanged
is re-approved without agents. Nothing here posts to GitHub or writes to Jira.
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def git_email():
    """Commits are also matched by author email, which only git config knows."""
    try:
        r = subprocess.run(["git", "config", "--global", "user.email"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return set()
    return {r.stdout.strip().lower()} - {""}


OWNER = "newsuk"
REPOS = ("ncu-ad-manager", "ncu-commercial-assets", "nuk-cdn")
ME = "warrendeleon"
MY_EMAILS = git_email()
CAP = 3
STALE_DAYS = 30
LOCK_STALE = dt.timedelta(hours=3)
HOME = os.path.expanduser(os.environ.get("PR_SWEEP_HOME", "~/.claude/pr-review-sweep"))
CLONES = os.path.expanduser("~/Developer/news.co.uk")
KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
DECISIVE = ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")
MARK_RE = re.compile(r"^<!-- pr-sweep:(body|comment (\d+)[^>]*|reply (\d+)) -->$", re.M)
LIGHTS = ("🟢 **Good:**", "🟡 **Suggestion:**", "🔴 **Change requested:**")


class GhError(RuntimeError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


# ---------- GitHub and Jira ----------

def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_json(path):
    return json.loads(read_text(path))


def _concat_json(text):
    """`gh api --paginate` prints one JSON array per page, back to back."""
    out, dec, i = [], json.JSONDecoder(), 0
    text = text.strip()
    while i < len(text):
        val, j = dec.raw_decode(text, i)
        out.extend(val) if isinstance(val, list) else out.append(val)
        i = j
        while i < len(text) and text[i].isspace():
            i += 1
    return out


def gh_api(path, paginate=False):
    cmd = ["gh", "api"] + (["--paginate"] if paginate else []) + [path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise GhError(f"gh api {path}: {r.stderr.strip()[:300]}")
    if paginate:
        return _concat_json(r.stdout)
    return json.loads(r.stdout) if r.stdout.strip() else None


def gh_search(flag):
    r = subprocess.run(
        ["gh", "search", "prs", flag, "--state=open", f"--owner={OWNER}", "--limit", "200",
         "--json", "number,repository,url,updatedAt"],
        capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise GhError(f"gh search prs {flag}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout or "[]")


def gh_open_prs(repo):
    r = subprocess.run(
        ["gh", "pr", "list", "--repo", f"{OWNER}/{repo}", "--state", "open", "--limit", "300",
         "--json", "number,title,headRefName"],
        capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise GhError(f"gh pr list {repo}: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout or "[]")


def secrets():
    env = {}
    try:
        lines = read_text(os.path.expanduser("~/.secrets.env")).splitlines()
    except OSError:
        return env
    for ln in lines:
        m = re.match(r"\s*(?:export\s+)?([A-Z0-9_]+)=(.*)$", ln)
        if m:
            env[m.group(1)] = m.group(2).strip().strip("'\"")
    return env


def jira_search(jql, fields="summary,issuetype"):
    env = secrets()
    site = env.get("JIRA_SITE", "")
    if not site or not env.get("JIRA_EMAIL") or not env.get("JIRA_TOKEN"):
        raise RuntimeError("JIRA_SITE, JIRA_EMAIL or JIRA_TOKEN missing from ~/.secrets.env")
    if not site.startswith("http"):
        site = "https://" + site
    q = urllib.parse.urlencode({"jql": jql, "fields": fields, "maxResults": 100})
    req = urllib.request.Request(f"{site.rstrip('/')}/rest/api/3/search/jql?{q}")
    tok = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_TOKEN']}".encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return {i["key"]: {"type": ((i.get("fields") or {}).get("issuetype") or {}).get("name", ""),
                       "summary": (i.get("fields") or {}).get("summary", "")}
            for i in data.get("issues", [])}


# ---------- state and lock ----------

def state_path():
    return os.path.join(HOME, "state.json")


def load_state():
    try:
        s = read_json(state_path())
    except (OSError, ValueError):
        s = {}
    s.setdefault("prs", {})
    s.setdefault("seen", {})
    return s


def save_state(s):
    os.makedirs(HOME, exist_ok=True)
    tmp = state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1, sort_keys=True)
    os.replace(tmp, state_path())


def cmd_lock(_):
    os.makedirs(HOME, exist_ok=True)
    lock = os.path.join(HOME, "lock")
    stamp = os.path.join(lock, "since")
    try:
        os.mkdir(lock)
    except FileExistsError:
        try:
            since = parse_time(read_text(stamp).strip())
        except (OSError, ValueError):
            since = None
        if since and now() - since < LOCK_STALE:
            print(f"busy: another run has held the lock since {since.isoformat()}")
            return 3
        shutil.rmtree(lock, ignore_errors=True)
        os.mkdir(lock)
        print(f"took over a stale lock from {since.isoformat() if since else 'an unknown time'}")
    with open(stamp, "w") as fh:
        fh.write(now().isoformat())
    print("locked")
    return 0


def cmd_unlock(_):
    shutil.rmtree(os.path.join(HOME, "lock"), ignore_errors=True)
    print("unlocked")
    return 0


def cmd_record(a):
    s = load_state()
    at = now().isoformat()
    # A replies lane judges comments, not the head: recording its head would stop a review
    # that becomes due later at the same head.
    if getattr(a, "mode", None) != "replies":
        s["prs"][f"{a.repo}#{a.pr}"] = {"head": a.head, "outcome": a.outcome, "reason": a.reason or "", "at": at}
    for cid in filter(None, (a.seen or "").split(",")):
        s["seen"][cid.strip()] = {"outcome": a.outcome, "at": at}
    save_state(s)
    print(f"recorded {a.repo}#{a.pr} {a.outcome} at {a.head[:9]}")
    return 0


# ---------- classification ----------

def is_bot(user):
    login = (user or {}).get("login", "")
    return (user or {}).get("type") == "Bot" or login.endswith("[bot]") or login.lower() == "copilot"


def committed_by_me(commits):
    for c in commits:
        for who in ("author", "committer"):
            if ((c.get(who) or {}).get("login") or "") == ME:
                return True
        if ((c.get("commit") or {}).get("author") or {}).get("email", "").lower() in MY_EMAILS:
            return True
    return False


def last_decisive(reviews):
    mine = [r for r in reviews if (r.get("user") or {}).get("login") == ME and r.get("state") in DECISIVE]
    return mine[-1] if mine else None


def dismissal(timeline, review_id):
    """(original state, who dismissed it) for one dismissed review, from the issue timeline."""
    for ev in timeline:
        d = ev.get("dismissed_review") or {}
        if ev.get("event") == "review_dismissed" and d.get("review_id") == review_id:
            return (d.get("state") or "").lower(), (ev.get("actor") or {}).get("login", ""), d.get("dismissal_commit_id")
    return "", "", None


def new_threads(review_comments, issue_comments, seen, my_last_activity):
    """Comments that may need an answer from Warren: replies in a review thread he took part
    in, and conversation comments that mention him, written after his last activity on the PR
    (a comment in that thread, a review, a conversation comment). A reply he reviewed past has
    been read. Bots and comments already judged are left out."""
    threads = {}
    for c in sorted(review_comments, key=lambda c: c.get("created_at", "")):
        root = c.get("in_reply_to_id") or c["id"]
        threads.setdefault(root, []).append(c)
    out = []
    for root, cs in threads.items():
        mine = [c for c in cs if (c.get("user") or {}).get("login") == ME]
        if not mine:
            continue
        last_mine = max(mine[-1]["created_at"], my_last_activity or "")
        fresh = [c for c in cs if c["created_at"] > last_mine and not is_bot(c.get("user"))
                 and (c.get("user") or {}).get("login") != ME and str(c["id"]) not in seen]
        if fresh:
            first = cs[0]
            out.append({"kind": "review", "reply_to": root, "path": first.get("path"),
                        "line": first.get("line") or first.get("original_line"),
                        "url": fresh[-1].get("html_url"), "comment_ids": [c["id"] for c in fresh],
                        "authors": sorted({c["user"]["login"] for c in fresh}),
                        "waiting_since": fresh[0]["created_at"]})
    for c in sorted(issue_comments, key=lambda c: c.get("created_at", "")):
        login = (c.get("user") or {}).get("login", "")
        if (login == ME or is_bot(c.get("user")) or str(c["id"]) in seen
                or not re.search(r"@" + ME + r"\b", c.get("body") or "", re.I)
                or (my_last_activity and c["created_at"] <= my_last_activity)):
            continue
        out.append({"kind": "issue", "reply_to": c["id"], "path": None, "line": None,
                    "url": c.get("html_url"), "comment_ids": [c["id"]], "authors": [login],
                    "waiting_since": c["created_at"]})
    return out


def own_patch_changed(repo, base, pr, old, new):
    """True when the PR's own changes differ between two heads, False when only main moved
    under them (merges from main, a rebase), None when it cannot be told (the old head is gone).
    Compares `git patch-id --stable` of each head against its merge base with the base branch."""
    if old == new:
        return False
    clone = os.path.join(CLONES, repo)
    if not os.path.isdir(os.path.join(clone, ".git")):
        return None

    def git(*args, check=True):
        r = subprocess.run(["git", "-C", clone, *args], capture_output=True, text=True, timeout=300)
        if check and r.returncode != 0:
            raise GhError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")
        return r

    git("fetch", "--quiet", "--no-write-fetch-head", "origin",
        f"+refs/heads/{base}:refs/remotes/origin/{base}", f"refs/pull/{pr}/head")
    for sha in (old, new):
        if git("cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode != 0:
            git("fetch", "--quiet", "--no-write-fetch-head", "origin", sha, check=False)
            if git("cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode != 0:
                return None

    def pid(sha):
        mb = git("merge-base", f"origin/{base}", sha).stdout.strip()
        diff = git("diff", "--no-color", mb, sha).stdout
        r = subprocess.run(["git", "-C", clone, "patch-id", "--stable"], input=diff,
                           capture_output=True, text=True, timeout=120)
        return r.stdout.split()[0] if r.stdout.strip() else ""

    return pid(old) != pid(new)


def classify(pr, ctx):
    """Decide what one PR needs. ctx: pull, commits, reviews, review_comments, issue_comments,
    timeline, state, on_ticket, patch_changed (callable old, new -> True/False/None).
    Returns (mode, reason, extra) where mode is new, rereview, reapprove, replies, hold, skip or None."""
    pull = ctx["pull"]
    author = pull.get("user") or {}
    head = pull["head"]["sha"]
    if pull.get("state") != "open":
        return "skip", "no longer open", {}
    if author.get("login") == ME:
        return "skip", "his own PR", {}
    if is_bot(author):
        return "skip", "opened by a bot", {}
    if committed_by_me(ctx["commits"]):
        return "skip", "he has commits on it", {}
    requested = ME in [u.get("login") for u in pull.get("requested_reviewers") or []]
    last = last_decisive(ctx["reviews"])
    st = ctx["state"]["prs"].get(f"{ctx['repo']}#{pr}") or {}
    handled = st.get("head") == head
    my_times = [r.get("submitted_at") or "" for r in ctx["reviews"] if (r.get("user") or {}).get("login") == ME]
    my_times += [c.get("created_at") or "" for c in ctx["issue_comments"] if (c.get("user") or {}).get("login") == ME]
    threads = new_threads(ctx["review_comments"], ctx["issue_comments"], ctx["state"]["seen"], max(my_times) if my_times else "")
    extra = {"threads": threads, "requested": requested, "last_review": None}
    mode, reason = None, ""
    if last is None:
        stale = now() - parse_time(pull["updated_at"]) > dt.timedelta(days=STALE_DAYS)
        if (requested or ctx["on_ticket"]) and stale:
            return "skip", f"no activity for {STALE_DAYS} days", extra
        if requested or ctx["on_ticket"]:
            mode, reason = "new", "review requested" if requested else "ticket in PR review"
    else:
        extra["last_review"] = {"id": last["id"], "state": last["state"], "commit_id": last.get("commit_id"),
                                "submitted_at": last.get("submitted_at"), "url": last.get("html_url")}
        if last["state"] == "DISMISSED":
            orig, actor, by_commit = dismissal(ctx["timeline"], last["id"])
            extra["last_review"]["dismissed_from"] = orig
            if orig == "changes_requested" and actor != ME and not by_commit:
                mode, reason = "hold", f"{actor or 'someone'} dismissed his change request"
            else:
                changed = ctx["patch_changed"](last.get("commit_id"), head)
                if orig == "approved" and changed is False:
                    mode, reason = "reapprove", "approval dismissed; the PR's own changes are the same"
                else:
                    mode, reason = "rereview", f"{orig or 'review'} dismissed and the PR's own changes moved"
        elif last.get("commit_id") != head and (last["state"] == "CHANGES_REQUESTED" or requested):
            changed = ctx["patch_changed"](last.get("commit_id"), head)
            if changed is not False:
                mode, reason = "rereview", "new changes since his last review"
    if mode in ("new", "rereview", "reapprove", "hold") and handled:
        mode, reason = None, f"already {st.get('outcome')} at this head"
    if mode is None and threads:
        mode, reason = "replies", "new comments in his threads"
    return mode, reason, extra


# ---------- discover ----------

def fetch_pr(repo, n):
    base = f"repos/{OWNER}/{repo}"
    pull = gh_api(f"{base}/pulls/{n}")
    with ThreadPoolExecutor(4) as ex:
        commits, reviews, rc, ic = ex.map(lambda p: gh_api(p, paginate=True), [
            f"{base}/pulls/{n}/commits?per_page=100", f"{base}/pulls/{n}/reviews?per_page=100",
            f"{base}/pulls/{n}/comments?per_page=100", f"{base}/issues/{n}/comments?per_page=100"])
    last = last_decisive(reviews)
    timeline = gh_api(f"{base}/issues/{n}/timeline?per_page=100", paginate=True) if last and last["state"] == "DISMISSED" else []
    return {"pull": pull, "commits": commits, "reviews": reviews, "review_comments": rc,
            "issue_comments": ic, "timeline": timeline}


def jira_key(pull):
    for text in (pull.get("title") or "", (pull.get("head") or {}).get("ref") or ""):
        m = KEY_RE.search(text)
        if m:
            return m.group(1)
    return None


def order_lanes(lanes):
    """A re-review, or a reply on a PR his change request is blocking, comes first; then new
    reviews; then replies on PRs he has approved, which block no one. Oldest wait first within each."""
    def waiting(i):
        ts = [t["waiting_since"] for t in i.get("threads") or []]
        if i["mode"] == "rereview" and i.get("last_review"):
            ts.append(i["last_review"].get("submitted_at") or "")
        return min(ts) if ts else (i.get("created_at") or "")

    def rank(i):
        blocking = (i.get("last_review") or {}).get("state") == "CHANGES_REQUESTED"
        return 0 if i["mode"] == "rereview" or (i["mode"] == "replies" and blocking) else 1 if i["mode"] == "new" else 2

    return sorted(lanes, key=lambda i: (rank(i), waiting(i)))


def cmd_discover(a):
    run = os.path.abspath(a.run_dir)
    os.makedirs(run, exist_ok=True)
    state = load_state()
    errors, outside = [], []
    try:
        tickets = jira_search('status = "PR review" ORDER BY updated DESC')
    except Exception as e:  # Jira down: carry on with what GitHub says
        tickets = {}
        errors.append(f"Jira search failed: {e}")
    cands = set()
    for flag in (f"--review-requested={ME}", f"--reviewed-by={ME}"):
        try:
            for p in gh_search(flag):
                name = (p.get("repository") or {}).get("name", "")
                (cands.add((name, p["number"])) if name in REPOS else outside.append(p.get("url")))
        except GhError as e:
            errors.append(str(e))
    for repo in REPOS:
        try:
            for p in gh_open_prs(repo):
                keys = set(KEY_RE.findall(p.get("title") or "")) | set(KEY_RE.findall(p.get("headRefName") or ""))
                if keys & set(tickets):
                    cands.add((repo, p["number"]))
        except GhError as e:
            errors.append(str(e))

    def one(c):
        repo, n = c
        try:
            return c, fetch_pr(repo, n), None
        except Exception as e:
            return c, None, str(e)

    with ThreadPoolExecutor(6) as ex:
        fetched = list(ex.map(one, sorted(cands)))
    keys = {jira_key(d["pull"]) for _, d, _ in fetched if d} - {None}
    types = {k: v for k, v in tickets.items()}
    missing = sorted(keys - set(types))
    if missing:
        try:
            types.update(jira_search("key in (" + ",".join(missing) + ")"))
        except Exception as e:
            errors.append(f"Jira lookup of {len(missing)} keys failed: {e}")

    lanes, reapprove, holds, skipped = [], [], [], []
    for (repo, n), d, err in fetched:
        if err:
            errors.append(f"{repo}#{n}: {err}")
            continue
        pull = d["pull"]
        key = jira_key(pull)
        ctx = dict(d, repo=repo, state=state, on_ticket=key in tickets,
                   patch_changed=lambda old, new, r=repo, p=pull, k=n: own_patch_changed(r, p["base"]["ref"], k, old, new))
        try:
            mode, reason, extra = classify(n, ctx)
        except Exception as e:
            errors.append(f"{repo}#{n}: {e}")
            continue
        item = {"repo": repo, "n": n, "url": pull.get("html_url"), "title": pull.get("title"),
                "author": (pull.get("user") or {}).get("login"), "draft": pull.get("draft", False),
                "head": pull["head"]["sha"], "base": pull["base"]["ref"], "key": key,
                "ticket_type": (types.get(key) or {}).get("type", ""), "mode": mode, "reason": reason,
                "created_at": pull.get("created_at"),
                "size": {"additions": pull.get("additions"), "deletions": pull.get("deletions"), "files": pull.get("changed_files")},
                **extra}
        item["dir"] = os.path.join(run, f"{repo}-{n}")
        if mode == "skip":
            skipped.append({"pr": f"{repo}#{n}", "reason": reason})
        elif mode == "reapprove":
            os.makedirs(item["dir"], exist_ok=True)
            with open(os.path.join(item["dir"], "payload.json"), "w", encoding="utf-8") as fh:
                json.dump({"commit_id": item["head"], "event": "APPROVE", "body": ""}, fh)
            item["payload"] = os.path.join(item["dir"], "payload.json")
            reapprove.append(item)
        elif mode == "hold":
            holds.append(item)
        elif mode in ("new", "rereview", "replies"):
            lanes.append(item)
        elif reason:
            skipped.append({"pr": f"{repo}#{n}", "reason": reason})

    lanes = order_lanes(lanes)
    work, deferred = lanes[:CAP], lanes[CAP:]
    for item in work:
        os.makedirs(item["dir"], exist_ok=True)
        with open(os.path.join(item["dir"], "lane.json"), "w", encoding="utf-8") as fh:
            json.dump(item, fh, indent=1)
    out = {"run_dir": run, "at": now().isoformat(), "lanes": work, "reapprove": reapprove, "holds": holds,
           "deferred": deferred,
           "skipped": skipped, "outside": sorted(set(filter(None, outside))), "errors": errors}
    with open(os.path.join(run, "discover.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"discover: {len(work)} lanes, {len(reapprove)} re-approvals, {len(holds)} holds, "
          f"{len(deferred)} deferred, {len(skipped)} skipped, {len(errors)} errors -> {run}/discover.json")
    for i in work:
        print(f"  lane {i['repo']}#{i['n']} {i['mode']}: {i['reason']} ({len(i.get('threads') or [])} threads)")
    for i in reapprove:
        print(f"  re-approve {i['repo']}#{i['n']}: {i['reason']}")
    for i in holds:
        print(f"  hold {i['repo']}#{i['n']}: {i['reason']}")
    for e in errors:
        print(f"  error: {e}")
    return 0


# ---------- before posting ----------

def cmd_check_head(a):
    base = f"repos/{OWNER}/{a.repo}"
    pull = gh_api(f"{base}/pulls/{a.pr}")
    if pull.get("state") != "open":
        print(f"stop: {a.repo}#{a.pr} is {pull.get('state')}{' (merged)' if pull.get('merged') else ''}")
        return 1
    if pull["head"]["sha"] != a.head:
        print(f"stop: head moved from {a.head[:9]} to {pull['head']['sha'][:9]}")
        return 1
    if a.kind == "review":
        reviews = gh_api(f"{base}/pulls/{a.pr}/reviews?per_page=100", paginate=True)
        done = [r for r in reviews if (r.get("user") or {}).get("login") == ME
                and r.get("commit_id") == a.head and r.get("state") in ("APPROVED", "CHANGES_REQUESTED")]
        if done:
            print(f"stop: he already has a {done[-1]['state']} review at this head ({done[-1].get('html_url')})")
            return 1
    print("ok")
    return 0


# ---------- texts for tighten ----------

def lane_texts(d):
    """(label, text, setter) for every drafted text in a lane folder, in a fixed order."""
    out = []
    pay = os.path.join(d, "payload.json")
    if os.path.isfile(pay):
        p = read_json(pay)
        out.append(("body", p.get("body") or "", ("payload", "body", None)))
        for i, c in enumerate(p.get("comments") or []):
            out.append((f"comment {i} {c.get('path')}:{c.get('line')}", c.get("body") or "", ("payload", "comment", i)))
    for f in sorted(os.listdir(d)):
        m = re.fullmatch(r"reply-(\d+)\.json", f)
        if m:
            r = read_json(os.path.join(d, f))
            out.append((f"reply {m.group(1)}", r.get("body") or "", ("reply", f, None)))
    return out


def cmd_export_text(a):
    d = os.path.abspath(a.dir)
    parts = [f"<!-- pr-sweep:{label} -->\n{text.strip()}\n" for label, text, _ in lane_texts(d)]
    with open(os.path.join(d, "texts.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))
    print(f"exported {len(parts)} texts to {d}/texts.md")
    return 0


def section_key(label):
    """"body", "comment 3" or "reply 123": the part of a label that names its draft."""
    parts = label.split(" ")
    return "body" if parts[0] == "body" else " ".join(parts[:2])


def cmd_import_text(a):
    d = os.path.abspath(a.dir)
    src = read_text(os.path.join(d, "texts.md"))
    marks = list(MARK_RE.finditer(src))
    got = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(src)
        got[section_key(m.group(1))] = src[m.end():end].strip()
    want = lane_texts(d)
    pay_path = os.path.join(d, "payload.json")
    pay = read_json(pay_path) if os.path.isfile(pay_path) else None
    replies, problems = {}, []
    for label, old, (kind, field, idx) in want:
        key = section_key(label)
        if key not in got:
            problems.append(f"section '{label}' is missing from texts.md")
            continue
        new = got[key]
        if kind == "payload" and field == "body":
            pay["body"] = new
            continue
        if not new:
            problems.append(f"{label} is empty")
        if kind == "payload":
            light = next((l for l in LIGHTS if old.startswith(l)), None)
            if light and not new.startswith(light):
                problems.append(f"{label} lost its opening '{light}'")
            pay["comments"][idx]["body"] = new
        else:
            replies[field] = new
    extra = set(got) - {section_key(label) for label, _, _ in want}
    if extra:
        problems.append("texts.md has sections no draft has: " + ", ".join(sorted(extra)))
    if problems:
        print("import refused, nothing written:\n  " + "\n  ".join(problems))
        return 1
    if pay is not None:
        with open(pay_path, "w", encoding="utf-8") as fh:
            json.dump(pay, fh, ensure_ascii=False, indent=1)
    for f, body in replies.items():
        with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
            json.dump({"body": body}, fh, ensure_ascii=False)
    print(f"imported {len(want)} texts into {d}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lock")
    sub.add_parser("unlock")
    p = sub.add_parser("discover")
    p.add_argument("--run-dir", required=True)
    p = sub.add_parser("check-head")
    p.add_argument("--repo", required=True, choices=REPOS)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--head", required=True)
    p.add_argument("--kind", choices=("review", "reply"), default="review")
    p = sub.add_parser("record")
    p.add_argument("--repo", required=True, choices=REPOS)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--head", required=True)
    p.add_argument("--outcome", required=True, choices=("posted", "held", "nothing"))
    p.add_argument("--reason")
    p.add_argument("--seen")
    p.add_argument("--mode", choices=("new", "rereview", "reapprove", "replies", "hold"))
    for name in ("export-text", "import-text"):
        p = sub.add_parser(name)
        p.add_argument("dir")
    a = ap.parse_args(argv)
    fn = {"lock": cmd_lock, "unlock": cmd_unlock, "discover": cmd_discover, "check-head": cmd_check_head,
          "record": cmd_record, "export-text": cmd_export_text, "import-text": cmd_import_text}[a.cmd]
    return fn(a)


if __name__ == "__main__":
    sys.exit(main())
