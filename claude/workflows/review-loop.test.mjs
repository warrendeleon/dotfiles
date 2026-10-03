// Runs review-loop.js with every agent stubbed, to check how a run ends. The workflow runtime
// is replaced by plain functions: agent() answers by the label the loop gives each stage.
//
//   node --test claude/workflows/review-loop.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./review-loop.js', import.meta.url), 'utf8')
  .replace('export const meta =', 'const meta =')
const run = new Function('agent', 'parallel', 'pipeline', 'log', 'phase', 'args', 'budget',
  `return (async () => {\n${source}\n})()`)

const parallel = thunks => Promise.all(thunks.map(t => t().catch(() => null)))
const pipeline = (items, ...stages) => Promise.all(items.map(async (item, i) => {
  let r = item
  for (const stage of stages) r = await stage(r, item, i)
  return r
}))

const finding = {
  claim: 'README.md:192 says "(see below)", a positional reference',
  location: 'README.md:192', status: 'rule', rule: 'revision-passes.md', evidence: 'line 192',
  correction: 'name the section',
}

// One re-check run of two rounds: the gate finds one fault in round 1, which is confirmed, and
// says READY in round 2. fixer decides what the fixer does with the confirmed fault.
async function endOfRun(fixer) {
  const logs = []
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    const round = Number((/r(\d+)/.exec(label) || [])[1] || 0)
    if (label.startsWith('oracles')) return { ran: [{ command: 'verifiers', exit: 0, summary: 'all OK' }], failures: [] }
    if (label.startsWith('recheck')) return { claims_checked: 1, findings: [], ledger: [] }
    if (label.startsWith('gate')) return round === 1
      ? { findings: [finding], verdict: 'NOT READY', reason: 'one fault' }
      : { findings: [], verdict: 'READY', reason: 'nothing found' }
    if (label.startsWith('confirm')) return { confirmed: true, evidence: 'read it', fix: 'name the section', reason: '' }
    if (label.startsWith('fix')) return { ...fixer, rebuilt: true, verifiers: 'all OK' }
    if (label === 'receipt') return { path: '/tmp/receipt.json', written: true, note: '' }
    throw new Error(`unexpected agent ${label}`)
  }
  const args = {
    profile: 'blog', targets: ['/tmp/post.md'], repo: '/tmp/companion', maxRounds: 3,
    ledgerFile: '/tmp/ledger.json', edits: [{ file: '/tmp/post.md', before: 'a', after: 'b' }],
  }
  const result = await run(agent, parallel, pipeline, m => logs.push(m), () => {}, args,
    { total: null, spent: () => 0, remaining: () => Infinity })
  return { result, logs }
}

test('a confirmed fault the fixer could not apply keeps the run from being clean', async () => {
  const { result, logs } = await endOfRun({
    applied: [], skipped: [{ claim: finding.claim, reason: 'the fix belongs in the companion' }],
  })
  assert.equal(result.clean, false)
  assert.equal(result.unfixed.length, 1)
  assert.match(result.unfixed[0].reason, /companion/)
  assert.ok(logs.some(l => l.startsWith('not clean: 1 confirmed finding')))
})

test('a run whose confirmed fault was applied ends clean', async () => {
  const { result } = await endOfRun({
    applied: [{ file: '/tmp/post.md', before: '(see below)', after: '(see the section)' }], skipped: [],
  })
  assert.equal(result.clean, true)
  assert.deepEqual(result.unfixed, [])
})
