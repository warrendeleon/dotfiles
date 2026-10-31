// Runs pr-review-sweep.js with the agents and the pr-review-check gate stubbed.
//
//   node --test claude/workflows/pr-review-sweep.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./pr-review-sweep.js', import.meta.url), 'utf8').replace('export const meta =', 'const meta =')
const run = new Function('agent', 'parallel', 'pipeline', 'log', 'phase', 'args', 'budget', 'workflow', `return (async () => {\n${source}\n})()`)

// As the real pipeline(): each item runs through the stages in order, and a stage that throws
// or returns null drops the item to null without running the stages after it.
const pipeline = async (items, ...stages) => Promise.all(items.map(async (item, i) => {
  let v = item
  try {
    for (const [k, s] of stages.entries()) {
      v = await s(k === 0 ? item : v, item, i)
      if (v == null) return null
    }
    return v
  } catch {
    return null
  }
}))

const D = '/h/.claude/pr-review-sweep/runs/20261028-1300/ncu-ad-manager-3482'
const lane = (over = {}) => ({
  repo: 'ncu-ad-manager', n: 3482, url: 'https://github.com/newsuk/ncu-ad-manager/pull/3482', title: 'feat(SCB-1): x', author: 'chuan',
  draft: false, head: 'b'.repeat(40), base: 'main', key: 'SCB-1', ticket_type: 'Bug', mode: 'new', reason: 'review requested',
  size: { additions: 10, deletions: 2, files: 2 }, last_review: null, threads: [], dir: D, ...over,
})
const draft = (over = {}) => ({
  payload_path: `${D}/payload.json`, head_sha: 'b'.repeat(40), proposed_event: 'REQUEST_CHANGES', red: 1, yellow: 0, green: 0,
  ac_results: [], edge_cases: [], replies: [], dropped_as_overlap: [], open_points_by_others: [], decisions_pending: [], summary: 's', ...over,
})
const coverage = { ran: true, reason: '', source_files: ['src/a.ts'], uncovered_lines: [], revert: { applies: true, failing_tests: [], caught: false }, mutations: [], gaps: [{ file: 'src/a.ts', line: 4, light: 'red', text: 't' }], worktree_removed: true }
const tight = { words_before: 80, words_after: 60, inventory_kept: 9, inventory_total: 9, imported: true, notes: '' }
const decision = (over = {}) => ({ action: 'post', edited: false, edits: [], keep_files: [`${D}/payload.json`], hold_reason: '', note: 'request changes, one 🔴', ...over })

async function runWith(lanes, answers, gates = [{ clean: true, findings: [] }]) {
  const calls = [], gateCalls = [], logs = []
  const agent = async (prompt, opts) => {
    const stage = opts.label.split(' ')[0]
    calls.push({ stage, prompt, opts })
    const a = answers[stage]
    return typeof a === 'function' ? a(prompt, opts) : a
  }
  const workflow = async (ref, a) => {
    gateCalls.push(a)
    return gates[Math.min(gateCalls.length - 1, gates.length - 1)]
  }
  const result = await run(agent, null, pipeline, m => logs.push(m), () => {}, { lanes }, null, workflow)
  return { result, calls, gateCalls, logs }
}

test('a new review runs every stage and returns the exact post command', async () => {
  const { result, calls, gateCalls } = await runWith([lane()], { coverage, draft: draft(), tighten: tight, decide: decision() })
  assert.deepEqual(calls.map(c => c.stage), ['coverage', 'draft', 'tighten', 'decide'])
  assert.equal(gateCalls.length, 1)
  assert.deepEqual(gateCalls[0].files, [`${D}/payload.json`])
  assert.equal(result[0].action, 'post')
  assert.deepEqual(result[0].posts, [{ file: `${D}/payload.json`, command: `gh api repos/newsuk/ncu-ad-manager/pulls/3482/reviews --input ${D}/payload.json --jq '.html_url'` }])
  assert.match(calls[1].prompt, /"gaps":\[\{"file":"src\/a.ts"/)
})

test('replies that need no answer cost one agent and post nothing, and every judged comment is marked seen', async () => {
  const threads = [{ kind: 'review', reply_to: 10, comment_ids: [11, 12] }, { kind: 'issue', reply_to: 20, comment_ids: [20] }]
  const replies = [{ reply_to: 10, verdict: 'none', reason: 'done, and the head has it', file: '' }, { reply_to: 20, verdict: 'none', reason: 'thanks', file: '' }]
  const { result, calls, gateCalls } = await runWith([lane({ mode: 'replies', threads })], { draft: draft({ payload_path: '', proposed_event: 'NONE', replies }) })
  assert.deepEqual(calls.map(c => c.stage), ['draft'])
  assert.equal(gateCalls.length, 0)
  assert.equal(result[0].action, 'nothing')
  assert.deepEqual(result[0].seen, [11, 12, 20])
  assert.match(calls[0].prompt, /REPLIES ONLY/)
})

test('answers go to the thread they belong to: review threads to /replies, conversation comments to the issue', async () => {
  const threads = [{ kind: 'review', reply_to: 10, comment_ids: [11] }, { kind: 'issue', reply_to: 20, comment_ids: [20] }]
  const replies = [{ reply_to: 10, verdict: 'answer', reason: 'fix not at head', file: `${D}/reply-10.json` }, { reply_to: 20, verdict: 'answer', reason: 'question', file: `${D}/reply-20.json` }]
  const { result } = await runWith([lane({ mode: 'replies', threads })], {
    draft: draft({ payload_path: '', proposed_event: 'NONE', replies }), tighten: tight,
    decide: decision({ keep_files: [`${D}/reply-10.json`, `${D}/reply-20.json`] }),
  })
  assert.deepEqual(result[0].posts.map(p => p.command), [
    `gh api repos/newsuk/ncu-ad-manager/pulls/3482/comments/10/replies --input ${D}/reply-10.json --jq '.html_url'`,
    `gh api repos/newsuk/ncu-ad-manager/issues/3482/comments --input ${D}/reply-20.json --jq '.html_url'`,
  ])
})

test('a dispute is decided even with nothing drafted, so it can be held', async () => {
  const replies = [{ reply_to: 10, verdict: 'dispute-holds', reason: 'author says the guard is not needed', file: '' }]
  const { result, calls } = await runWith([lane({ mode: 'replies', threads: [{ kind: 'review', reply_to: 10, comment_ids: [11] }] })], {
    draft: draft({ payload_path: '', proposed_event: 'NONE', replies }),
    decide: decision({ action: 'hold', keep_files: [], hold_reason: 'the author disputes the guard comment' }),
  })
  assert.deepEqual(calls.map(c => c.stage), ['draft', 'decide'])
  assert.equal(result[0].action, 'hold')
  assert.deepEqual(result[0].posts, [])
  assert.deepEqual(result[0].seen, [11])
})

test('an edit by the decider is gated again, and an unclean receipt holds the PR', async () => {
  const { result, gateCalls } = await runWith([lane()], { coverage, draft: draft(), tighten: tight, decide: decision({ edited: true, edits: ['cut a 🔴'] }) },
    [{ clean: true, findings: [] }, { clean: false, findings: [{ kind: 'reference' }] }])
  assert.equal(gateCalls.length, 2)
  assert.equal(result[0].action, 'hold')
  assert.deepEqual(result[0].posts, [])
  assert.match(result[0].hold_reason, /receipt is not clean/)
})

test('a reply the gate deleted is dropped and what is kept is gated again before posting', async () => {
  const replies = [{ reply_to: 10, verdict: 'answer', reason: 'fix not at head', file: `${D}/reply-10.json` }]
  const { result, gateCalls } = await runWith([lane({ threads: [{ kind: 'review', reply_to: 10, comment_ids: [11] }] })],
    { coverage, draft: draft({ replies }), tighten: tight, decide: decision({ keep_files: [`${D}/payload.json`] }) },
    [{ clean: false, findings: [{ kind: 'not-reproduced' }] }, { clean: true, findings: [] }])
  assert.deepEqual(gateCalls.map(g => g.files), [[`${D}/payload.json`, `${D}/reply-10.json`], [`${D}/payload.json`]])
  assert.equal(result[0].action, 'post')
  assert.deepEqual(result[0].posts.map(p => p.file), [`${D}/payload.json`])
})

test('a post with no files left becomes nothing', async () => {
  const { result } = await runWith([lane()], { coverage, draft: draft(), tighten: tight, decide: decision({ keep_files: [] }) })
  assert.equal(result[0].action, 'nothing')
  assert.deepEqual(result[0].posts, [])
})

test('a failed stage holds the lane instead of dropping it', async () => {
  const { result } = await runWith([lane()], { coverage, draft: null })
  assert.equal(result[0].action, 'hold')
  assert.match(result[0].hold_reason, /a stage failed/)
})

test('a re-review measures only what moved since the last review', async () => {
  const last = { state: 'CHANGES_REQUESTED', commit_id: 'a'.repeat(40), submitted_at: '2026-10-20T10:00:00Z', url: 'u' }
  const { calls } = await runWith([lane({ mode: 'rereview', last_review: last })], { coverage, draft: draft(), tighten: tight, decide: decision() })
  assert.match(calls[0].prompt, new RegExp(`RE-REVIEW: first list the non-test source files whose own changes moved between ${'a'.repeat(40)}`))
  assert.match(calls[1].prompt, new RegExp(`compare/${'a'.repeat(40)}\\.\\.\\.${'b'.repeat(40)}`))
})

test('no lanes, no agents', async () => {
  const { result, calls } = await runWith([], {})
  assert.deepEqual(result, [])
  assert.equal(calls.length, 0)
})
