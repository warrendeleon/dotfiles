export const meta = {
  name: 'review-loop',
  description: 'Check every claim in a deliverable against its source of truth once, fix what is confirmed wrong, re-check the ledger after the fixes, then write a verification receipt',
  whenToUse: 'Before a long document or blog post goes out. Not for pull request reviews: those use hooks/pr-check.sh, one deterministic pass. args: {profile: "delivery" | "baseline" | "blog", targets: [paths], outputs?: [built files], repo?: path, notes?: string, decisions?: [author framings the loop must not touch], maxRounds?: number (default 3, or 2 in re-check mode), models?: {oracle, find, recheck, confirm, fix, receipt}, efforts?: {same keys}}. Defaults: oracle sonnet/low, find opus/high, recheck sonnet/medium, confirm opus/medium, fix opus/medium, receipt haiku/low. Round 1 discovers and returns a claim ledger; later rounds re-derive only the ledger entries the edits touched and read only the edited passages, never the whole document, so the finding supply is bounded and the loop ends. Duplicate findings from different critics on the same defect are merged before confirmation, so one confirmer rules and the fixer gets one correction. Findings marked unsupported or weak go straight to forAuthor without a confirm agent; only wrong, inconsistent and rule findings are confirmed and fixed. Refuted findings are carried across rounds and runs so critics do not raise them again. Re-check rounds use ONE agent for every claim type (args.recheckPerType: true restores one per type). After hand edits, pass ledgerFile (from hooks/ledger-from-run.py on the last run; it carries the refuted list too) and edits [{file, before, after}] to skip discovery: the first re-check round is 1 oracle + 1 re-check + one confirm per wrong finding + 1 fix; later rounds skip the oracle because the fixer re-runs the verifiers; then 1 receipt. About five agents when the edits are sound. Rule findings are confirmed on Sonnet; the numeric critic trusts the deterministic verifier for the figures it covers and re-derives only the rest. Run ONE loop at a time; parallel loops hit the session limit and the dead agents still cost their tokens. Launch by scriptPath (~/Developer/dotfiles/claude/workflows/review-loop.js), not by name: the name resolves to a copy cached at session start. Say the model plan and the expected agent count to the user before launching. Lock gate (on for the blog profile, args.gate for others): once a round confirms nothing, one fresh Opus agent reads every target whole, plus the profile\'s gate scope (for a blog post, the companion\'s changed files and README), lists every fault with no cap and returns READY or NOT READY; NOT READY findings are confirmed and fixed in the same round and the loop goes on, so a clean result means the gate said READY. For a blog post pass args.startRef and args.endRef (the companion\'s start and end points) so the oracle replays the file steps and the companion critic reads the changed files. A clean receipt is still not a lock: say what it covered.',
  phases: [
    { title: 'Oracles', detail: 'deterministic checks: verifier scripts, builds, banned-word and link sweeps' },
    { title: 'Find', detail: 'round 1 only: fresh-context critics, one per claim type, returning a ledger of every claim checked' },
    { title: 'Re-check', detail: 'later rounds: the ledger entries the fixes touched, plus the edited passages' },
    { title: 'Confirm', detail: 'an independent agent tries to refute each finding' },
    { title: 'Fix', detail: 'confirmed findings applied by hand, then rebuilt' },
    { title: 'Gate', detail: 'once the loop converges: a fresh whole-document read that must return READY before the run counts as clean' },
    { title: 'Receipt', detail: 'verification receipt written for the hook that gates outward actions' },
  ],
}

// ---------------------------------------------------------------- profiles
// The loop is generic. A profile names the source of truth, the deterministic
// checks, the claim types a critic is assigned to, and the house rules the
// fixer must keep. Add a case by adding a profile, not a workflow.

const PROFILES = {
  delivery: {
    name: 'delivery documents',
    sources: `
- SQLite database: ~/Developer/newsuk-delivery/delivery.sqlite. Open it read-only: sqlite3 -readonly, or the URI file:...?mode=ro.
- Schema and starter queries: ~/.wiki/raw/news-uk/team/delivery-2026-09/README.md and the scripts under ~/Developer/newsuk-delivery/scripts/.
- Working set (markdown): one page per engineer at ~/.wiki/news-uk/team/people/<name>/<name>-delivery-baseline-2026-09.md, and the round's index and method under ~/.wiki/news-uk/team/rounds/delivery-baseline-2026-09/. Reports (HTML source): ~/.wiki/raw/news-uk/team/delivery-2026-09/report/report.html and report-long.html; built copies under _build/.
- Definitions that hold everywhere: working days exclude weekends, England bank holidays and recorded leave. Only In Progress time is counted; Blocked and With third party are outside the clock. Completion comes from the status changelog because resolutiondate is empty. Estimated time is the top of the range for a size (1pt=1d, 2=2, 3=5, 5=10, 8=20). "Substantive" is a text heuristic defined in the documents. Hand-written lines are added plus deleted lines with lockfiles, minified bundles, build output, vendored code, snapshots and source maps left out.`,
    oracles: `
Run from ~/Developer/newsuk-delivery, in this order, and report each exit status and every FAIL line:
1. python3 scripts/build_charts.py
2. python3 scripts/build_report.py && python3 scripts/build_report.py --long
3. python3 scripts/verify_page.py
4. python3 scripts/verify_report.py
5. python3 scripts/verify_all_pages.py
6. Name sweep on report.html and report-long.html: any personal name other than "Bruce Thomas", "Warren de Leon" and "Ovidiu Bokar" is a failure. Check first names and surnames separately.
7. Wording sweep on every target: the words machine, automated, automatic, classifier, generated, model, algorithm, script (as in "a script found") used about how the document was produced are failures; "AI Assistant" as the epic's name and "the board's agent" are allowed.
8. Link sweep on the HTML targets: every SCB-#### key and every pull request number in the prose must be inside an <a class="lnk"> element, and each must exist in the database (jira_issue.key, pull_request.repo + number).
Read the whole output of each command. A verifier that prints OK lines and exits 0 is a pass for the claims it covers and says nothing about the rest.`,
    claimTypes: [
      { key: 'numeric', brief: 'Every number, percentage, rank, range, count, date and duration in the prose, tables and chart data attributes. The deterministic stage already re-derived every figure its verifier names; audit that verifier once (read what it checks and re-derive five of its figures yourself), then spend your effort on the figures it does NOT cover, re-deriving each from the database with a query you write yourself. A figure the document rounds is checked against the same rounding.' },
      { key: 'existence', brief: 'Every ticket key, pull request, file path, epic, repository and quoted comment. Confirm it exists, belongs to the person the sentence implies, carries the properties claimed (points, days, status, dates, size), and that quotations match the stored text word for word.' },
      { key: 'attribution', brief: 'Every statement about who did, wrote, moved, estimated, reviewed or assigned something. Check the changelog author, comment author, reviewer login or assignee history. "Recorded by a colleague" must be a colleague; "he" must be the subject.' },
      { key: 'inference', brief: 'Every sentence that explains, dismisses, attributes cause, or generalises: "explains", "accounts for", "because", "so", "rules out", "does not", "survives", "holds", "nothing on record". For each, name the measurement in the document that would have to support it, and report it as unsupported when the measurement is absent or measures something else (a keyword match is not a cause; a lower frequency is not a smaller effect).' },
      { key: 'consistency', brief: 'The same quantity stated in two places must agree: within a target, across the targets, and between each target and the working paper. Build a table of every quantity that appears more than once and diff it. Include chart data attributes against prose and tables.' },
    ],
    rules: `
- The HTML reports name nobody but Bruce Thomas, Warren de Leon and Ovidiu Bokar. Colleagues appear as ranks, ranges, counts or roles.
- No wording that implies how the document was produced (see the wording sweep). Only the epic name "AI Assistant" and "the board's agent" may appear.
- Every cited ticket, pull request or comment is a clickable <a class="lnk"> link in the HTML.
- A qualification sits beside the figure it qualifies, never in a separate section.
- A causal or dismissive claim names the measurement that supports it, or is reworded to what the data shows.
- British English, plain words, no em-dash used to stitch clauses.
- Edit by hand with exact-string edits. Never mass-replace by script.
- After edits, rebuild (build_charts, build_report, build_report --long) and re-run the three verifiers; if a verifier regex no longer matches reworded prose, repoint the regex, never weaken the check.`,
  },

  baseline: {
    name: 'performance review baseline',
    sources: `
- SQLite database, the frozen 14 September 2026 build: ~/Developer/newsuk-delivery/review/delivery-2026-09-14.sqlite. Open it from Python with sqlite3.connect("file:...?mode=ro&immutable=1", uri=True); the sqlite3 CLI cannot open it. build_meta holds the snapshot (2026-09-14T23:59). Bruce Thomas's two editions and the eight other reports all draw on this build.
- Definitions and every derived figure: ~/Developer/newsuk-delivery/scripts/measures.py (per-person measures, team ranks, ranges, the 90-day quarter, the review-wait figures). The eight reports are assembled by scripts/build_person_report.py from review/narrative/<id>.json; each narrative's "literals" map states the source of every bare number in its prose. Bruce Thomas's editions are hand-written HTML: report.html and report-long.html under ~/.wiki/raw/news-uk/team/delivery-2026-09/report/, checked by scripts/verify_report.py.
- Hand readings (comment quality, code audits, scope classifications) come from the working pages at ~/.wiki/news-uk/team/people/<name>/<name>-delivery-baseline-2026-09.md, which describe the same 14 September 2026 build as the reports. A hand-read claim the report carries forward is checked against the page and, where the database can show it, against the database.
- The video architecture record in Bruce Thomas's reverts section also rests on Slack. Export: ~/Developer/slack-scraper/output/history-T0692QH4Z-U0BSYT9KZN0.sqlite3, table messages(channel, ts, body JSON with user, text, thread_ts). Threads: G014RH4CNQ0 from ts 1767890533.721369 (8 January 2026), GK2SAUPAQ messages of 8 January 2026 14:00 to 17:30 and of 7 to 8 July 2026, G010EACHKGB from ts 1783419349.271329 (7 July 2026), D0C134SC30Q ts 1789392782.174199 (14 September 2026). Times in the export are UTC; the report gives London time. Slack user ids: U05CY77GFUG is Bruce Thomas, U06PTE90SQ7 the colleague who coordinates releases, WGMT45RUG is Ovidiu Bokar, U03E8AETGBT and U05KHMNK95M are the data team, U067F2E6BJN the delivery lead, U056LG7S8DR and U06ETF6R084 are engineering colleagues.
- Definitions that hold everywhere: working days exclude weekends, England bank holidays and recorded leave. Only In Progress time is counted; Blocked and With third party are outside the clock. Completion comes from the status changelog. Estimated time is the top of the range for a size (1pt=1d, 2=2, 3=5, 5=10, 8=20). "Substantive" is a text heuristic. Hand-written lines are added plus deleted lines with lockfiles, minified bundles, build output, vendored code, snapshots and source maps left out. Team ranges and ranks are across the eight engineers with a substantial record; Fragkiskos Katsimpas is left out of every range.
- Writing conventions: ~/.wiki/personal/writing/writing-guides.md and, for prose, the guides it numbers 1, 2, 3, 5, 6 and 7 in ~/.wiki/personal/writing/.`,
    oracles: `
Run from ~/Developer/newsuk-delivery, in this order, and report each exit status and every FAIL line:
1. If a target is report.html or report-long.html: python3 scripts/build_charts.py && python3 scripts/build_report.py && python3 scripts/build_report.py --long, then python3 scripts/verify_report.py (must end "Every figure checked matches"), then REPORT_HTML=$HOME/.wiki/raw/news-uk/team/delivery-2026-09/report/_build/report-long.html python3 scripts/verify_report.py, where lines reading "nothing matches" are summary-edition wordings absent from the long edition and are expected; every other FAIL is a failure.
2. If a target is review/narrative/<id>.json: cd scripts && python3 -c "import build_person_report as B; B.build('<id>')" then python3 scripts/verify_person_report.py <id> (must end "clean").
3. Name sweep on the report HTML: any personal name, first name, surname, Jira display name or GitHub login other than the subject's own, "Warren de Leon" and "Ovidiu Bokar" is a failure.
4. Wording sweep on every target: the words machine, automated, automatic, classifier, generated, model, algorithm, script (as in "a script found") used about how the document was produced are failures; "AI Assistant" as the epic's name, "the board's agent" and "the automated reviewer" for the review bot are allowed. Also sweep for the avoid-list in ~/.wiki/personal/writing/ai-writing-gotchas.md and for em-dashes in prose; em-dashes inside table rows of the form "term — definition" and inside quoted comments are exempt.
5. Link sweep on the HTML: every SCB-#### key and every pull request number in the prose must be inside an <a class="lnk"> element, and each must exist in the database (jira_issue.key, pull_request.repo + number).
Read the whole output of each command. A verifier that prints OK lines and exits 0 is a pass for the claims it covers and says nothing about the rest.`,
    claimTypes: [
      { key: 'numeric', brief: 'Every number, percentage, rank, range, count, date and duration in the prose, tables and chart data attributes. The deterministic stage already re-derived every figure its verifier names (verify_report.py for the two Bruce Thomas editions, verify_person_report.py and the literals map for the eight reports); audit that verifier once (read what it checks and re-derive five of its figures yourself with the definitions in measures.py), then spend your effort on the figures it does NOT cover, re-deriving each from the database with a query you write yourself. A figure the document rounds is checked against the same rounding. For the eight reports, a bare number in the narrative must match the source its literals entry names.' },
      { key: 'existence', brief: 'Every ticket key, pull request, file path, epic, repository, quoted comment and quoted Slack message. Confirm it exists, belongs to the person the sentence implies, carries the properties claimed (points, days, status, dates, size, reviewers, times), and that quotations match the stored text word for word.' },
      { key: 'attribution', brief: 'Every statement about who did, wrote, moved, merged, reverted, estimated, reviewed, approved, asked or assigned something, and every time interval between two events. Check the changelog author, comment author, reviewer login, assignee history, pull request timestamps and Slack authorship and timestamps. "A colleague" must be a colleague; "he" or "she" must be the subject; a stated number of minutes or days must follow from the timestamps.' },
      { key: 'inference', brief: 'Every sentence that explains, dismisses, attributes cause, or generalises: "explains", "accounts for", "because", "so", "rules out", "does not", "survives", "holds", "nothing on record", "reads as". For each, name the measurement or record in the document that would have to support it, and report it as unsupported when the measurement is absent or measures something else (a keyword match is not a cause; a lower frequency is not a smaller effect).' },
      { key: 'consistency', brief: 'The same quantity stated in two places must agree: within a target, between the summary and full editions of Bruce Thomas\'s report, between each report and the cover, stats block, tables and chart data attributes, and between the eight reports where they quote the same team figure (ranges, ranks, the review-wait figures, the sources paragraph). Build a table of every quantity that appears more than once and diff it.' },
      { key: 'style', brief: 'Read every sentence of prose against ~/.wiki/personal/writing/writing-guides.md and the guides it numbers 1, 2, 3, 5, 6 and 7: subject first, no personified abstractions, no decorative tails, no restated points; the avoid-list words and expressions and the near-zero em-dash rule; steelman before disagreeing, hedge non-absolutes, name decisions as decisions; qualifications beside the figure they qualify; a skimmable bold on decision points; no positional references invalidated by later edits. Quote each violating sentence with the rule it breaks. A choice of words that breaks no stated rule is not a finding.' },
    ],
    rules: `
- Each report names nobody but its subject, Warren de Leon and Ovidiu Bokar. Colleagues appear as ranks, ranges, counts or roles. Bruce Thomas may be named only in his own editions.
- No wording that implies how the document was produced. Only the epic name "AI Assistant", "the board's agent" and "the automated reviewer" may appear.
- Every cited ticket, pull request or comment is a clickable <a class="lnk"> link in the HTML.
- A qualification sits beside the figure it qualifies, never in a separate section. No agenda, limitations or open-questions section.
- A causal or dismissive claim names the measurement that supports it, or is reworded to what the data shows.
- British English, plain words, the avoid-list, no em-dash used to stitch clauses.
- Edit by hand with exact-string edits. Never mass-replace by script.
- For the eight reports edit review/narrative/<id>.json (keeping its literals map complete), never report-<id>.html, then rebuild with build_person_report.build('<id>') and re-run verify_person_report.py. For Bruce Thomas's editions edit report.html and report-long.html, keeping both in step, then rebuild with build_report.py and build_report.py --long and re-run verify_report.py on both; if a verifier regex no longer matches reworded prose, repoint the regex, never weaken the check.
- The video architecture record is written from Slack timestamps and GitHub; a correction to it must cite the message or record it rests on.`,
  },
  blog: {
    name: 'blog post',
    gate: true,
    gateScope: 'the companion\'s teaching surface: every explanatory comment in the files the post copies or changes (git diff between args.startRef and args.endRef in args.repo) and the README section for this post',
    sources: `
- The post files given as targets, and the companion repository in args.repo at the branch or commit the post names (args.startRef to args.endRef when given).
- The companion's teaching surface is part of the deliverable: every explanatory comment in the files the post copies or changes, and the README section for this post. A comment that contradicts the code or the article is a finding, returned to the author because the fixer does not edit the companion.
- Library behaviour is checked against the installed source under node_modules or the vendor's documentation, not from memory.
- Writing conventions: ~/.wiki/personal/writing/writing-guides.md and the guides it names for a blog post; ~/.wiki/personal/writing/ai-writing-gotchas.md; ~/.wiki/personal/writing/plain-sentence-construction.md.
- Animated demos: the frame-by-frame gate in the wiki page blog-publishing-pipeline.`,
    oracles: `
1. Replay the post's file steps: clone args.repo into a temporary directory, check out the start point (args.startRef, or the tag the post starts from), apply every copy command, typed edit and deletion the post gives, in order (where the post fetches the end point from the network, use git archive on the end point from args.repo instead), then diff the tree against the end point (args.endRef). Every difference is a failure unless the notes name it as expected.
2. Run every other command the post tells the reader to run that can run here, in order, against a clean checkout at the stated point, and report any that fail or print output that differs from what the post shows. Never run a command the notes say rotates keys, writes tracked files or needs a device; report it as not run.
3. Banned-word, em-dash and idiom sweep against ai-writing-gotchas.md; quote each hit with its line.
4. Every link resolves (HEAD request or file exists); every image and demo file referenced exists.
5. If the post has an animated demo, decode the composed frames and check continuity and every tap ring against the control it marks.`,
    claimTypes: [
      { key: 'code', brief: 'Every code block, file path, command and identifier. Confirm it matches the companion repository at the stated point character for character, or is clearly marked as an excerpt. Run what can be run.' },
      { key: 'behaviour', brief: 'Every statement about what a library, tool, platform, API or the companion\'s own code does. Verify it against the installed source or the vendor documentation and quote the line that supports it. Then test the claim\'s general form, not only the case the post demonstrates: list the cases the sentence covers (each platform, build type, launch mode, failure kind, input and timing it names or implies), follow the code path for each, and report every case the code handles differently. A sentence that holds for the demo but is wider than the code is wrong. When reading cannot settle a library behaviour, run a small read-only probe against the installed source. Report anything that rests on memory.' },
      { key: 'narrative', brief: 'Every scenario, anecdote, demo step and "you will see" prediction. Reproduce it where it can run here; otherwise check it against the recorded evidence the notes name. Walk the demos in article order and track the state each one leaves behind (servers running or stopped, files moved, maps or config edited, builds made): a step that depends on a state an earlier step changed, with no instruction to restore it, is wrong. A framing that cannot be reproduced or found in the record is fabricated and must be reported.' },
      { key: 'style', brief: 'Read every sentence and paragraph against writing-guides.md and the guides its reading profile names for a blog post. Check at least: the subject first, and named again after a code block or digression; no idiom or figurative phrase (state the literal meaning); the avoid-list words and expressions; near-zero em-dashes in prose; one mechanism or decision per paragraph, a second causal chain starting a new paragraph; no inserted sentence that interrupts an explanation; no positional references; no closing recap that repeats the body; steelman before disagreeing; decisions named as decisions; acronyms spelled out on first use; no self-deprecating hook; series navigation and cross-references correct. A breach of a stated rule is a rule finding even when the fix is a change of words. Quote each violating sentence with the guide and the rule it breaks.' },
      { key: 'consistency', brief: 'Version numbers, file names, step numbers and figures must agree across the post and with the companion repository and the other posts in the series it links to. So must every promise the frontmatter description, the diagrams, the tables and the closing make: each must say no more than the body and the code support.' },
      { key: 'companion', brief: 'The companion\'s teaching surface: every explanatory comment in the files the post copies or changes (git diff between args.startRef and args.endRef in args.repo, or the tags the post names) and the README section for this post. Each comment must agree with the code at the end point and with the article: a comment that describes an earlier implementation, generalises past the code, or contradicts the article is a finding. Quote it with its file and line. The fixer does not edit the companion, so these return to the author under skipped.' },
    ],
    rules: `
- Copy-paste build-alongs must run as written; fix the post or the companion repository, and say which.
- Keep the author's content; do not cut sections on judgement. A cut is a finding for the user, not an edit.
- British English, plain words, the ai-writing-gotchas avoid-list, near-zero em-dashes in prose.
- Never publish or push from this loop; edit the draft only.`,
  },
}

// ---------------------------------------------------------------- schemas

const ORACLE_SCHEMA = {
  type: 'object',
  properties: {
    ran: { type: 'array', items: { type: 'object', properties: { command: { type: 'string' }, exit: { type: 'integer' }, summary: { type: 'string' } }, required: ['command', 'exit', 'summary'] } },
    failures: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string' }, location: { type: 'string' }, expected: { type: 'string' }, got: { type: 'string' }, source: { type: 'string' } },
      required: ['claim', 'location', 'expected', 'got', 'source'] } },
  },
  required: ['ran', 'failures'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    claims_checked: { type: 'integer' },
    ledger: { type: 'array', description: 'every claim of this type that was checked and passed, so a later round can re-check the same list instead of discovering afresh; group a table into one entry per column when one query covers it', items: { type: 'object', properties: {
      claim: { type: 'string', description: 'short quote or label' },
      location: { type: 'string' },
      check: { type: 'string', description: 'the query or command that settles it' },
    }, required: ['claim', 'location', 'check'] } },
    findings: { type: 'array', items: { type: 'object', properties: {
      claim: { type: 'string', description: 'the exact quoted sentence or cell' },
      location: { type: 'string', description: 'file:line, or file and table caption' },
      status: { type: 'string', enum: ['wrong', 'unsupported', 'weak', 'inconsistent', 'rule'] },
      evidence: { type: 'string', description: 'the query or command run and what it returned' },
      correction: { type: 'string', description: 'what the sentence should say, or "reword" with the reason' },
    }, required: ['claim', 'location', 'status', 'evidence', 'correction'] } },
  },
  required: ['claims_checked', 'ledger', 'findings'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    confirmed: { type: 'boolean' },
    evidence: { type: 'string', description: 'your own independent derivation, with the command and its output' },
    fix: { type: 'string', description: 'the exact replacement text or edit, if confirmed' },
    reason: { type: 'string' },
  },
  required: ['confirmed', 'evidence', 'reason'],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    applied: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, before: { type: 'string' }, after: { type: 'string' } }, required: ['file', 'before', 'after'] } },
    skipped: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, reason: { type: 'string' } }, required: ['claim', 'reason'] } },
    rebuilt: { type: 'boolean' },
    verifiers: { type: 'string', description: 'exit status and OK/FAIL counts of every verifier re-run' },
  },
  required: ['applied', 'skipped', 'rebuilt', 'verifiers'],
}

// The lock gate's answer: every fault it found, in the critics' shape, and its verdict.
const GATE_SCHEMA = {
  type: 'object',
  properties: {
    findings: FINDINGS_SCHEMA.properties.findings,
    verdict: { type: 'string', enum: ['READY', 'NOT READY'] },
    reason: { type: 'string' },
  },
  required: ['findings', 'verdict', 'reason'],
}

const RECEIPT_SCHEMA = {
  type: 'object',
  properties: { path: { type: 'string' }, written: { type: 'boolean' }, note: { type: 'string' } },
  required: ['path', 'written', 'note'],
}

// ---------------------------------------------------------------- prompts

// What counts as wrong. Without this every round finds something to call wrong in a
// long document, and the loop never ends.
const MATERIALITY = `WHAT COUNTS AS A FINDING. Status "wrong" is reserved for a claim where the reader would take away a different number, name, date, count, rank, direction or attribution than the source gives, under the document's own definitions. These are NOT wrong and must not be reported: a figure rounded within the precision the document uses; a quotation shortened with an ellipsis or square brackets that keeps its meaning; a choice of words, emphasis or order that breaks no stated rule; anything the AUTHOR DECISIONS list covers; a claim already carrying its own qualification; a difference that comes from applying a definition other than the document's. "inconsistent" is for the same quantity given two values. "rule" is for a house rule or a writing-guide rule broken, including a rule about wording (an idiom, a paragraph carrying two mechanisms, a positional reference): a breach of a stated rule is a finding even when the fix is a change of words. "unsupported" and "weak" are for reasoning the evidence does not carry; report them, but they go to the author, not the fixer.`

const header = (P, targets, narrow) => `You are one stage of a review loop for a ${P.name}. The deliverable will be challenged by the people it affects, so treat every claim as wrong until you have re-derived it yourself.

TARGETS${narrow ? ' (do NOT read these in full; this stage names the exact passages to read)' : ' (read each in full before anything else)'}:
${targets.map(t => '- ' + t).join('\n')}

SOURCES OF TRUTH:${P.sources}
${args.repo ? `\nREPOSITORY: ${args.repo}${args.startRef ? `, start point ${args.startRef}` : ''}${args.endRef ? `, end point ${args.endRef}` : ''}\n` : ''}
${args.notes ? 'NOTES FROM THE USER:\n' + args.notes + '\n' : ''}${(args.decisions || []).length ? 'AUTHOR DECISIONS, NOT UNDER REVIEW. These framings are the author\'s deliberate choices. Do not report them, do not reword them, do not add material that argues against them:\n' + args.decisions.map(d => '- ' + d).join('\n') + '\n' : ''}Your final text is data for the next stage, not a message to a person. Do not pad with confirmations. Do not edit any file unless this stage says so.`

// Findings an independent checker has already refuted, in this run or an earlier one.
// Listed to every critic so the same refuted finding is not raised, confirmed and refuted again.
const refutedBlock = refuted => (refuted.length || args.ledgerFile)
  ? `\nALREADY REFUTED. Each of these was reported before and an independent checker showed it was not a finding. Do not report them again, nor any variant of them (same passage, same rule, same quantity):\n${refuted.map(r => `- ${r.location}: ${r.claim}${r.reason ? ' :: refuted because ' + r.reason : ''}`).join('\n')}${args.ledgerFile ? `\n- also every entry under the "refuted" key of the ledger file ${args.ledgerFile}, if that key exists; read it before you start` : ''}\n`
  : ''

const oraclePrompt = (P, targets) => `${header(P, targets)}

STAGE: deterministic checks.${P.oracles}

Report every command you ran with its exit status and a one-line summary, and list every failure as a claim with its location, what was expected, what was found, and which source says so. A verifier that could not run is a failure, not a pass.`

const criticPrompt = (P, targets, ct, oracle, refuted) => `${header(P, targets)}

STAGE: find. You are the critic for one claim type only: ${ct.key}.
${ct.brief}

Method: list every claim of this type in every target, in order, with its location. Then check each one against the sources with a command or query you write and run yourself. The deterministic stage already ran the verifier scripts; their failures are known and listed below, so concentrate on what they do not cover. Return two things: the ledger of every claim that passed, each with the check that settled it, and the findings for every claim that failed. Quote each failing claim exactly, give the command and its output as evidence, and suggest the correction. Do not fix anything.

${MATERIALITY}
${refutedBlock(refuted)}
Already known from the deterministic stage:
${oracle.failures.length ? oracle.failures.map(f => `- ${f.location}: ${f.claim} (expected ${f.expected}, got ${f.got})`).join('\n') : '- nothing'}`

const clip = s => (s || '').replace(/\s+/g, ' ').slice(0, 150)
const inEdited = (entries, edits) => {
  const files = new Set(edits.map(e => (e.file || '').split('/').pop()).filter(Boolean))
  return entries.filter(l => [...files].some(f => (l.location || '').includes(f)))
}
const recheckPrompt = (P, targets, ct, ledger, delta, edits, oracle, refuted) => `${header(P, targets, true)}

STAGE: re-check. ${ct.key === 'all' ? 'You are the checker for every claim type; the types and what each covers:' : `You are the checker for one claim type only: ${ct.key}.`}
${ct.brief}

This is not a fresh review, and it is not a read of the document. An earlier round already listed every claim of this type and checked it; that ledger is below. Since then the passages listed under EDITS changed. Do exactly this and nothing else:
1. For each ledger entry, grep for its claim text at its location. If the text is still there and the location is outside every edited passage, the entry stands: do not open the passage, do not re-run its check, do not count it. Only an entry whose text is gone, or whose location falls inside an edited passage, is re-derived.
2. Read each edited passage (the "after" text and the paragraph around it, nothing more) and check every claim of this type it now contains, including claims that are new.
3. Report only failures, with the command and its output as evidence and the correction. In "ledger" return ONLY the entries you re-derived or added, not the whole ledger. Set claims_checked to the number you re-derived or added.
Reading either target in full, or re-running checks on entries that still stand, is a failure of this stage.

${MATERIALITY}
${refutedBlock(refuted)}
${typeof ledger === 'string'
  ? `LEDGER: read the entries ${ct.key === 'all' ? 'of every claim type' : `for type "${ct.key}"`} from the JSON file ${ledger} (an object keyed by claim type; each entry has claim, location, check). Consider only entries whose location is in a file named under EDITS; the rest stand.`
  : `LEDGER (${ledger.length} entries in the edited files; entries elsewhere stand and are not listed)\n${ledger.map(l => `- ${l.location}: ${l.claim} :: ${clip(l.check)}`).join('\n')}`}
${delta.length ? `\nENTRIES RE-DERIVED IN EARLIER ROUNDS OF THIS RUN (${delta.length}; these supersede the same entries above)\n${delta.map(l => `- ${l.location}: ${l.claim} :: ${clip(l.check)}`).join('\n')}\n` : ''}
EDITS SINCE THE LEDGER WAS MADE (${edits.length})
${edits.map(e => `- ${e.file}\n  before: ${e.before}\n  after:  ${e.after}`).join('\n')}

Already known from the deterministic stage:
${oracle.failures.length ? oracle.failures.map(f => `- ${f.location}: ${f.claim} (expected ${f.expected}, got ${f.got})`).join('\n') : '- nothing'}`

const confirmPrompt = (P, f) => `You are an independent checker for a ${P.name}. Another agent reported this finding. Your job is to refute it.

FINDING${f.merged ? ` (reported by ${f.merged} critics, ${f.type}; their evidence and corrections are listed in turn, and you return ONE fix that satisfies every part of the defect that holds)` : ''}
- claim: ${f.claim}
- location: ${f.location}
- status: ${f.status}
- their evidence: ${f.evidence}
- their correction: ${f.correction}

SOURCES OF TRUTH:${P.sources}

${(args.decisions || []).length ? 'AUTHOR DECISIONS, NOT UNDER REVIEW:\n' + args.decisions.map(d => '- ' + d).join('\n') + '\n' : ''}
${MATERIALITY}

Re-derive the fact yourself from the sources with your own command or query; do not rerun their command as your only step. If the original claim in the document is in fact correct under the document's own definitions, the finding is refuted. If you cannot reproduce their evidence, the finding is refuted. If the difference is one the list above says is not a finding, the finding is refuted. If the claim is wrong or unsupported and your own derivation shows it, confirm it and give the exact fix. A finding that cites a stated rule (the house rules or the writing guides) is confirmed when the text breaks that rule: "it is only a choice of words" does not refute a breach of a rule about words. Default to refuted when uncertain.`

const fixPrompt = (P, targets, confirmed) => `${header(P, targets)}

STAGE: fix. Apply every confirmed finding below to the targets, by hand, with exact-string edits. Then rebuild and re-run the deterministic checks. The list has already been merged: each entry is one defect with one fix. Where the same sentence appears in more than one target (the two editions), apply the same edit to each.

HOUSE RULES (all of them hold after your edits):${P.rules}

CONFIRMED FINDINGS
${confirmed.map((f, i) => `${i + 1}. [${f.status}] ${f.location}
   claim: ${f.claim}
   evidence: ${f.evidence}
   fix: ${f.fix || f.correction}`).join('\n')}

For each finding report the file, the exact text before and after. If a fix would break a house rule or contradict the sources, skip it and say why. After editing: rebuild, run every verifier the profile names, and report their exit status and counts. If a verifier's regex no longer matches your rewording, repoint the regex to the new wording and say so; never weaken what it checks.`

// The lock gate. The critics and re-checks are built to converge: a re-check reads only what
// the fixes touched, and each critic owns one claim type. A run that converged has therefore not
// had a fresh reader take in the whole deliverable after its fixes, which is what an outside
// review does (3 Oct 2026: two clean runs on blog post 16, then an outside whole-document review
// found 20, 12 and 6 more faults, among them claims wider than the code and stale comments in the
// companion the loop never read). The gate is that reader, and nothing counts as clean until it
// returns READY with nothing an independent checker can confirm.
const gatePrompt = (P, targets, refuted) => `${header(P, targets)}

STAGE: lock gate. The loop has converged: its critics found nothing more they could confirm. You are a fresh reader deciding whether the deliverable is ready to be locked. Read every target in full${P.gateScope ? `, then ${P.gateScope}` : ''}, and the writing guides the sources name. Then report every fault you find, however minor, with no limit on their number. Test each claim's general form against the sources, not only the case the deliverable demonstrates, and check that the description, diagrams, tables and closing promise no more than the body supports. For each fault give the exact quoted text, its location, the rule broken (the guide or house rule and its wording) or the evidence (file, line, what it says), a concrete correction, and a status.

${MATERIALITY}
${refutedBlock(refuted)}
Then give the verdict: READY only when you found no wrong, inconsistent or rule finding; NOT READY otherwise, with the reason. Do not answer any question in the user's notes: your verdict is data for the loop.`

const receiptPrompt = (P, targets, outputs, history, clean, refuted, refutedPath) => `You are the last stage of a review loop for a ${P.name}. Write the verification receipt.

Run exactly this command, replacing nothing else:

$HOME/Developer/dotfiles/claude/hooks/write-receipt.sh --profile ${JSON.stringify(P.name)} --clean ${clean ? 'true' : 'false'} --history '${JSON.stringify(history).replace(/'/g, "'\\''")}' ${[...targets, ...outputs].map(p => JSON.stringify(p)).join(' ')}

Then write the refuted-findings file for the next run, exactly this, replacing nothing:

cat > ${JSON.stringify(refutedPath)} <<'REFUTED_EOF'
${JSON.stringify({ refuted }, null, 1)}
REFUTED_EOF

Report the receipt path the first command printed, whether it wrote, and one line of note. Do nothing else.`

// ---------------------------------------------------------------- loop
//
// Round 1 discovers: every critic lists every claim of its type, checks each, and returns a
// ledger of what passed plus findings for what failed. Later rounds do not discover again:
// they re-check the ledger entries the fixes touched and read the edited passages. The
// finding supply is therefore bounded by the ledger, and the loop ends when one complete
// re-check round confirms nothing wrong, or at the round cap.

const P = PROFILES[args && args.profile]
if (!P) throw new Error(`unknown profile ${args && args.profile}; expected one of ${Object.keys(PROFILES).join(', ')}`)
const targets = (args.targets || []).filter(Boolean)
if (!targets.length) throw new Error('args.targets must list at least one file')
const outputs = (args.outputs || []).filter(Boolean)
const MAX_ROUNDS = args.maxRounds || (args.ledgerFile ? 2 : 3)
const CONFIRM_CAP = 16
// The lock gate runs once the loop converges: on for profiles that ask for it, or with args.gate.
const GATE = args.gate !== undefined ? !!args.gate : !!P.gate

// Model and effort per stage. The critics carry the quality of the whole loop and get the
// strongest default; re-checks re-run known queries on a few passages, so Sonnet; confirms
// and fixes stay on Opus because they decide what changes. Override any stage with
// args.models / args.efforts, e.g. {find: 'fable'}.
// Family aliases resolve to the current model in each family. Pinned version IDs retire and
// fail every agent at launch (28 Sep 2026: all eleven agents of a run failed on retired IDs).
const TIER = {
  oracle:  { model: 'sonnet', effort: 'low' },
  find:    { model: 'opus',   effort: 'high' },
  recheck: { model: 'sonnet', effort: 'medium' },
  confirm: { model: 'opus',   effort: 'medium' },
  confirmRule: { model: 'sonnet', effort: 'medium' },   // style and cross-reference findings
  fix:     { model: 'opus',   effort: 'medium' },
  gate:    { model: 'opus',   effort: 'high' },
  // Sonnet, not Haiku: on 3 Oct 2026 a Haiku receipt agent answered the user's question instead
  // of running its two commands, and no receipt was written.
  receipt: { model: 'sonnet', effort: 'low' },
}
for (const k of Object.keys(TIER)) {
  if (args.models && args.models[k]) TIER[k].model = args.models[k]
  if (args.efforts && args.efforts[k]) TIER[k].effort = args.efforts[k]
}
const tier = k => ({ model: TIER[k].model, effort: TIER[k].effort })
log(`models: ${Object.entries(TIER).map(([k, v]) => `${k} ${v.model}/${v.effort}`).join(', ')}; round 1 = 1 oracle + ${P.claimTypes.length} critics + one confirm per wrong finding (cap ${CONFIRM_CAP}) + 1 fix; later rounds re-derive only what the edits touched; up to ${MAX_ROUNDS} rounds`)

const key = f => `${f.location}|${(f.claim || '').replace(/\s+/g, ' ').trim().slice(0, 160)}`
const seen = new Set()
const history = []
const forAuthor = []
const ledgers = {}          // claim type -> ledger entries from the discovery round, or the ledger file path
const ledgerDelta = {}      // claim type -> entries re-derived or added in later rounds of this run
let edits = []              // every before/after the fixer applied, for the re-check rounds
let round = 0, clean = false, lastFix = null
// Refuted findings: from an earlier run (args.refuted, or the ledger file's "refuted" key,
// which hooks/ledger-from-run.py writes) plus every refutation in this run. Passed to every
// critic so the same finding is not raised, confirmed and refuted round after round.
const refuted = (args.refuted || []).map(r => ({ location: r.location, claim: r.claim, reason: r.reason }))
// Cheap re-check mode: a ledger from an earlier run (hooks/ledger-from-run.py) plus the
// edits made since. Discovery is skipped; the first round re-checks what the edits touched.
const LEDGER_FILE = args.ledgerFile || null
if (LEDGER_FILE) {
  for (const ct of P.claimTypes) ledgers[ct.key] = LEDGER_FILE
  edits = (args.edits || []).map(e => ({ file: e.file, before: e.before, after: e.after }))
  if (!edits.length) throw new Error('args.edits is required with args.ledgerFile: the before/after pairs made since the ledger')
  log(`re-check mode: ledger from ${LEDGER_FILE}, ${edits.length} edits since; no discovery round`)
}
// A finding whose status the fixer would never act on goes to the author without a confirm agent.
const FIXABLE = f => ['wrong', 'inconsistent', 'rule'].includes(f.status) || f.type === 'oracle'

// Critics run in parallel and cannot see each other, so the same defect arrives more than once:
// the numeric critic and the attribution critic quoting the same sentence, or the same sentence
// at report.html:520 and report-long.html:819. Merge those into one finding before anything is
// confirmed, so one confirmer rules on it and the fixer gets one correction, not rivals.
const RANK = { wrong: 4, inconsistent: 3, rule: 2, unsupported: 1, weak: 0 }
const norm = s => (s || '').toLowerCase().replace(/<[^>]+>/g, ' ').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim()
const anchor = loc => { const m = /([\w.-]+\.(?:html|json|md)):?(\d+)?/.exec(loc || ''); return m ? `${m[1]}:${m[2] || ''}` : (loc || '') }
const overlap = (a, b) => {
  const A = norm(a), B = norm(b)
  if (!A || !B) return false
  if (A.includes(B) || B.includes(A)) return true
  const ta = new Set(A.split(' ')), tb = new Set(B.split(' '))
  const common = [...ta].filter(t => t.length > 3 && tb.has(t)).length
  return common >= 6 && common / Math.min(ta.size, tb.size) >= 0.6
}
const sameDefect = (a, b) => overlap(a.claim, b.claim) || (anchor(a.location) === anchor(b.location) && anchor(a.location).endsWith(':') === false && overlap(a.correction, b.correction))
const unify = findings => {
  const groups = []
  for (const f of findings) {
    const g = groups.find(g => g.some(x => sameDefect(x, f)))
    if (g) g.push(f); else groups.push([f])
  }
  return groups.map(g => {
    if (g.length === 1) return g[0]
    const lead = [...g].sort((a, b) => (RANK[b.status] || 0) - (RANK[a.status] || 0) || (b.claim || '').length - (a.claim || '').length)[0]
    return {
      ...lead,
      type: [...new Set(g.map(x => x.type))].join('+'),
      location: [...new Set(g.map(x => x.location))].join(' ; '),
      evidence: g.map((x, i) => `[${x.type}] ${x.evidence}`).join('\n'),
      correction: g.map((x, i) => `[${x.type}] ${x.correction}`).join('\n'),
      merged: g.length,
    }
  })
}

while (!clean && round < MAX_ROUNDS) {
  round++
  const mode = (round === 1 && !LEDGER_FILE) ? 'discover' : 'recheck'
  log(`round ${round} (${mode}): deterministic checks`)
  // The fixer rebuilds and re-runs every verifier after its edits and reports the result, so a
  // re-check round after a fix reuses that instead of running the oracle again. The oracle runs
  // in round 1 (discovery, or the hand-edit re-check) and whenever the last fix did not report.
  const oracle = (round === 1 || !lastFix || !lastFix.verifiers)
    ? ((await agent(oraclePrompt(P, targets), { phase: 'Oracles', label: `oracles r${round}`, schema: ORACLE_SCHEMA, ...tier('oracle') })) || { ran: [], failures: [] })
    : { ran: [{ command: 'verifiers re-run by the fixer', exit: 0, summary: lastFix.verifiers }], failures: [] }

  // Discovery is one specialist critic per claim type, each with fresh context, because a
  // 30-page document is too much for one reader to check for everything at once. A re-check
  // is a handful of touched entries and edited paragraphs, so one agent covers every type;
  // args.recheckPerType restores the split for a very large edit set.
  const perType = mode === 'discover' || args.recheckPerType
  const ALL = { key: 'all', brief: P.claimTypes.map(ct => `${ct.key}: ${ct.brief}`).join('\n') }
  const units = perType ? P.claimTypes : [ALL]
  log(`round ${round} (${mode}): ${units.length} ${mode === 'discover' ? 'critics' : 're-check agent(s)'}`)
  const criticResults = await parallel(units.map(ct => () => {
    let ledger = ct.key === 'all'
      ? (LEDGER_FILE || P.claimTypes.flatMap(t => ledgers[t.key] || []))
      : (ledgers[ct.key] || [])
    if (Array.isArray(ledger) && mode !== 'discover') ledger = inEdited(ledger, edits)
    const delta = inEdited(ct.key === 'all' ? Object.values(ledgerDelta).flat() : (ledgerDelta[ct.key] || []), edits)
    const prompt = mode === 'discover'
      ? criticPrompt(P, targets, ct, oracle, refuted)
      : recheckPrompt(P, targets, ct, ledger, delta, edits, oracle, refuted)
    const phase = mode === 'discover' ? 'Find' : 'Re-check'
    return agent(prompt, { phase, label: `${mode}:${ct.key} r${round}`, schema: FINDINGS_SCHEMA, ...tier(mode === 'discover' ? 'find' : 'recheck') })
      .then(r => r && { ...r, type: ct.key })
  }))
  const critics = criticResults.filter(Boolean)
  const lost = criticResults.length - critics.length
  const checked = critics.reduce((n, c) => n + (c.claims_checked || 0), 0)
  // Discovery returns the whole ledger; a re-check returns only the entries it re-derived or
  // added, which are kept apart and supersede the same entries in the next round's prompt.
  for (const c of critics) {
    if (!c.ledger || !c.ledger.length) continue
    if (mode === 'discover') ledgers[c.type] = c.ledger
    else {
      const k = l => `${l.location}|${(l.claim || '').replace(/\s+/g, ' ').trim().slice(0, 160)}`
      const fresh = new Set(c.ledger.map(k))
      ledgerDelta[c.type] = (ledgerDelta[c.type] || []).filter(l => !fresh.has(k(l))).concat(c.ledger)
    }
  }
  // A critic that died (usage limit, API error) returns null. A round with a missing critic
  // or missing oracle proves nothing about the claims it did not read, so it can never count
  // as clean; it is recorded as incomplete and the loop moves on.
  const incomplete = lost > 0 || !oracle.ran.length
  if (incomplete) log(`round ${round}: INCOMPLETE, ${lost} critic(s) and ${oracle.ran.length ? 0 : 1} oracle failed; this round cannot count as clean`)

  const found = [
    ...oracle.failures.map(f => ({ claim: f.claim, location: f.location, status: 'wrong', evidence: `${f.source}: expected ${f.expected}, got ${f.got}`, correction: f.expected, type: 'oracle' })),
    ...critics.flatMap(c => c.findings.map(f => ({ ...f, type: c.type }))),
  ]
  const rawFresh = found.filter(f => !seen.has(key(f)))
  rawFresh.forEach(f => seen.add(key(f)))
  const fresh = unify(rawFresh)
  log(`round ${round}: ${checked} claims checked, ${found.length} findings, ${rawFresh.length} new, ${fresh.length} after merging duplicates`)

  // "Unsupported" and "weak" findings belong to the author whatever a confirmer says, so they
  // go straight to forAuthor with the critic's evidence and no confirm agent is spent on them.
  const authorOnly = fresh.filter(f => !FIXABLE(f))
  forAuthor.push(...authorOnly.map(f => ({ round, ...f })))
  const fixable = fresh.filter(FIXABLE)
  const toConfirm = fixable.slice(0, CONFIRM_CAP)
  if (fixable.length > CONFIRM_CAP) { log(`round ${round}: confirming ${CONFIRM_CAP} of ${fixable.length}; the rest return next round`); fixable.slice(CONFIRM_CAP).forEach(f => seen.delete(key(f))) }
  const judged = toConfirm.length ? (await pipeline(toConfirm, (f, _, i) =>
    agent(confirmPrompt(P, f), { phase: 'Confirm', label: `confirm ${i + 1}/${toConfirm.length} (${f.type})`, schema: VERDICT_SCHEMA, ...tier(f.status === 'rule' ? 'confirmRule' : 'confirm') })
      .then(v => v && { f, v }))).filter(Boolean) : []
  // Only a claim shown to be WRONG against the source (or inconsistent, or breaking a house rule)
  // is the fixer's to change.
  const confirmed = judged.filter(x => x.v.confirmed).map(x => ({ ...x.f, evidence: x.v.evidence, fix: x.v.fix }))
  refuted.push(...judged.filter(x => !x.v.confirmed).map(x => ({ location: x.f.location, claim: x.f.claim, reason: (x.v.reason || '').replace(/\s+/g, ' ').slice(0, 240) })))
  const entry = { round, mode, checked, found: found.length, fresh: fresh.length, confirmed: confirmed.length,
    forAuthor: authorOnly.length, refuted: judged.length - confirmed.length,
    lostConfirms: toConfirm.length - judged.length, incomplete, applied: 0, skipped: [] }
  history.push(entry)
  log(`round ${round}: ${confirmed.length} confirmed wrong, ${authorOnly.length} for the author, ${judged.length - confirmed.length} refuted${entry.lostConfirms ? `, ${entry.lostConfirms} confirmers failed` : ''}`)

  let toFix = confirmed
  if (!confirmed.length) {
    // Converged only when a complete re-check round, with every confirmer answering, finds nothing
    // wrong. The discovery round cannot be that round unless it found nothing at all: it has not
    // seen the document after any fix.
    const converged = (mode === 'recheck' && !incomplete && !entry.lostConfirms && checked > 0)
      || (mode === 'discover' && !incomplete && !entry.lostConfirms && found.length === 0 && oracle.failures.length === 0)
    if (!converged) continue
    if (!GATE) { clean = true; continue }
    const gate = await agent(gatePrompt(P, targets, refuted), { phase: 'Gate', label: `gate r${round}`, schema: GATE_SCHEMA, ...tier('gate') })
    if (!gate) { entry.gate = 'failed'; log(`round ${round}: the gate failed; this round cannot count as clean`); continue }
    const gateRaw = (gate.findings || []).map(f => ({ ...f, type: 'gate' })).filter(f => !seen.has(key(f)))
    gateRaw.forEach(f => seen.add(key(f)))
    const gateFresh = unify(gateRaw)
    const gateAuthor = gateFresh.filter(f => !FIXABLE(f))
    forAuthor.push(...gateAuthor.map(f => ({ round, ...f })))
    const gateFixable = gateFresh.filter(FIXABLE)
    const gateConfirm = gateFixable.slice(0, CONFIRM_CAP)
    if (gateFixable.length > CONFIRM_CAP) { log(`round ${round}: confirming ${CONFIRM_CAP} of ${gateFixable.length} gate findings; the rest return next round`); gateFixable.slice(CONFIRM_CAP).forEach(f => seen.delete(key(f))) }
    const gateJudged = gateConfirm.length ? (await pipeline(gateConfirm, (f, _, i) =>
      agent(confirmPrompt(P, f), { phase: 'Confirm', label: `confirm gate ${i + 1}/${gateConfirm.length}`, schema: VERDICT_SCHEMA, ...tier(f.status === 'rule' ? 'confirmRule' : 'confirm') })
        .then(v => v && { f, v }))).filter(Boolean) : []
    toFix = gateJudged.filter(x => x.v.confirmed).map(x => ({ ...x.f, evidence: x.v.evidence, fix: x.v.fix }))
    refuted.push(...gateJudged.filter(x => !x.v.confirmed).map(x => ({ location: x.f.location, claim: x.f.claim, reason: (x.v.reason || '').replace(/\s+/g, ' ').slice(0, 240) })))
    Object.assign(entry, { gate: gate.verdict, gateFound: gateFresh.length, gateConfirmed: toFix.length,
      gateForAuthor: gateAuthor.length, gateLostConfirms: gateConfirm.length - gateJudged.length })
    log(`round ${round}: gate ${gate.verdict}, ${gateFresh.length} findings, ${toFix.length} confirmed, ${gateAuthor.length} for the author`)
    if (!toFix.length) {
      // READY, or NOT READY on findings every confirmer refuted: nothing confirmed is wrong.
      if (!entry.gateLostConfirms && gateConfirm.length === gateFixable.length) clean = true
      continue
    }
  }

  const fix = await agent(fixPrompt(P, targets, toFix), { phase: 'Fix', label: `fix r${round} (${toFix.length})`, schema: FIX_SCHEMA, ...tier('fix') })
  entry.applied = fix ? fix.applied.length : 0
  entry.skipped = fix ? fix.skipped : []
  if (fix) edits = edits.concat(fix.applied)
  lastFix = fix
  log(`round ${round}: ${entry.applied} edits applied${entry.skipped.length ? `, ${entry.skipped.length} skipped` : ''}`)
}

if (!clean) log(`stopped after ${round} rounds without a clean ${GATE ? 'gate' : 're-check'}; receipt will say not clean`)
else log(GATE ? 'clean: the loop converged and the lock gate found nothing confirmable. This covers the targets and the gate scope; it is not a lock.' : 'clean: a complete re-check round found nothing wrong in the targets. This is not a lock.')
// The refuted list is written beside the receipts so hooks/ledger-from-run.py --result can
// carry it into the next run's ledger file; the journal does not record it.
const slug = (targets[0] || 'run').split('/').pop().replace(/\.[A-Za-z0-9]+$/, '').replace(/[^A-Za-z0-9._-]/g, '_')
const refutedPath = args.refutedOut || `$HOME/.claude/receipts/refuted-${slug}.json`
const receipt = await agent(receiptPrompt(P, targets, outputs, history, clean, refuted, refutedPath), { phase: 'Receipt', label: 'receipt', schema: RECEIPT_SCHEMA, ...tier('receipt') })
log(`refuted findings (${refuted.length}) written to ${refutedPath}; pass it to ledger-from-run.py --result next time`)

// clean means a complete re-check round found nothing wrong, the lock gate (when the profile has
// one) found nothing confirmable, AND the receipt was written.
// forAuthor lists the "unsupported" and "weak" findings: the author decides those.
// ledgers, ledgerDelta and refuted are returned so hooks/ledger-from-run.py can carry them
// into the next run's ledger file.
return { clean: clean && !!(receipt && receipt.written), rounds: round, history, forAuthor, edits, receipt, ledgers, ledgerDelta, refuted }
