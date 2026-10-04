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
  const prompts = {}
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    prompts[label] = prompt
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
  return { result, logs, prompts }
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

// 3 Oct 2026, post 16: a fix to a comment the post copies from build.gradle was applied to the
// post only; the next round found the post's block no longer matched the companion and put the
// old text back. The blog fixer is now told to leave such a fix to the author, untouched.
test('the blog fixer leaves a fix to text the post copies from the companion to the author', async () => {
  const { prompts } = await endOfRun({
    applied: [{ file: '/tmp/post.md', before: '(see below)', after: '(see the section)' }], skipped: [],
  })
  const fix = prompts['fix r1 (1)']
  assert.ok(fix, 'the fixer ran in round 1')
  assert.match(fix, /copies from the companion/)
  assert.match(fix, /edit nothing: return it under skipped/)
})

test('a run whose confirmed fault was applied ends clean', async () => {
  const { result } = await endOfRun({
    applied: [{ file: '/tmp/post.md', before: '(see below)', after: '(see the section)' }], skipped: [],
  })
  assert.equal(result.clean, true)
  assert.deepEqual(result.unfixed, [])
})

// 4 Oct 2026, post 16's translations: the loop gained a translation profile. A discovery run on
// it must send the oracle to the parity comparator and every critic to translation-review.md,
// and a run that finds nothing must still pass the lock gate before it counts as clean.
async function translationRun() {
  const prompts = {}
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    prompts[label] = prompt
    if (label.startsWith('oracles')) return { ran: [{ command: 'translation-parity.py', exit: 0, summary: 'RESULT OK' }], failures: [] }
    if (label.startsWith('discover')) return { claims_checked: 3, findings: [], ledger: [{ claim: 'x', location: 'es/post.md:1', check: 'read' }] }
    if (label.startsWith('gate')) return { findings: [], verdict: 'READY', reason: 'nothing found' }
    if (label === 'receipt') return { path: '/tmp/receipt.json', written: true, note: '' }
    throw new Error(`unexpected agent ${label}`)
  }
  const args = { profile: 'translation', targets: ['/tmp/es/post.md'], maxRounds: 2 }
  const result = await run(agent, parallel, pipeline, () => {}, () => {}, args,
    { total: null, spent: () => 0, remaining: () => Infinity })
  return { result, prompts }
}

test('the translation profile runs the comparator, the locale guide and the lock gate', async () => {
  const { result, prompts } = await translationRun()
  assert.equal(result.clean, true)
  assert.match(prompts['oracles r1'], /translation-parity\.py/)
  for (const k of ['parity', 'fidelity', 'language', 'glossary', 'style']) {
    assert.ok(prompts[`discover:${k} r1`], `critic ${k} ran`)
    assert.match(prompts[`discover:${k} r1`], /translation-review\.md/)
  }
  assert.match(prompts['discover:language r1'], /blind native read/)
  assert.match(prompts['gate r1'], /English source of each target in full/)
})

// 4 Oct 2026, post 17's companion: the loop gained a companion profile for a code change. Its
// oracle runs the type check, the suites and the smoke script; its critics read the diff against
// the specification, the tests, the comments, the mechanism's security and the README; its gate
// reads every touched file whole.
test('the companion profile runs the suites, reads the diff five ways and gates on every touched file', async () => {
  const prompts = {}
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    prompts[label] = prompt
    if (label.startsWith('oracles')) return { ran: [{ command: 'npx jest', exit: 0, summary: '183 passed' }], failures: [] }
    if (label.startsWith('discover')) return { claims_checked: 3, findings: [], ledger: [{ claim: 'x', location: 'src/a.ts:1', check: 'read' }] }
    if (label.startsWith('gate')) return { findings: [], verdict: 'READY', reason: 'nothing found' }
    if (label === 'receipt') return { path: '/tmp/receipt.json', written: true, note: '' }
    throw new Error(`unexpected agent ${label}`)
  }
  const args = { profile: 'companion', targets: ['/tmp/repo/src/a.ts'], repo: '/tmp/repo', startRef: 'post-16-fallbacks', maxRounds: 2 }
  const result = await run(agent, parallel, pipeline, () => {}, () => {}, args,
    { total: null, spent: () => 0, remaining: () => Infinity })
  assert.equal(result.clean, true)
  assert.match(prompts['oracles r1'], /npx jest/)
  assert.match(prompts['oracles r1'], /federation-smoke\.sh/)
  for (const k of ['correctness', 'tests', 'comments', 'security', 'readme']) {
    assert.ok(prompts[`discover:${k} r1`], `critic ${k} ran`)
    assert.match(prompts[`discover:${k} r1`], /node_modules/)
  }
  assert.match(prompts['discover:security r1'], /older map/)
  assert.match(prompts['gate r1'], /every file the change touches, in full/)
})
