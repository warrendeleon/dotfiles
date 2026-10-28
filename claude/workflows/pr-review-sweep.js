export const meta = {
  name: 'pr-review-sweep',
  description: 'Review lanes for the hourly PR sweep: coverage, draft, tighten, gate and decide for each PR; returns what to post and what to hold, and posts nothing',
  whenToUse: 'Run by the pr-review-sweep scheduled task after `pr-sweep.py discover`. args: {lanes: [the lanes array of discover.json]}. Each lane is new, rereview or replies. Returns one result per lane with the exact post commands; the task posts them. Launch by scriptPath: ~/Developer/dotfiles/claude/workflows/pr-review-sweep.js.',
  phases: [
    { title: 'Coverage', detail: 'worktree at head: changed-line coverage, revert test, targeted mutations' },
    { title: 'Draft', detail: 'review payload and thread replies: ACs, edge cases, coverage gaps' },
    { title: 'Tighten', detail: 'tighten.md over every drafted text' },
    { title: 'Gate', detail: 'pr-review-check: checker, fixer, pr-check.sh receipt' },
    { title: 'Decide', detail: 'post, post with edits, or hold' },
  ],
}

const GATE = '/Users/warrendeleon/Developer/dotfiles/claude/workflows/pr-review-check.js'
const SWEEP = '/Users/warrendeleon/Developer/dotfiles/claude/hooks/pr-sweep.py'
const CLONES = '/Users/warrendeleon/Developer/news.co.uk'
const lanes = (args && args.lanes) || []
if (!lanes.length) return []
const tag = p => `${p.repo}#${p.n}`

const NEVER = `You never post, comment, reply, push, edit, resolve, approve or transition anything on GitHub or Jira: read through gh and curl only. Never @mention anyone, never mention AI, never thank or praise a bot. Your final text is data for the next stage, not a message to a person.`

const COVERAGE = {
  type: 'object',
  properties: {
    ran: { type: 'boolean' },
    reason: { type: 'string', description: 'why it did not run, or empty' },
    source_files: { type: 'array', items: { type: 'string' } },
    uncovered_lines: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, lines: { type: 'string' } }, required: ['file', 'lines'] } },
    revert: { type: 'object', properties: { applies: { type: 'boolean' }, failing_tests: { type: 'array', items: { type: 'string' } }, caught: { type: 'boolean' } }, required: ['applies', 'failing_tests', 'caught'] },
    mutations: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, line: { type: 'integer' }, change: { type: 'string' }, caught: { type: 'boolean' }, test: { type: 'string' } }, required: ['file', 'line', 'change', 'caught', 'test'] } },
    gaps: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, line: { type: 'integer' }, light: { type: 'string', enum: ['red', 'yellow'] }, text: { type: 'string' } }, required: ['file', 'line', 'light', 'text'] } },
    worktree_removed: { type: 'boolean' },
  },
  required: ['ran', 'reason', 'source_files', 'uncovered_lines', 'revert', 'mutations', 'gaps', 'worktree_removed'],
}

const DRAFT = {
  type: 'object',
  properties: {
    payload_path: { type: 'string', description: 'the payload.json written, or empty when no review is posted (replies lanes)' },
    head_sha: { type: 'string' },
    proposed_event: { type: 'string', enum: ['APPROVE', 'REQUEST_CHANGES', 'NONE'] },
    red: { type: 'integer' }, yellow: { type: 'integer' }, green: { type: 'integer' },
    ac_results: { type: 'array', items: { type: 'object', properties: { ac: { type: 'string' }, result: { type: 'string', enum: ['met', 'partly', 'not-met', 'not-checkable'] }, where: { type: 'string' } }, required: ['ac', 'result', 'where'] } },
    edge_cases: { type: 'array', items: { type: 'object', properties: { case: { type: 'string' }, handled: { type: 'boolean' }, tested: { type: 'boolean' }, light: { type: 'string', enum: ['red', 'yellow', 'none'] } }, required: ['case', 'handled', 'tested', 'light'] } },
    replies: { type: 'array', items: { type: 'object', properties: {
      reply_to: { type: 'integer' },
      verdict: { type: 'string', enum: ['answer', 'none', 'dispute-author-right', 'dispute-holds'] },
      reason: { type: 'string' },
      file: { type: 'string', description: 'the reply-<id>.json written for an answer, else empty' },
    }, required: ['reply_to', 'verdict', 'reason', 'file'] } },
    dropped_as_overlap: { type: 'array', items: { type: 'string' } },
    open_points_by_others: { type: 'array', items: { type: 'string' } },
    decisions_pending: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['payload_path', 'head_sha', 'proposed_event', 'red', 'yellow', 'green', 'ac_results', 'edge_cases', 'replies', 'dropped_as_overlap', 'open_points_by_others', 'decisions_pending', 'summary'],
}

const TIGHT = {
  type: 'object',
  properties: {
    words_before: { type: 'integer' }, words_after: { type: 'integer' },
    inventory_kept: { type: 'integer' }, inventory_total: { type: 'integer' },
    imported: { type: 'boolean', description: 'pr-sweep.py import-text exited 0' },
    notes: { type: 'string' },
  },
  required: ['words_before', 'words_after', 'inventory_kept', 'inventory_total', 'imported', 'notes'],
}

const DECISION = {
  type: 'object',
  properties: {
    action: { type: 'string', enum: ['post', 'hold', 'nothing'] },
    edited: { type: 'boolean', description: 'true if you changed any file' },
    edits: { type: 'array', items: { type: 'string' } },
    keep_files: { type: 'array', items: { type: 'string' }, description: 'absolute paths of payload.json and reply-<id>.json files to post' },
    hold_reason: { type: 'string' },
    note: { type: 'string', description: 'one line for the run summary: what goes out, or why it is held' },
  },
  required: ['action', 'edited', 'edits', 'keep_files', 'hold_reason', 'note'],
}

// ---------- prompts ----------

const laneFacts = p => `PULL REQUEST: newsuk/${p.repo}#${p.n} "${p.title}" by ${p.author}${p.draft ? ' (a draft)' : ''}, ${p.url}
HEAD: ${p.head} on base ${p.base}. Size: +${p.size.additions} -${p.size.deletions} in ${p.size.files} files.
TICKET: ${p.key || 'none found'}${p.ticket_type ? ` (${p.ticket_type})` : ''}
MODE: ${p.mode} (${p.reason})
${p.last_review ? `WARREN'S LAST REVIEW: ${p.last_review.state}${p.last_review.dismissed_from ? ` (was ${p.last_review.dismissed_from})` : ''} at ${p.last_review.commit_id} on ${p.last_review.submitted_at}, ${p.last_review.url || ''}` : "WARREN HAS NOT REVIEWED IT"}
FOLDER: ${p.dir} (lane.json there holds all of this, with the threads)`

const coveragePrompt = p => `${NEVER}

You measure how well the tests of one pull request cover its change, so the review can ask for the tests it lacks. Above all for a bug: a test must fail if the fix is reverted, so the bug cannot come back unseen.

${laneFacts(p)}
CLONE: ${CLONES}/${p.repo}. Other sessions use it: never check out, reset, stash, clean or commit in it. Work only in ${p.dir}.
${p.mode === 'rereview' ? `
RE-REVIEW: first list the non-test source files whose own changes moved between ${p.last_review.commit_id} and the head (compare each against its merge base with origin/${p.base}, so merges from main do not count). If none changed behaviour (only tests, docs, comments or formatting), return ran=false with reason "no behaviour change since the last review" and stop. Otherwise measure only those files.
` : ''}
1. WORKTREE.
   git -C ${CLONES}/${p.repo} fetch --quiet --no-write-fetch-head origin +refs/heads/${p.base}:refs/remotes/origin/${p.base} refs/pull/${p.n}/head
   git -C ${CLONES}/${p.repo} worktree add --detach ${p.dir}/wt ${p.head}
   Dependencies: when ${CLONES}/${p.repo}/node_modules exists and \`git -C ${CLONES}/${p.repo} show ${p.head}:package-lock.json | cmp -s - ${CLONES}/${p.repo}/package-lock.json\` succeeds, symlink it: ln -s ${CLONES}/${p.repo}/node_modules ${p.dir}/wt/node_modules. Otherwise run \`HUSKY=0 npm ci --no-audit --no-fund\` in the worktree with a 600000 ms timeout. In a monorepo (nuk-cdn), work in the package the PR changes and read its package.json for the install and test commands. If dependencies cannot be installed, return ran=false with the reason, after step 6.
2. SOURCE. The non-test code the PR adds or changes: \`git -C ${p.dir}/wt diff --name-only $(git -C ${p.dir}/wt merge-base origin/${p.base} HEAD) HEAD\`, without tests, snapshots, mocks, docs, .agent files and lock files. Brand config under config/ counts when it changes behaviour. No source changed: ran=false, reason "no source change".
3. CHANGED-LINE COVERAGE. Run only the tests related to the changed source, with coverage limited to those files (read package.json and the jest or vitest config for the flags; in ncu-ad-manager, for example, \`TEST_THIRD_PARTY=false npx jest -c jest.config.js --ci --coverage --findRelatedTests <files> --collectCoverageFrom=<file>\`). From coverage/coverage-final.json, list each added or changed line no test runs.
4. REVERT TEST. For a Bug ticket, or a PR that says it fixes a bug or changes existing behaviour: put the base version of every changed source file back (\`git -C ${p.dir}/wt checkout <merge base> -- <files>\`) while keeping the PR's tests, run the related tests and record which fail, then \`git -C ${p.dir}/wt checkout HEAD -- <files>\`. caught=true when at least one fails. A new file has no base version: its tests count as catching the revert only if they fail when the file's behaviour is removed, which step 5 shows.
5. TARGETED MUTATIONS. Up to six on the changed source, each one a reviewer would expect a test to catch: flip a condition, drop a guard, return early, remove a call, change a constant, drop a field such as a bidders list or an ID. Apply each alone with an exact edit, run the related tests, record caught or not and which test caught it, then \`git -C ${p.dir}/wt checkout HEAD -- <file>\` before the next. Never leave a mutation in place.
6. CLEAN UP. \`git -C ${CLONES}/${p.repo} worktree remove --force ${p.dir}/wt\`, then confirm it is gone from \`git -C ${CLONES}/${p.repo} worktree list\`.
7. GAPS, each on an added or changed line (file path and line number in the file at the head):
   - red: a Bug ticket where no test fails on the revert; new behaviour with no test at all.
   - yellow: a mutation no test catches; an uncovered changed line or branch that matters; an edge case the code handles that no test pins (null or empty input, a boundary, an error or timeout path, consent declined, a brand with and without the feature, first visit and returning reader).
   Leave out what nobody would test: logging, types, re-exports, constants with no logic. Each gap's text says what is untested, why it matters to a reader or a brand, and which test to add, in one or two plain sentences of British English.
Write the result as JSON to ${p.dir}/coverage.json too.`

const reviewPrompt = (p, cov) => `${NEVER}

You draft Warren de León's GitHub review of one pull request (he is Principal Engineer, Commercial Technology, News UK) and, where needed, his answers in his own review threads. A decider reads your drafts next and they may be posted with no one else reading them, so every claim must hold against the code at the head.

${laneFacts(p)}
After each numbered step append one line to ${p.dir}/progress.log, e.g. echo "$(date +%H:%M) step 2 context read" >> ${p.dir}/progress.log

1. WRITING RULES. Read ~/.wiki/personal/writing/writing-guides.md, then every guide its "Code review on GitHub" row names, and its "Reply to a review comment on GitHub" row. Every sentence follows them: British English, plain short words, subject first, no em-dash joining clauses, none of the banned words.

2. CONTEXT, read-only through gh; never check a branch out in a shared clone.
- \`gh pr view ${p.n} --repo newsuk/${p.repo} --json title,body,author,isDraft,headRefOid,baseRefName,files,commits\` and \`gh pr diff ${p.n} --repo newsuk/${p.repo}\` (if GitHub refuses the whole diff, read each file's patch from \`gh api repos/newsuk/${p.repo}/pulls/${p.n}/files --paginate\`).
- A file at head: \`gh api "repos/newsuk/${p.repo}/contents/<path>?ref=${p.head}" --jq .content | base64 -d\`; with ref=${p.base} for the base.
- The ticket and its acceptance criteria: \`set -a; . ~/.secrets.env; set +a; curl -s -G -u "$JIRA_EMAIL:$JIRA_TOKEN" "https://\${JIRA_SITE#https://}/rest/api/3/issue/${p.key || '<key>'}" --data-urlencode fields=summary,description,issuetype\`.
- The repo's review rules: every file in .agent/instructions at ${p.base} (\`gh api "repos/newsuk/${p.repo}/contents/.agent/instructions?ref=${p.base}"\`), plus .github/copilot-instructions.md and CONTRIBUTING.md if they exist.
- Everything already said on the PR, by people and bots: \`gh api repos/newsuk/${p.repo}/pulls/${p.n}/reviews --paginate\`, \`.../pulls/${p.n}/comments --paginate\`, \`gh api repos/newsuk/${p.repo}/issues/${p.n}/comments --paginate\`.
${p.mode === 'rereview' ? `
RE-REVIEW. Read all of Warren's earlier reviews and inline comments. For each change he asked for, check at the head whether it is done. Read what changed since his last review: \`gh api repos/newsuk/${p.repo}/compare/${p.last_review.commit_id}...${p.head}\` (ignore what came in from ${p.base}). Never restate an earlier comment of his. New inline findings only on code changed since his last review, or on something his earlier reviews did not cover.
` : ''}${p.mode === 'replies' ? `
REPLIES ONLY. Warren has already reviewed this head. Do not write payload.json and do not review the code afresh: only judge the threads in step 6. proposed_event is NONE.
` : ''}
3. COVERAGE. The coverage stage measured the tests at the head:
${JSON.stringify(cov || { ran: false, reason: 'not measured in this mode' })}
Carry its gaps into the review as inline comments on their lines (red gaps are 🔴, yellow gaps are 🟡), merged with your own findings so one line never gets two comments. Check each gap against the code before you use it. If it did not run, read the tests yourself: a Bug ticket with no test that pins the fix, or new behaviour with no test, is still a 🔴.

4. REVIEW${p.mode === 'replies' ? ' (skip in replies mode)' : ''}. A reading review: do not run the code.
- Acceptance criteria: take them one by one from the ticket and decide from the code whether each is met. An unmet criterion is a 🔴 on the line that should meet it, or one body line when it has no line.
- Edge cases: work out the cases the changed code paths and the brand configs it reaches can meet (empty, missing or malformed input; a boundary; an error or timeout; consent not given; a brand with and without the feature or on Prebid Server; first visit and returning reader; order and timing). A case the code mishandles, so that a reader or a brand breaks, is a 🔴. A case it handles that no test covers is a 🟡, merged with the coverage gaps.
- Also: correctness bugs in the changed lines, breaches of the repo's own rules, misleading names, dead code, magic numbers, loose types.
- Raise only what the code as written shows. A fault on a line this PR did not add or change is not this change's: leave it out unless it is serious, and then put it under a body heading "### Carried over". Steelman the author's choice before any 🔴. No suggestions to change .agent docs. Fewer, sharper comments: help the author fix things without overwhelming them.

5. NO OVERLAP. Leave out every point a colleague or Copilot already made on this PR, fixed or not, and list it in dropped_as_overlap. Do not restate a colleague's open blocking point; list it in open_points_by_others.

6. THREADS. For each thread in lane.json "threads", read the whole thread, the code it is about at the head, and the commits since. Decide one verdict:
- answer: the author asks Warren something, or says a point is fixed when the head does not contain the fix. Write ${p.dir}/reply-<reply_to>.json as {"body": "..."}: one short paragraph that answers the question, or says what is still missing and where (file and line at the head). No opener, no thanks to a bot, at most one plain "Thanks," to a person whose comment led to a change.
- none: "done" and the head confirms it, thanks, agreement, or anything that needs no answer. Most replies are this. Never reply only to have the last word.
- dispute-author-right: the author disagrees with Warren's comment and the code, or a fact you can check, shows they are right. No reply. In a re-review, drop that point.
- dispute-holds: the author disagrees and the code does not support their reason, or you cannot tell. No reply; this holds the PR for Warren.
In replies mode, any dispute is dispute-holds, because only a review can withdraw a change request.

7. PAYLOAD${p.mode === 'replies' ? ' (skip in replies mode)' : ''}. Write ${p.dir}/payload.json, the body for \`gh api repos/newsuk/${p.repo}/pulls/${p.n}/reviews --input\`:
{"commit_id": "${p.head}", "event": "APPROVE" or "REQUEST_CHANGES", "body": "...", "comments": [{"path": "...", "line": N, "side": "RIGHT", "body": "..."}, {"path": "...", "start_line": A, "start_side": "RIGHT", "line": B, "side": "RIGHT", "body": "..."}]}
- Every line and start_line is a line number in the file at the head that sits inside a hunk of the diff. Take it from the file at head, never by counting from a hunk header.
- Each comment starts with exactly one of "🟢 **Good:**", "🟡 **Suggestion:**", "🔴 **Change requested:**", then says what the code does, why it matters and what to change, once, usually in two to four sentences. A plain fenced code block only when showing the fix is clearer than describing it. No \`\`\`suggestion blocks.
- At most one 🟢, and only when it tells the author something worth keeping.
- event: REQUEST_CHANGES if any 🔴, or a colleague's blocking point is still open at the head; otherwise APPROVE. Never COMMENT.
- body: for REQUEST_CHANGES one short line that repeats nothing inline (when an earlier point of Warren's is still open, say so and let the thread reply carry the detail; when the only reason is a colleague's open point, link that comment). For APPROVE an empty string unless the author needs one line the comments do not give.
- Never in the text: how the review was done ("checked", "verified", "ran", "I read", "mutation", "coverage run"), severity tags, the event name, a Recommendation heading, any mention of AI.
- Validate with \`python3 -m json.tool ${p.dir}/payload.json\`.

8. PROOFREAD every sentence you wrote, in the payload and the replies: subject first; the plain word; nothing said twice; nothing the author does not need. Edit the files.

9. Return the structured result. decisions_pending holds anything you could not settle from the code: a scope or product question, a judgement call, a doubt about a finding.`

const tightenPrompt = p => `${NEVER}

You shorten the drafted review texts of newsuk/${p.repo}#${p.n} without losing anything. Folder: ${p.dir}.

1. Run \`python3 ${SWEEP} export-text ${p.dir}\`. It writes ${p.dir}/texts.md: every drafted text (the review body, each inline comment, each thread reply) under its own marker line.
2. Read ~/Developer/dotfiles/claude/commands/tighten.md and follow its steps 1 to 5 on ${p.dir}/texts.md exactly: back up, inventory, cut, gate (content-inventory.py, inbound-quotes.py, writing-lint.py) and read the original against the edit.
   Also keep: every \`<!-- pr-sweep:... -->\` marker line exactly as it is; each inline comment's opening traffic light ("🟢 **Good:**", "🟡 **Suggestion:**" or "🔴 **Change requested:**") as its first words; code blocks, file paths, line numbers, identifiers and links byte for byte. An empty section stays empty. Add no section.
3. Run \`python3 ${SWEEP} import-text ${p.dir}\`; it must exit 0. If it refuses, fix texts.md and run it again, at most twice. If it still refuses, copy your backup over texts.md and run it once more, so the drafts are left as they were.
4. Return the words before and after, the inventory kept and total, whether the import succeeded, and anything you restored.`

const gateNotes = p => `Rules for this review, from Warren. payload.json is a gh api reviews payload; keep it valid JSON. Its event is APPROVE or REQUEST_CHANGES only, never COMMENT: any 🔴 means REQUEST_CHANGES, and so does a colleague's blocking point still open at the head. No \`\`\`suggestion blocks. Nothing may repeat or overlap a comment a colleague or Copilot already left on this PR (read gh api repos/newsuk/${p.repo}/pulls/${p.n}/comments, /reviews and issues/${p.n}/comments): overlap is a style finding whose correction is delete. Every inline line and start_line must sit inside a diff hunk on the RIGHT side at commit_id. Never @mention anyone. Each reply-<id>.json is Warren's answer in an existing thread, {"body": "..."}: it follows the "Reply to a review comment on GitHub" row of the writing guides (one short paragraph, no traffic light, no thanks to a bot), and every claim in it must hold at the head.`

const decidePrompt = (p, cov, draft, gate, tight) => `${NEVER}

You decide what goes out for newsuk/${p.repo}#${p.n}. Warren has given a standing go for this sweep: what you pass is posted with no one reading it first. Pass what is right and needed; hold what he would want to see.

${laneFacts(p)}

DRAFTER'S RESULT: ${JSON.stringify(draft)}
COVERAGE: ${JSON.stringify(cov || { ran: false })}
TIGHTEN: ${JSON.stringify(tight || { skipped: true })}
GATE: ${gate ? JSON.stringify({ clean: gate.clean, findings: gate.findings, fix: gate.fix, receipt: gate.receipt && { exit_code: gate.receipt.exit_code, output: gate.receipt.output } }) : 'not run'}

Read ${p.dir}/payload.json and every ${p.dir}/reply-*.json, the PR diff (\`gh pr diff ${p.n} --repo newsuk/${p.repo}\`) and the threads in ${p.dir}/lane.json. Then:
1. Re-read the code behind every 🔴 and every reply. A 🔴 you cannot confirm from the code is cut or turned into a 🟡; if the review then has no 🔴, the event becomes APPROVE.
2. Drop any reply that only acknowledges, thanks, agrees or has the last word. Keep one only when a question to Warren needs an answer or a claimed fix is not at the head.
3. Hold the whole PR when any of these is true:
   - the drafter left a decision you cannot settle from the code (decisions_pending);
   - a thread verdict is dispute-holds;
   - a 🔴 rests on a product, scope or priority call rather than on what the code does;
   - a gate finding on a file you keep was not fixed (the gate's fixer skipped it, or you cannot correct it from the code). A receipt that failed only because of a file you drop is not a reason to hold: the files you keep are gated again before anything is posted;
   - you are not sure the review is right.
4. Otherwise post. You may edit: cut a comment, a sentence or a reply, correct a fact against the code, make the event follow the lights. Never add a finding; if one that matters is missing, hold. Keep the JSON valid and every traffic light in place. List each edit.
5. Nothing to post (no payload and no reply left): action "nothing". Also "nothing" when Warren already has an APPROVED or CHANGES_REQUESTED review at ${p.head} (\`gh api repos/newsuk/${p.repo}/pulls/${p.n}/reviews --paginate\`): he reviewed it while this run was drafting, and a second review would repeat his.
Return keep_files as absolute paths, chosen from ${p.dir}/payload.json and ${p.dir}/reply-<id>.json. note is one line for Warren's run summary: what goes out (event and counts), or why it is held.`

// ---------- the lanes ----------

const files = draft => [draft.payload_path, ...draft.replies.filter(r => r.verdict === 'answer' && r.file).map(r => r.file)].filter(Boolean)
const runGate = async (p, fileList) => {
  try {
    return await workflow({ scriptPath: GATE }, { repo: `newsuk/${p.repo}`, pr: p.n, files: fileList, notes: gateNotes(p) })
  } catch (e) {
    log(`${tag(p)}: gate failed: ${e.message}`)
    return null
  }
}
const command = (p, file) => {
  const reply = file.match(/reply-(\d+)\.json$/)
  if (!reply) return `gh api repos/newsuk/${p.repo}/pulls/${p.n}/reviews --input ${file} --jq '.html_url'`
  const thread = (p.threads || []).find(t => String(t.reply_to) === reply[1])
  if (thread && thread.kind === 'issue') return `gh api repos/newsuk/${p.repo}/issues/${p.n}/comments --input ${file} --jq '.html_url'`
  return `gh api repos/newsuk/${p.repo}/pulls/${p.n}/comments/${reply[1]}/replies --input ${file} --jq '.html_url'`
}
const seen = p => (p.threads || []).flatMap(t => t.comment_ids)
const result = (p, extra) => ({ pr: tag(p), repo: p.repo, n: p.n, head: p.head, mode: p.mode, dir: p.dir, seen: seen(p), posts: [], hold_reason: '', note: '', ...extra })

const results = await pipeline(
  lanes,
  p => p.mode === 'replies' ? null
    : agent(coveragePrompt(p), { label: `coverage ${tag(p)}`, phase: 'Coverage', schema: COVERAGE, effort: 'medium' }),
  async (cov, p) => {
    const draft = await agent(reviewPrompt(p, cov), { label: `draft ${tag(p)}`, phase: 'Draft', schema: DRAFT, effort: 'high' })
    if (!draft) throw new Error(`no draft for ${tag(p)}`)
    return { cov, draft }
  },
  async (r, p) => {
    if (!files(r.draft).length) return { ...r, tight: null }
    const tight = await agent(tightenPrompt(p), { label: `tighten ${tag(p)}`, phase: 'Tighten', schema: TIGHT, effort: 'high' })
    return { ...r, tight }
  },
  async (r, p) => {
    const list = files(r.draft)
    return { ...r, gate: list.length ? await runGate(p, list) : null }
  },
  async (r, p) => {
    const disputes = r.draft.replies.filter(x => x.verdict === 'dispute-holds')
    if (!files(r.draft).length && !disputes.length && !r.draft.decisions_pending.length) {
      log(`${tag(p)}: nothing to post (${r.draft.replies.length} thread replies judged, none needed)`)
      return result(p, { action: 'nothing', note: `${r.draft.replies.length} thread replies need no answer` })
    }
    const d = await agent(decidePrompt(p, r.cov, r.draft, r.gate, r.tight), { label: `decide ${tag(p)}`, phase: 'Decide', schema: DECISION, effort: 'high' })
    if (!d) return result(p, { action: 'hold', hold_reason: 'the decider did not return', draft: r.draft })
    // The receipt must cover exactly what is posted: gate again after an edit, a dropped file or an unclean first pass.
    let gate = r.gate
    const gated = files(r.draft)
    const same = gated.length === d.keep_files.length && gated.every(f => d.keep_files.includes(f))
    if (d.action === 'post' && d.keep_files.length && (d.edited || !gate || !gate.clean || !same)) gate = await runGate(p, d.keep_files)
    if (d.action === 'post' && !(gate && gate.clean)) {
      log(`${tag(p)}: held, the receipt is not clean`)
      return result(p, { action: 'hold', hold_reason: "the pr-check receipt is not clean after the decider's edits", note: d.note, draft: r.draft, decision: d })
    }
    if (d.action === 'post' && !d.keep_files.length) d.action = 'nothing'
    const posts = d.action === 'post' ? d.keep_files.map(f => ({ file: f, command: command(p, f) })) : []
    log(`${tag(p)}: ${d.action}${d.action === 'hold' ? ` (${d.hold_reason})` : ''}: ${d.note}`)
    return result(p, { action: d.action, posts, hold_reason: d.hold_reason, note: d.note, draft: r.draft, decision: d, coverage: r.cov, tighten: r.tight })
  },
)

return results.map((r, i) => r || result(lanes[i], { action: 'hold', hold_reason: 'a stage failed; see the workflow journal' }))
