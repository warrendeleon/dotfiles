#!/bin/bash
# Regression checks for consent-gate.sh: feed it a transcript and a tool call,
# and compare allow (no output) or deny (a JSON decision) with the expectation.
set -uo pipefail
HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/consent-gate.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fails=0

# check <name> <expect allow|deny> <command> <human turn>...
check() {
  local name=$1 expect=$2 cmd=$3; shift 3
  local transcript="$TMP/$name.jsonl"
  : > "$transcript"
  for turn in "$@"; do
    python3 -c 'import json,sys;print(json.dumps({"type":"user","message":{"role":"user","content":sys.argv[1]}}))' "$turn" >> "$transcript"
  done
  local out
  out=$(python3 -c 'import json,sys;print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]},"transcript_path":sys.argv[2]}))' "$cmd" "$transcript" | "$HOOK")
  local got=allow
  [ -n "$out" ] && got=deny
  if [ "$got" = "$expect" ]; then echo "ok   $name"; else echo "FAIL $name: expected $expect, got $got"; fails=$((fails + 1)); fi
}

PR='gh pr create --draft --title x --body-file b.md'
check create-go            allow "$PR" "Create the PR first"
check create-then-followup allow "$PR" "Create the PR first" "Follow writing-guides.md don't forget"
check open-go              allow "$PR" "open the PR"
check no-go                deny  "$PR" "what does the PR template say?"
check negated-create       deny  "$PR" "don't create the PR yet"
check veto-after-go        deny  "$PR" "Create the PR first" "don't post anything"
check close-go             allow "gh pr close 1 --comment x" "Close PR explain why. Unasign the Jira ticket, move it to the correct column"
check negated-close        deny  "gh pr close 1" "don't close the PR"
check push-go              allow "git push origin x" "push it"
check numbered-go          allow "gh pr edit 1 --body-file b.md" "Do 2-3"
check numbered-both-go     allow "gh pr edit 1 --body-file b.md" "do both"
check numbered-negated     deny  "gh pr edit 1 --body-file b.md" "don't do 2 yet"
check do-as-question       deny  "gh pr edit 1 --body-file b.md" "what do you think?"

# "Don't forget to <verb>" is a reminder to act, not a veto (5 Oct, PR #3412 Copilot thread).
REPLY='gh api -X POST repos/o/r/pulls/1/comments/2/replies --input /tmp/r.json'
check dont-forget-reply    allow "$REPLY" "Don't forget to reply to the comment and resolve it. Following writing-guides.md"
check do-not-forget-post   allow "$REPLY" "do not forget to post it"
check dont-reply-veto      deny  "$REPLY" "don't reply to that comment"
check resolve-go           allow "gh api graphql -f query=x" "resolve the thread"

# Standing go: rerun only the failed jobs of a CircleCI workflow (5 Oct, SCB-6338 flaky e2e).
RERUN_URL='https://circleci.com/api/v2/workflow/972c00a3-8b78-4b52-94c2-1069149805b3/rerun'
RERUN="curl -s -X POST -H \"Circle-Token: \$CIRCLE_TOKEN\" -H \"Content-Type: application/json\" -d '{\"from_failed\": true}' \"$RERUN_URL\""
check circle-rerun          allow "$RERUN" "what's the status?"
check circle-rerun-env      allow "set -a; . ~/.secrets.env; set +a; $RERUN" "status?"
check circle-rerun-all      deny  "${RERUN/from_failed\": true/from_failed\": false}" "status?"
check circle-approve        deny  "curl -s -X POST -H \"Circle-Token: \$CIRCLE_TOKEN\" \"https://circleci.com/api/v2/workflow/972c00a3-8b78-4b52-94c2-1069149805b3/approve/3e170d71-f0f1-40db-882f-72f5a2b5d072\"" "status?"
check circle-rerun-chained  deny  "$RERUN && git push origin main" "status?"
check circle-rerun-veto     deny  "$RERUN" "don't rerun anything"
# Standing go: post a receipted review payload in the PR-review workflow (20 Oct, "You decided what to publish").
RV='gh api repos/newsuk/ncu-ad-manager/pulls/3472/reviews --input /private/tmp/x/payload.json'
check review-post-standing   allow "$RV" "Review all six, same procedure as before."
check review-post-jq         allow "$RV --jq '\"\\(.id) \\(.state)\"'" "Review this one: https://github.com/newsuk/ncu-ad-manager/pull/3272"
check review-post-assets     allow "${RV/ncu-ad-manager/ncu-commercial-assets}" "Peter need a review on 226"
check review-post-no-ask     deny  "$RV" "what's the status?"
check review-post-veto       deny  "$RV" "Review all six" "don't post anything yet"
check review-post-cdn        allow "${RV/ncu-ad-manager/nuk-cdn}" "Review all six"
check review-post-other-repo deny  "${RV/ncu-ad-manager/ncu-commercial-ads-txt}" "Review all six"
check review-post-comments   deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3472/comments --input /private/tmp/x/payload.json" "Review all six"
check review-post-chained    deny  "$RV && git push origin main" "Review all six"
# "Hit the release" is a go for the production approval (5 Oct, #3413).
APPROVE='curl -s -X POST -H "Circle-Token: $CIRCLE_TOKEN" "https://circleci.com/api/v2/workflow/x/approve/y"'
check release-go            allow "$APPROVE" "3413 was merged. When you can, hit the release"
check release-veto          deny  "$APPROVE" "don't release it yet"
check release-go-earlier    allow "$APPROVE" "3413 was merged. When you can, hit the release" "which one should be merged next?" "Did you find what was wrong with the failing test?" "So apparently it is because the video is not present" "or something like that"
check release-later-veto    deny  "$APPROVE" "When you can, hit the release" "which one next?" "actually don't release it" "status?"

# "No need just approve it" is a go for the approval; "no need to push" is still a veto (5 Oct, #3423).
check no-need-just-approve  allow "gh pr review 3423 --approve" "No need just approve it"
check no-need-comma-just    allow "gh pr review 3423 --approve" "no need, just approve it"
check no-need-to-push-veto  deny  "git push origin x" "no need to push it"

# The MF companion's private staging repo is a standing go (4 Oct 2026): main and a post tag
# pass with no go in the message; origin, chaining, a forced main and a veto do not.
C="git -C /Users/warrendeleon/Developer/warrendeleon/react-native-module-federation"
check staging-main         allow "$C push staging main" "lock it when Codex finds nothing"
check staging-tag          allow "$C push -f staging refs/tags/post-17-signing-rollback" "lock it"
check staging-origin       deny  "$C push origin main" "lock it"
check staging-chained      deny  "$C push staging main && $C push origin main" "lock it"
check staging-force-main   deny  "$C push -f staging main" "lock it"
check staging-other-repo   deny  "git -C /tmp/x push staging main" "lock it"
check staging-veto         deny  "$C push staging main" "don't push anything"

# Polite requests are imperatives; questions about an edit are not (2 Oct, SCB-6314).
PUT='curl -s -X PUT --data @d.json https://nidigitalsolutions.jira.com/rest/api/3/issue/SCB-1'
check can-you-edit         allow "$PUT" "Can you edit them all up with the corrected values?"
check can-you-edit-follow  allow "$PUT" "Can you edit them all up with the corrected values?" "Check that all tickets are correct."
check could-you-please-fix allow "$PUT" "could you please fix the table"
check can-you-explain-fix  deny  "$PUT" "can you explain how to fix this?"
check fix-as-noun          deny  "$PUT" "how difficult is the fix?"

# curl -G sends -d/--data as the query string of a GET, so it is a read (8 Oct, SCB-6401 JQL search).
JQL="https://nidigitalsolutions.jira.com/rest/api/3/search/jql"
check get-data-urlencode    allow "curl -s -u \"\$A\" -G \"$JQL\" --data-urlencode 'jql=parent=SCB-5989' --data-urlencode 'fields=summary'" "Can you check if this is ready for development?"
check get-long-flag         allow "curl -s --get \"$JQL\" -d 'jql=key=SCB-1'" "status?"
check get-combined-flag     allow "curl -sG \"$JQL\" --data-urlencode 'jql=key=SCB-1'" "status?"
check get-with-post         deny  "curl -s -G -X POST \"$JQL\" -d 'x=1'" "status?"
check get-with-json         deny  "curl -s -G --json '{}' \"$JQL\"" "status?"
check plain-data            deny  "curl -s -d 'x=1' \"$JQL\"" "status?"
check get-then-post         deny  "curl -s -G \"$JQL\" -d 'a=1' && curl -s -d 'b=2' \"$JQL\"" "status?"

# Standing go for one scheduled task: the first turn is the <scheduled-task> block.
SCHED='<scheduled-task name="rebase-scb-6272-triplelift" file="x">Keep the branch rebased.</scheduled-task>'
OTHER='<scheduled-task name="some-other-task" file="x">Do things.</scheduled-task>'
W='git -C ~/Developer/news.co.uk/.worktrees/ncu-ad-manager-SCB-6272'
B='feat/SCB-6272-triplelift-parent-id-news-uk'
SHA=0c1eed3094fa9dde7d605ac62779793aee9acec6
check sched-push            allow "$W push --force-with-lease=$B:$SHA origin $B" "$SCHED"
check sched-push-abs        allow "git -C /Users/warrendeleon/Developer/news.co.uk/.worktrees/ncu-ad-manager-SCB-6272 push --force-with-lease=$B:$SHA origin $B 2>&1" "$SCHED"
check sched-bare-lease      deny  "$W push --force-with-lease origin $B" "$SCHED"
check sched-plain-force     deny  "$W push --force origin $B" "$SCHED"
check sched-other-branch    deny  "$W push --force-with-lease=main:$SHA origin main" "$SCHED"
check sched-chained         deny  "$W push --force-with-lease=$B:$SHA origin $B && git push origin main" "$SCHED"
check sched-gh-write        deny  "gh pr reopen 3392" "$SCHED"
check other-task-push       deny  "$W push --force-with-lease=$B:$SHA origin $B" "$OTHER"
check human-not-standing    deny  "$W push --force-with-lease=$B:$SHA origin $B" "what's the status?"

# Standing go for the hourly PR review sweep (28 Oct): only its own receipted files, to the PR and thread they name.
SW='<scheduled-task name="pr-review-sweep" file="x">Review the PRs.</scheduled-task>'
RUN=/Users/warrendeleon/.claude/pr-review-sweep/runs/20261028-1300
J="--jq '.html_url'"
check sweep-review          allow "gh api repos/newsuk/ncu-ad-manager/pulls/3482/reviews --input $RUN/ncu-ad-manager-3482/payload.json $J" "$SW"
check sweep-reply           allow "gh api repos/newsuk/ncu-ad-manager/pulls/3482/comments/4281601281/replies --input $RUN/ncu-ad-manager-3482/reply-4281601281.json $J" "$SW"
check sweep-issue-reply     allow "gh api repos/newsuk/nuk-cdn/issues/8060/comments --input $RUN/nuk-cdn-8060/reply-77.json $J" "$SW"
check sweep-assets          allow "gh api repos/newsuk/ncu-commercial-assets/pulls/228/reviews --input $RUN/ncu-commercial-assets-228/payload.json $J" "$SW"
check sweep-other-pr        deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3481/reviews --input $RUN/ncu-ad-manager-3482/payload.json $J" "$SW"
check sweep-other-thread    deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3482/comments/1/replies --input $RUN/ncu-ad-manager-3482/reply-2.json $J" "$SW"
check sweep-other-repo      deny  "gh api repos/newsuk/ncu-commercial-ads-txt/pulls/5/reviews --input $RUN/ncu-commercial-ads-txt-5/payload.json $J" "$SW"
check sweep-outside-folder  deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3482/reviews --input /tmp/x/ncu-ad-manager-3482/payload.json $J" "$SW"
check sweep-new-comment     deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3482/comments --input $RUN/ncu-ad-manager-3482/reply-1.json $J" "$SW"
check sweep-chained         deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3482/reviews --input $RUN/ncu-ad-manager-3482/payload.json $J && git push origin main" "$SW"
check sweep-merge           deny  "gh pr merge 3482 --repo newsuk/ncu-ad-manager" "$SW"
check sweep-other-task      deny  "gh api repos/newsuk/ncu-ad-manager/pulls/3482/comments/4281601281/replies --input $RUN/ncu-ad-manager-3482/reply-4281601281.json $J" "$OTHER"

# Standing go for the SCB-6338 sub-task branches (2 Oct), whatever the latest turn says.
VW='git -C /Users/warrendeleon/Developer/news.co.uk/.worktrees/ncu-ad-manager-SCB-6310'
VB='feat/SCB-6310-talksport-xandr-config-update'
check batch-push            allow "$VW push -u origin $VB" "why is the review taking so long?"
check batch-lease           allow "$VW push --force-with-lease=$VB:$SHA origin $VB" "what's the status?"
check batch-pr              allow "gh pr create --repo newsuk/ncu-ad-manager --base main --head $VB --title 'feat(SCB-6310): map Talksport Xandr placement IDs per ad slot' --body-file /tmp/pr-SCB-6310.md --label talksport --label enhancement" "status?"
check batch-other-key       deny  "$VW push -u origin feat/SCB-6311-something" "status?"
check batch-mixed-keys      deny  "${VW/6310/6313} push -u origin $VB" "status?"
check batch-not-in-list     deny  "git -C /Users/warrendeleon/Developer/news.co.uk/.worktrees/ncu-ad-manager-SCB-6272 push -u origin feat/SCB-6272-x" "status?"
check batch-main            deny  "$VW push origin main" "status?"
check batch-plain-force     deny  "$VW push --force origin $VB" "status?"
check batch-chained         deny  "$VW push -u origin $VB && git push origin main" "status?"
check batch-pr-draft        allow "gh pr create --repo newsuk/ncu-ad-manager --base main --head $VB --draft --title 'feat(SCB-6310): x' --body-file /tmp/pr-SCB-6310.md --label talksport --label enhancement" "status?"
check batch-pr-other-repo  deny  "gh pr create --repo newsuk/other --base main --head $VB --title 'x' --body-file /tmp/b.md --label talksport" "status?"
check batch-pr-no-label     deny  "gh pr create --repo newsuk/ncu-ad-manager --base main --head $VB --title 'x' --body-file /tmp/b.md" "status?"
check batch-pr-merge        deny  "gh pr merge 1 --squash" "status?"
check batch-veto            deny  "$VW push -u origin $VB" "don't push anything"
check batch-lease-mismatch  deny  "$VW push --force-with-lease=feat/SCB-6310-other:$SHA origin $VB" "status?"

exit $fails
