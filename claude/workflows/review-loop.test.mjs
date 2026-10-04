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
// The workflow runtime hands each stage a copy of the item, not the item itself, so a script
// that matches results to items by object identity breaks there; structuredClone does the same.
const pipeline = (items, ...stages) => Promise.all(items.map(async (item, i) => {
  let r = structuredClone(item)
  for (const stage of stages) r = await stage(r, structuredClone(item), i)
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

// 4 Oct 2026, post 17's English: a discovery round raised 56 fixable findings and the cap
// confirmed 16. The other 40 were only dropped from "seen" so a critic could raise them again,
// but the re-check rounds read only the edited passages, so none of the 40 was ever ruled on.
// The same run refuted a finding because its confirmer was not told where the article was.
// distinct claims, so the merge step keeps them apart
const many = n => Array.from({ length: n }, (_, i) => ({
  claim: `sentence number ${i} breaks rule q${i}`, location: `post.md:${i + 1}`, status: 'rule',
  evidence: `line ${i + 1}`, correction: `rewrite z${i}`,
}))
const claimOf = prompt => (/^- claim: (.*)$/m.exec(prompt) || [])[1]

// A discovery run on the blog profile. verdict(claim, attempt) answers each confirm agent.
async function blogRun({ findings, verdict, args: extra = {} }) {
  const logs = [], prompts = {}, confirmPrompts = [], attempts = {}
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    prompts[label] = prompt
    if (label.startsWith('oracles')) return { ran: [{ command: 'sweep', exit: 0, summary: 'OK' }], failures: [] }
    if (label === 'discover:style r1') return { claims_checked: findings.length, findings, ledger: [] }
    if (label.startsWith('discover')) return { claims_checked: 1, findings: [], ledger: [] }
    if (label.startsWith('recheck')) return { claims_checked: 1, findings: [], ledger: [] }
    if (label.startsWith('confirm')) {
      confirmPrompts.push(prompt)
      const c = claimOf(prompt)
      attempts[c] = (attempts[c] || 0) + 1
      return verdict(c, attempts[c])
    }
    if (label.startsWith('fix')) return { applied: [{ file: '/tmp/post.md', before: 'a', after: 'b' }], skipped: [], rebuilt: true, verifiers: 'all OK' }
    if (label.startsWith('gate')) return { findings: [], verdict: 'READY', reason: 'nothing found' }
    if (label === 'receipt') return { path: '/tmp/receipt.json', written: true, note: '' }
    throw new Error(`unexpected agent ${label}`)
  }
  const args = { profile: 'blog', targets: ['/tmp/post.md'], repo: '/tmp/companion', notes: 'TAGS ARE LOCAL', maxRounds: 3, ...extra }
  const result = await run(agent, parallel, pipeline, m => logs.push(m), () => {}, args,
    { total: null, spent: () => 0, remaining: () => Infinity })
  return { result, logs, prompts, confirmPrompts, attempts }
}
const yes = () => ({ confirmed: true, evidence: 'read it', fix: 'rewrite', reason: '' })

test('findings past the confirm cap are confirmed in the next round, not dropped', async () => {
  const findings = many(20)
  const { result, confirmPrompts } = await blogRun({ findings, verdict: yes })
  const ruled = new Set(confirmPrompts.map(claimOf))
  for (const f of findings) assert.ok(ruled.has(f.claim), `a confirmer ruled on: ${f.claim}`)
  assert.equal(result.clean, true)
  assert.equal(result.history[0].queued, 4)
  assert.equal(result.history[1].queued, 0)
  assert.deepEqual(result.unconfirmed, [])
  // each finding is ruled on once, not again in every later round
  assert.equal(confirmPrompts.length, findings.length)
})

test('a run that reaches the round cap with findings still queued is not clean and returns them', async () => {
  const { result, logs } = await blogRun({ findings: many(3), verdict: yes, args: { confirmCap: 1, maxRounds: 2 } })
  assert.equal(result.clean, false)
  assert.equal(result.unconfirmed.length, 1)
  assert.ok(logs.some(l => /1 finding\(s\) were never ruled on/.test(l)))
})

test('the confirm prompt names the targets, the repository and the notes', async () => {
  const { confirmPrompts } = await blogRun({ findings: many(1), verdict: yes })
  assert.match(confirmPrompts[0], /\/tmp\/post\.md/)
  assert.match(confirmPrompts[0], /REPOSITORY: \/tmp\/companion/)
  assert.match(confirmPrompts[0], /TAGS ARE LOCAL/)
})

test('a confirmer that could not check is retried, and never counted as a refutation', async () => {
  const [f] = many(1)
  const blind = { confirmed: false, cannot_check: true, evidence: '', reason: 'could not find the article' }
  const once = await blogRun({ findings: [f], verdict: (_, n) => n === 1 ? blind : yes() })
  assert.equal(once.attempts[f.claim], 2)
  assert.deepEqual(once.result.refuted, [])
  assert.equal(once.result.clean, true)

  const never = await blogRun({ findings: [f], verdict: () => blind })
  assert.deepEqual(never.result.refuted, [])
  assert.equal(never.result.forAuthor.length, 1)
  assert.equal(never.result.forAuthor[0].status, 'unchecked')
})

test('findings an earlier run never ruled on are confirmed in the first round', async () => {
  const [f] = many(1)
  const { result, confirmPrompts } = await blogRun({ findings: [], verdict: yes, args: {
    ledgerFile: '/tmp/ledger.json', edits: [{ file: '/tmp/post.md', before: 'a', after: 'b' }], pending: [f],
  } })
  assert.equal(claimOf(confirmPrompts[0]), f.claim)
  assert.equal(result.clean, true)
})
