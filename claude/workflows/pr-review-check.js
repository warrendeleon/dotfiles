export const meta = {
  name: 'pr-review-check',
  description: 'One bounded pass over a drafted pull request review, by reading: every file:line against the pull request diff, every quoted code and identifier checked in the diff, style against the writing guides, then the receipt',
  whenToUse: 'Before posting a pull request review. args: {repo: "owner/name", pr: number, files: [drafted review body and inline-comment files], notes?: string, probe?: boolean (default false: nothing is cloned or run except that each ```suggestion block is applied to the head and type-checked; the review is read against gh pr diff), models?: {check, fix}}. Three agents at most: one checker (opus/medium), one fixer if anything is wrong (opus/medium), one receipt (sonnet/low, runs pr-check.sh). No loop. Launch by scriptPath: ~/Developer/dotfiles/claude/workflows/pr-review-check.js.',
  phases: [
    { title: 'Check', detail: 'file:line references against the diff, quoted code and identifiers, style' },
    { title: 'Fix', detail: 'only what is shown wrong, in the draft files' },
    { title: 'Receipt', detail: 'pr-check.sh: diff test and the receipt' },
  ],
}

const repo = args && args.repo
const pr = args && args.pr
const files = ((args && args.files) || []).filter(Boolean)
if (!repo || !pr || !files.length) throw new Error('args.repo, args.pr and args.files are required')
const probe = !!(args && args.probe)
const MODEL = { check: 'opus', fix: 'opus', receipt: 'sonnet', ...((args && args.models) || {}) }
log(`models: check ${MODEL.check}/medium, fix ${MODEL.fix}/medium, receipt ${MODEL.receipt}/low; at most three agents, no loop`)

const FINDINGS = {
  type: 'object',
  properties: {
    references_checked: { type: 'integer' },
    claims_probed: { type: 'integer' },
    findings: { type: 'array', items: { type: 'object', properties: {
      quote: { type: 'string', description: 'the exact sentence in the draft' },
      file: { type: 'string', description: 'which draft file' },
      kind: { type: 'string', enum: ['on-main', 'reference', 'not-reproduced', 'scope', 'style'] },
      evidence: { type: 'string', description: 'the command run and its output' },
      correction: { type: 'string', description: 'replacement text, or "move to carried-over section", or "delete"' },
    }, required: ['quote', 'file', 'kind', 'evidence', 'correction'] } },
  },
  required: ['references_checked', 'claims_probed', 'findings'],
}
const FIX = {
  type: 'object',
  properties: {
    applied: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, before: { type: 'string' }, after: { type: 'string' } }, required: ['file', 'before', 'after'] } },
    skipped: { type: 'array', items: { type: 'object', properties: { quote: { type: 'string' }, reason: { type: 'string' } }, required: ['quote', 'reason'] } },
  },
  required: ['applied', 'skipped'],
}
const RECEIPT = { type: 'object', properties: { output: { type: 'string', description: 'the full stdout and stderr' }, exit_code: { type: 'integer' }, receipt_path: { type: 'string', description: 'the path the script printed, or empty' } }, required: ['output', 'exit_code', 'receipt_path'] }

const common = `You are checking a DRAFT pull request review before it is posted. Nothing here is posted to GitHub; you edit only the draft files named below, and only when this stage says so.

DRAFT FILES
${files.map(f => '- ' + f).join('\n')}

PULL REQUEST: ${repo}#${pr}. The source is the pull request itself, read with gh: \`gh pr diff ${pr} --repo ${repo}\` for every changed line, \`gh pr view ${pr} --repo ${repo}\` for the description, and \`gh api repos/${repo}/contents/<path>?ref=<head sha>\` when you need lines of a file the diff does not show. Do not clone the repository${probe ? '' : ' and do not run its code; this is a reading review'}, except to test \`\`\`suggestion blocks in step 5.
${args.notes ? 'NOTES FROM THE USER:\n' + args.notes + '\n' : ''}
Your final text is data for the next stage, not a message to a person. No confirmations, no padding.`

const checkPrompt = `${common}

STAGE: check. Do these five things, in order, and report only failures.

1. ON MAIN. For every file:line the draft names, find it in the diff. A line the pull request did not add or change is a carried-over fault, not this change's; it is a finding of kind "on-main" unless the draft already places it under a heading containing "carried over" or "already on main".
2. REFERENCES. For every file path, line number, identifier, function name and quoted code in the draft, confirm it appears in the diff (or the file at the head commit) at the stated place and says what the draft says. A mismatch is kind "reference".
3. CLAIMS. For every mechanical claim ("throws", "returns undefined", "never fires", "leaks", "is not awaited", "fails on"), read the code path in the diff and say whether the code as written supports it; quote the lines. ${probe ? 'You may also write and run a probe when reading cannot settle it.' : 'Do not run anything; reading is the review.'} A claim the code does not support is kind "not-reproduced".
4. SCOPE AND STYLE. Product decisions, ticket scope and priority calls belong on the Jira ticket via its owner, not in a GitHub review: kind "scope". Then read ~/.wiki/personal/writing/writing-guides.md and the guides its code review row names, and report kind "style" for: any sentence, heading or table that describes the reviewer's own process rather than the code ("verified", "ran it", "re-verified on <sha>", "my probe", "my mutation", "on my checkout", "bookkeeping", "recording this here", "checked against the diff", lists of commands run and their pass counts), which the author must never see; severity tags such as "Suggestion — medium, non-blocking"; narration of the review's own state ("withdrawn", "approving separately", "leaving this on the record"); a finding argued in the body when it concerns one line and could be an inline comment there (inline comments carry the review); a body that repeats or summarises what the inline comments already say (the body is optional: leave it out when the inline comments cover everything, and when GitHub needs one, as for REQUEST_CHANGES, one short line is enough); an inline comment that does not start with exactly one traffic-light emoji followed by its meaning in bold, "🟢 **Good:**" for something done well, "🟡 **Suggestion:**" for a suggestion, "🔴 **Change requested:**" for a change requested; a review event that contradicts the lights (any 🔴 means REQUEST_CHANGES, otherwise COMMENT or APPROVE); a body that prints the review-event name or has a Recommendation heading; verbosity (the aim is to help the author fix things without overwhelming them): a comment, body, snippet or 🟢 the author does not need, a comment longer than what the code does, why it matters and what to change, or a point made twice anywhere in the review; a snippet where one sentence would make the fix clear (snippets are optional and only for when showing the fix is clearer than describing it); a \`\`\`suggestion block used for a sketch, where a plain code block belongs; semicolon chains where a list belongs; a 🔴 comment with no steelman (a 🟢 comment on the same change counts); positional references ("above", "the second point"); a banned word or an em-dash stitching two clauses. Quote the sentence.

5. SUGGESTIONS. A \`\`\`suggestion block gives the author a button that commits it as it stands, so it must leave the branch working on its own. For each one: confirm the comment is anchored (line, or start_line to line, side RIGHT) to lines inside the diff and that the block is a complete replacement for exactly those lines with the file's indentation. Then test it: find a local checkout of ${repo} with dependencies installed (look under ~/Developer), add a temporary git worktree at the pull request head sha (symlink node_modules from that checkout), apply that one suggestion alone by replacing the anchored lines, and run the repository's own type check and lint on it (read package.json for the scripts). Grep the repository for anything else the change needs: a new import, a renamed or removed identifier's other uses, a changed signature's callers, a test that pins the old behaviour. Remove the worktree when done. A suggestion that is anchored wrongly, fails the type check or lint, needs a change elsewhere, or only works together with another suggestion is kind "suggestion-breaks"; its correction turns it into a plain code block that names the other places to change. If no checkout with dependencies exists, report every suggestion as kind "suggestion-untested" with the same correction.

What is NOT a finding: a choice of words, a shorter or longer phrasing, a claim that reproduces, a reference that resolves.`

const fixPrompt = findings => `${common}

STAGE: fix. Apply these findings to the draft files by hand, with exact-string edits. Reviewer-process sentences and severity tags are deleted, not reworded; if a verification detail is the evidence for a finding, keep at most one clause stating what the code does ("the old shape throws on the same input"), never what the reviewer did. "on-main" findings move under a heading containing "Carried over" with the ask framed as the cheapest moment to add the guard, and lose any "blocking" label. "not-reproduced" findings are deleted or reworded to what the code shows. Inline comments carry the review: a one-line finding argued in the body moves to an inline comment on its line. A body that repeats the inline comments is cut to one short line, or removed when the review event does not need one. Every inline comment starts with one traffic-light emoji and its meaning in bold ("🟢 **Good:**", "🟡 **Suggestion:**", "🔴 **Change requested:**"), and the review event follows the lights (any 🔴 means REQUEST_CHANGES). Never print the review-event name or add a Recommendation heading. Cut verbosity and repetition. Snippets are optional: never add one the comment does not need. "suggestion-breaks" and "suggestion-untested" findings turn the \`\`\`suggestion block into a plain code block that names the other places to change; never post a suggestion that was not tested. Do not post anything.

FINDINGS
${findings.map((f, i) => `${i + 1}. [${f.kind}] ${f.file}
   quote: ${f.quote}
   evidence: ${f.evidence}
   correction: ${f.correction}`).join('\n')}

Report each file with the exact before and after. Skip a finding only if applying it would make the draft say something the evidence contradicts, and say why.`

const receiptPrompt = `${common}

STAGE: receipt. Run exactly this command with \`; echo exit=$?\` appended, and report its full output, the exit code as printed, and the receipt path it printed (a line under ~/.claude/receipts/). Do not interpret the result; copy it.

$HOME/Developer/dotfiles/claude/hooks/pr-check.sh --repo ${JSON.stringify(repo)} --pr ${pr} ${files.map(f => JSON.stringify(f)).join(' ')}

Do nothing else.`

phase('Check')
const check = await agent(checkPrompt, { label: `check #${pr}`, schema: FINDINGS, model: MODEL.check, effort: 'medium' })
if (!check) throw new Error('the checker did not return; nothing was verified, so nothing is receipted')
log(`${check.references_checked} references, ${check.claims_probed} claims probed, ${check.findings.length} findings`)

let fix = null
if (check.findings.length) {
  phase('Fix')
  fix = await agent(fixPrompt(check.findings), { label: `fix #${pr} (${check.findings.length})`, schema: FIX, model: MODEL.fix, effort: 'medium' })
  log(`${fix ? fix.applied.length : 0} edits applied${fix && fix.skipped.length ? `, ${fix.skipped.length} skipped` : ''}`)
}

phase('Receipt')
const receipt = await agent(receiptPrompt, { label: 'pr-check + receipt', schema: RECEIPT, model: MODEL.receipt, effort: 'low' })

// clean is decided from the script's exit code and receipt path, never from the agent's opinion
const clean = !!(receipt && receipt.exit_code === 0 && /\/receipts\/.+\.json/.test(receipt.receipt_path || ''))
if (!clean) log(`receipt stage did not produce a clean receipt: ${receipt ? `exit ${receipt.exit_code}` : 'no result'}`)
return { clean, findings: check.findings, referencesChecked: check.references_checked, claimsProbed: check.claims_probed, fix, receipt }
