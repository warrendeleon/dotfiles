// Runs edit-doc.js with every agent stubbed, to check which stages run and how a run ends.
// The workflow runtime is replaced by plain functions: agent() answers by the label each stage
// is given.
//
//   node --test claude/workflows/edit-doc.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'

const source = readFileSync(new URL('./edit-doc.js', import.meta.url), 'utf8')
  .replace('export const meta =', 'const meta =')
const run = new Function('agent', 'parallel', 'pipeline', 'log', 'phase', 'args', 'budget',
  `return (async () => {\n${source}\n})()`)
const parallel = thunks => Promise.all(thunks.map(t => t().catch(() => null)))
const pipeline = (items, ...stages) => Promise.all(items.map(async (item, i) => {
  let r = structuredClone(item)
  for (const stage of stages) r = await stage(r, structuredClone(item), i)
  return r
}))
const budget = { total: null, spent: () => 0, remaining: () => Infinity }

const okMech = { exit: 0, total: 40, missing: [] }
const okLint = { exit: 0, hits: 0, emdash_per_1000: 0 }
const backupOf = { backed_up: true, dir: '/h/.claude/edit-doc/post.md.Ab12Cd', original: '/h/.claude/edit-doc/post.md.Ab12Cd/original.md', backup_error: '' }
const backup = backupOf
const prep = (words = 6000) => ({ ...backupOf, surface: 'blog', profile: 'Draft or edit English prose', guides: ['plain-sentence-construction.md', 'ai-writing-gotchas.md'],
  words_before: words + 200, words_after: words, inventory_items: 40, authority_changes: [],
  structure_changes: [{ what: 'moved the verdict up', why: 'guide 7' }], gaps: [], sha_after: 'bbb' })
const proposal = (before, after = 'plain') => ({ before, after, rule: 'ai-writing-gotchas.md: Words', reason: 'listed word', keeps: [] })
const review = (proposals = [], extra = {}) => ({ proposals, flags: [], kept: [], capped: false, ...extra })
const conduct = (extra = {}) => ({ tampered: false, applied: [{ id: 'P1', final: 'a solid cache', note: '' }], rejected: [], tightened: [], restored: [],
  words_after: 1500, inventory: okMech, lint: okLint, sha_after: 'ccc', ...extra })
const ready = { verdict: 'READY', missing: [], findings: [], elsewhere: [], inventory: okMech, lint: okLint, reason: 'nothing found' }
const finding = (extra = {}) => ({ location: 'line 4', quote: 'robust', rule: 'gotchas', fix: 'solid', reraised: false, ...extra })
const finalOk = { inventory: okMech, lint: okLint, unconfirmed: [], breaches: [] }

async function runWith(answers, args = { target: '/tmp/post.md' }) {
  const calls = [], prompts = {}, logs = []
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    calls.push({ label, model: opts.model, effort: opts.effort })
    prompts[label.split(' ')[0]] = prompt
    const key = Object.keys(answers).find(k => label === k || label.startsWith(k))
    if (!key) throw new Error(`unexpected agent ${label}`)
    const a = answers[key]
    return typeof a === 'function' ? a(prompt, opts) : a
  }
  const result = await run(agent, parallel, pipeline, m => logs.push(m), () => {}, args, budget)
  return { result, calls, prompts, logs, labels: calls.map(c => c.label.split(' ')[0]) }
}

const base = {
  prepare: prep(),
  'review:words': review([proposal('a robust cache')]),
  'review:argument': review(),
  'review:claims': review(),
  'review:length': review(),
  'review:whole': review(),
  conduct: conduct(),
  check: ready,
}
const repairing = (check, repair, final = finalOk) => ({ ...base, check, repair, final })

test('a long document gets four reviewers and a clean check ends the run with no repair', async () => {
  const { result, labels } = await runWith(base)
  assert.deepEqual(labels.filter(l => l.startsWith('review:')).sort(), ['review:argument', 'review:claims', 'review:length', 'review:words'])
  assert.ok(!labels.includes('repair') && !labels.includes('final'))
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(labels.length, 7)
})

test('a document under 5,000 words gets one reviewer that reads the whole bundle', async () => {
  for (const words of [300, 1800, 4900]) {
    const { result, labels, prompts, calls } = await runWith({ ...base, prepare: prep(words), conduct: conduct({ words_after: words - 20 }) })
    assert.deepEqual(labels.filter(l => l.startsWith('review:')), ['review:whole'])
    assert.equal(result.clean, true, result.reasons.join('; '))
    assert.match(prompts['review:whole'], /Read the whole bundle together/)
    assert.match(prompts['review:whole'], /a decision a comment leaves open that the target closes/)
    assert.equal(calls.find(c => c.label === 'review:whole').model, 'opus')
    assert.equal(calls.find(c => c.label === 'review:whole').effort, 'high')
  }
})

test('a document of 5,000 words or more gets one reviewer per remit', async () => {
  const { labels } = await runWith({ ...base, prepare: prep(5000) })
  assert.deepEqual(labels.filter(l => l.startsWith('review:')).sort(), ['review:argument', 'review:claims', 'review:length', 'review:words'])
})

test('the conductor tightens the whole document when the whole-document reviewer was capped', async () => {
  const { prompts } = await runWith({ ...base, prepare: prep(1800), 'review:whole': review([], { capped: true }), conduct: conduct({ words_after: 1700 }) })
  assert.match(prompts.conduct, /run the skill's Pass 8 over the whole document/)
})

test('every stage runs on the model and effort set for it, and args can override one', async () => {
  const { calls } = await runWith(base, { target: '/tmp/post.md', models: { words: 'haiku' }, efforts: { check: 'max' } })
  const by = l => calls.find(c => c.label.startsWith(l))
  assert.equal(by('prepare').model, 'opus')
  assert.equal(by('review:words').model, 'haiku')
  assert.equal(by('review:argument').model, 'sonnet')
  assert.equal(by('check').effort, 'max')
  assert.equal(by('conduct').effort, 'high')
})

test('a backup the prepare stage could not confirm stops the run with nothing edited', async () => {
  const { result, labels } = await runWith({ ...base, prepare: { ...prep(), backed_up: false, backup_error: 'cmp: differ' } })
  assert.equal(result.clean, false)
  assert.deepEqual(labels, ['prepare'])
  assert.match(result.reason, /cmp: differ; nothing was edited/)
})

test('the prepare stage backs up first and is told to stop and edit nothing if that fails', async () => {
  const { prompts } = await runWith(base)
  assert.match(prompts.prepare, /1\. Back up before anything else\. Run exactly this, as your first tool call/)
  assert.match(prompts.prepare, /If any command fails, stop at once: edit nothing/)
})

test('every later stage uses the backup directory the prepare stage created', async () => {
  const { result, prompts } = await runWith(base)
  assert.equal(result.original, backup.original)
  assert.match(prompts['review:words'], /\/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/inventory\.md/)
  assert.match(prompts.check, /content-inventory\.py check '\/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/original\.md' '\/tmp\/post\.md'/)
})

test('the backup is a fresh mktemp directory per run, so reruns never overwrite an original', async () => {
  const { prompts } = await runWith(base)
  assert.match(prompts.prepare, /mktemp -d "\$HOME"\/\.claude\/edit-doc\/'post\.md'\.XXXXXX/)
  assert.match(prompts.prepare, /cmp '\/tmp\/post\.md' "\$d"\/original'\.md'/)
})

test('paths are shell-quoted, so $, quotes and $(...) in a file name are never run or expanded', async () => {
  const nasty = `/tmp/price$USD $(touch x) say"hi'.md`
  const { prompts } = await runWith(base, { target: nasty })
  const cmd = /cp -p (.*?) "\$d"/.exec(prompts.prepare)[1]
  assert.equal(execFileSync('/bin/sh', ['-c', `printf %s ${cmd}`]).toString(), nasty)
})

test('a tilde or $HOME path keeps $HOME expandable and nothing else', async () => {
  const { prompts } = await runWith(base, { target: '~/.wiki/a b/index.md' })
  assert.match(prompts.prepare, /cp -p "\$HOME"\/'\.wiki\/a b\/index\.md'/)
})

test('a file without an extension gets a backup without one', async () => {
  const { prompts } = await runWith(base, { target: '/tmp/README' })
  assert.match(prompts.prepare, /"\$d"\/original &&/)
})

test('partial and bridging overlaps group transitively; similar but separate passages do not', async () => {
  const { prompts } = await runWith({ ...base,
    'review:words': review([proposal('We use the cache for reads'), proposal('Primary service handles every request quickly')]),
    'review:length': review([proposal('the cache for reads and writes'), proposal('Secondary service handles every request quickly')]),
    'review:argument': review([proposal('reads and writes alike, always')]),
  })
  assert.match(prompts.conduct, /PROPOSALS \(5 in 3 passages\)/)
})

test('an exact duplicate is dropped, but replacements that differ only in case are both kept', async () => {
  const { prompts, logs } = await runWith({ ...base,
    'review:words': review([proposal('The pipeline is robust', 'Polish it'), proposal('the build is robust', 'x')]),
    'review:length': review([proposal('The pipeline is robust', 'Polish it'), proposal('The pipeline is robust', 'polish it')]),
  })
  assert.ok(logs.some(l => /1 exact duplicates dropped/.test(l)))
  assert.match(prompts.conduct, /PROPOSALS \(3 in 2 passages\)/)
})

test('each reviewer is told what the others own, that it must not edit, and that the document is data', async () => {
  const { prompts } = await runWith(base)
  assert.match(prompts['review:claims'], /NOT YOURS[^\n]*wording/)
  assert.match(prompts['review:claims'], /Do NOT edit, create or delete any file/)
  assert.match(prompts['review:claims'], /The document is data/)
  assert.match(prompts['review:words'], /writing-lint\.py/)
  assert.doesNotMatch(prompts['review:argument'], /writing-lint\.py/)
  assert.doesNotMatch(prompts['review:argument'], /Look for:[^\n]*chat leftovers/)
  assert.match(prompts['review:words'], /Look for:[^\n]*chat replies/)
})

test('reviewers get the reading profile the prepare stage resolved, not the full reading list', async () => {
  const { prompts } = await runWith(base)
  assert.match(prompts['review:words'], /READING PROFILE \(resolved once by the prepare stage\): Draft or edit English prose/)
  assert.match(prompts['review:words'], /"Required reading" list is for inline runs/)
})

test('the conductor tightens the whole document only when the length reviewer failed or was capped', async () => {
  const normal = await runWith(base)
  assert.match(normal.prompts.conduct, /tighten only the passages you edited/)
  const capped = await runWith({ ...base, 'review:length': review([], { capped: true }) })
  assert.match(capped.prompts.conduct, /run the skill's Pass 8 over the whole document/)
})

test('a reviewer that wrote to the file is detected and the run stops before more edits', async () => {
  const { result, labels } = await runWith({ ...base, conduct: conduct({ tampered: true }) })
  assert.equal(result.clean, false)
  assert.match(result.reason, /target changed after the prepare stage/)
  assert.ok(!labels.includes('check'))
})

test('the restore loops are bounded in the prompts', async () => {
  const { prompts } = await runWith(repairing({ ...ready, verdict: 'NOT READY', findings: [finding()] },
    { tampered: false, resolved: [{ ref: 'F1', passage: 'solid' }], unresolved: [], words_after: 1490 }))
  for (const p of [prompts.conduct, prompts.repair]) {
    assert.match(p, /at most three times/)
    assert.match(p, /Stop at once on exit 2/)
    assert.doesNotMatch(p, /until it exits 0/)
  }
})

test('a NOT READY check gets one repair and one final confirmation, and no second check', async () => {
  const { result, labels } = await runWith(repairing({ ...ready, verdict: 'NOT READY', findings: [finding()] },
    { tampered: false, resolved: [{ ref: 'F1', passage: 'a solid cache' }], unresolved: [], words_after: 1490 }))
  assert.deepEqual(labels.filter(l => ['check', 'repair', 'final'].includes(l)), ['check', 'repair', 'final'])
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(result.words.after, 1490)
})

test('a repair that ignores a missing item or finding is not clean', async () => {
  const { result } = await runWith(repairing(
    { ...ready, verdict: 'NOT READY', missing: [{ item: 'I3', original: 'only when offline', now: 'gone' }], findings: [finding()] },
    { tampered: false, resolved: [], unresolved: [], words_after: 1500 }))
  assert.equal(result.clean, false)
  assert.ok(result.reasons.some(r => /2 references not accounted for \(M1, F1\)/.test(r)))
})

test('a fix the final reader cannot find, or a breach it finds, is not clean', async () => {
  const c = { ...ready, verdict: 'NOT READY', findings: [finding()] }
  const r = { tampered: false, resolved: [{ ref: 'F1', passage: 'solid' }], unresolved: [], words_after: 1500 }
  assert.equal((await runWith(repairing(c, r, { ...finalOk, unconfirmed: ['F1'] }))).result.clean, false)
  assert.equal((await runWith(repairing(c, r, { ...finalOk, breaches: ['"robust" in line 4'] }))).result.clean, false)
})

test('a finding the repair could not apply keeps the run from being clean', async () => {
  const { result } = await runWith(repairing({ ...ready, verdict: 'NOT READY', findings: [finding({ reraised: true })] },
    { tampered: false, resolved: [], unresolved: [{ ref: 'F1', reason: 'would lose I7' }], words_after: 1500 }))
  assert.equal(result.clean, false)
})

test('a READY verdict with a failed inventory check or a lint that could not run goes to repair', async () => {
  for (const c of [{ ...ready, inventory: { exit: 1, total: 40, missing: ['number: 30%'] } }, { ...ready, lint: { ...okLint, exit: 2 } }]) {
    const { labels } = await runWith(repairing(c, { tampered: false, resolved: [{ ref: 'X1', passage: '30%' }], unresolved: [], words_after: 1500 }))
    assert.ok(labels.includes('repair'))
  }
})

test('a lint that still cannot run at the end keeps the run from being clean', async () => {
  const { result } = await runWith(repairing({ ...ready, lint: { ...okLint, exit: 2 } },
    { tampered: false, resolved: [], unresolved: [], words_after: 1500 }, { ...finalOk, lint: { ...okLint, exit: 2 } }))
  assert.equal(result.clean, false)
  assert.ok(result.reasons.some(r => /lint could not run/.test(r)))
})

test('missing values after the repair keep the run from being clean', async () => {
  const { result } = await runWith(repairing({ ...ready, verdict: 'NOT READY', missing: [{ item: 'I3', original: 'on 0.76', now: 'gone' }] },
    { tampered: false, resolved: [{ ref: 'M1', passage: 'on 0.76' }], unresolved: [], words_after: 1500 },
    { ...finalOk, inventory: { exit: 1, total: 40, missing: ['number: 0.76'] } }))
  assert.equal(result.clean, false)
  assert.ok(result.reasons.some(r => /missing number: 0\.76/.test(r)))
})

test('a reviewer that dies makes the run incomplete, and the conductor is told to cover its remit', async () => {
  const { result, prompts, logs } = await runWith({ ...base, 'review:claims': null })
  assert.equal(result.clean, false)
  assert.deepEqual(result.reviewers.lost, ['claims'])
  assert.ok(logs.some(l => /INCOMPLETE: claims/.test(l)))
  assert.match(prompts.conduct, /These reviewers failed[^\n]*claims/)
})

test('the check sees each rejected proposal with its text and reason, not just an id', async () => {
  const { prompts } = await runWith({ ...base, conduct: conduct({ applied: [], rejected: [{ id: 'P1', reason: 'literal technical use' }] }) })
  assert.match(prompts.check, /P1 \[ai-writing-gotchas\.md: Words\]/)
  assert.match(prompts.check, /proposed: "a robust cache"/)
  assert.match(prompts.check, /rejected because: literal technical use/)
})

test('the result carries a change ledger with the text actually written', async () => {
  const { result } = await runWith(base)
  assert.deepEqual(result.changes, [{ id: 'P1', remit: 'words', rule: 'ai-writing-gotchas.md: Words', before: 'a robust cache', after: 'a solid cache', note: '' }])
})

test('every failure exit carries the target, the original and the inventory paths', async () => {
  const none = await runWith({ ...base, prepare: null })
  assert.equal(none.result.target, '/tmp/post.md')
  assert.match(none.result.reason, /backup is under/)
  for (const answers of [{ ...base, conduct: null }, { ...base, check: null }]) {
    const { result } = await runWith(answers)
    assert.equal(result.clean, false)
    assert.equal(result.target, '/tmp/post.md')
    assert.equal(result.original, backup.original)
    assert.match(result.inventory, /inventory\.md$/)
  }
})

test('a missing target is refused', async () => {
  await assert.rejects(runWith(base, {}), /args\.target/)
})

test('a run that ends more than 2% longer than it started is not clean', async () => {
  const grown = await runWith({ ...base, prepare: { ...prep(1000), words_before: 1000 }, conduct: conduct({ words_after: 1030 }) })
  assert.equal(grown.result.clean, false)
  assert.ok(grown.result.reasons.some(r => /grew by 30 words/.test(r)))
  const level = await runWith({ ...base, prepare: { ...prep(1000), words_before: 1000 }, conduct: conduct({ words_after: 1015 }) })
  assert.equal(level.result.clean, true, level.result.reasons.join('; '))
})

test('a fault the check finds in another file goes to the author, not to the repair', async () => {
  const { result, labels } = await runWith({ ...base, check: { ...ready, elsewhere: [{ file: 'ai-writing-gotchas.md', issue: 'now disagrees with the target' }] } })
  assert.ok(!labels.includes('repair'))
  assert.equal(result.clean, true)
  assert.ok(result.flags.some(f => f.location === 'ai-writing-gotchas.md'))
})

test('every stage is told to edit no file but the target and to batch its reads and edits into few turns', async () => {
  const { prompts } = await runWith(repairing({ ...ready, verdict: 'NOT READY', findings: [finding()] },
    { tampered: false, resolved: [{ ref: 'F1', passage: 'solid' }], unresolved: [], words_after: 1490 }))
  for (const k of ['prepare', 'review:words', 'conduct', 'check', 'repair']) {
    assert.match(prompts[k], /No stage of this run edits any file but the target/)
    assert.match(prompts[k], /Every turn re-sends your whole context/)
    assert.match(prompts[k], /one Read call per file, all sent together/)
    assert.match(prompts[k], /send independent edits together/)
  }
  assert.match(prompts.check, /goes under elsewhere/)
})

test('the length reviewer is asked for every cut and the conductor must pay for additions', async () => {
  const { prompts, logs } = await runWith({ ...base, 'review:length': review([], { words_saved: 240 }) })
  assert.match(prompts['review:length'], /15 to 20 per cent longer/)
  assert.match(prompts.conduct, /recover them by tightening the same passage/)
  assert.ok(logs.some(l => /proposals save 240 words/.test(l)))
})

test('every stage protects code, charts and raw data, and reads the surface guides', async () => {
  const { prompts } = await runWith(base)
  for (const k of ['prepare', 'review:words', 'review:argument', 'review:length', 'conduct', 'check']) {
    assert.match(prompts[k], /PROTECTED CONTENT: code blocks, diagrams and charts/)
  }
  assert.match(prompts['review:length'], /protected content \(see above\) is never a length proposal/)
  assert.match(prompts['review:argument'], /never a table of raw data/)
  assert.match(prompts.check, /every protected block shortened, cut or turned into prose/)
  assert.match(prompts['review:words'], /plus every surface guide in it/)
  assert.match(prompts.prepare, /including any surface guide it names/)
})

test('a document with tests gets a tests reviewer; one without does not', async () => {
  const withTests = await runWith({ ...base, prepare: { ...prep(), has_tests: true }, 'review:tests': review() })
  assert.ok(withTests.labels.includes('review:tests'))
  assert.match(withTests.prompts['review:tests'], /Would each test fail on the code before the fix\?/)
  assert.match(withTests.prompts['review:tests'], /exist at the cited commit, or is it clearly marked as proposed/)
  const without = await runWith(base)
  assert.ok(!without.labels.includes('review:tests'))
})

test('sources reach the claims reviewer and the check, which also lints the attachments', async () => {
  const { prompts } = await runWith(base, { target: '/tmp/post.md', sources: ['/tmp/attachments/', 'ncu-ad-manager at 544654dfc'] })
  for (const k of ['review:claims', 'check']) {
    assert.match(prompts[k], /SOURCES OF TRUTH[^\n]*\n- \/tmp\/attachments\/\n- ncu-ad-manager at 544654dfc/)
  }
  assert.match(prompts['review:claims'], /Open every source the header lists/)
  assert.match(prompts.check, /run the leftovers search on every source file that ships with the document/)
  const none = await runWith(base)
  assert.doesNotMatch(none.prompts.check, /SOURCES OF TRUTH|leftovers search on every source file/)
})

test('the length reviewer reads the lint, so it sees the long-paragraph pointers', async () => {
  const { prompts } = await runWith(base)
  assert.match(prompts['review:length'], /writing-lint\.py/)
})
