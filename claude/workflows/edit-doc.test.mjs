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
const backup = { backed_up: true, dir: '/h/.claude/edit-doc/post.md.Ab12Cd', original: '/h/.claude/edit-doc/post.md.Ab12Cd/original.md', backup_error: '' }
const prep = (words = 1500, extra = {}) => ({ ...backup, surface: 'blog', surface_guides: [], words_before: words, inventory_items: 40, quoted_elsewhere: 0, has_tests: false, lint: okLint, sha: 'aaa', ...extra })
const change = { pass: 'words', before: 'a robust cache', after: 'a solid cache', rule: 'checklist: Words' }
const edited = (extra = {}) => ({ tampered: false, authority_changes: [], structure_changes: [{ what: 'moved the verdict up', why: 'checklist: Structure' }], gaps: [], changes: [change], flags: [], kept: [], restored: [],
  words_after: 1520, inventory: okMech, lint: okLint, sha_after: 'bbb', ...extra })
const structured = (words = 5900, extra = {}) => ({ tampered: false, authority_changes: [], structure_changes: [{ what: 'moved the verdict up', why: 'checklist: Structure' }], gaps: [], words_after: words, inventory: okMech, sha_after: 'bbb', ...extra })
const proposal = (before, after = 'plain') => ({ before, after, rule: 'ai-writing-gotchas.md: Words', reason: 'listed word', keeps: [] })
const review = (proposals = [], extra = {}) => ({ proposals, flags: [], kept: [], capped: false, ...extra })
const conducted = (extra = {}) => ({ tampered: false, applied: [{ id: 'P1', final: 'a solid cache', note: '' }], rejected: [], restored: [], words_after: 5920, inventory: okMech, lint: okLint, sha_after: 'ccc', ...extra })
const cut = (before, saves = 40) => ({ before, after: '', saves, keeps: [], reason: 'restatement' })
const cuts = (list = [cut('a line the Description repeats')], extra = {}) => ({ cuts: list, total_saves: list.reduce((n, c) => n + c.saves, 0), capped: false, ...extra })
const tightened = (before = 1520, after = 1450, extra = {}) => ({ tampered: false, words_before: before, words_after: after, taken: 1, declined: [], beyond: [], restored: [], inventory: okMech, inbound: okMech, sha_after: 'ddd', ...extra })
const finding = (extra = {}) => ({ ref: 'F1', location: 'line 4', quote: 'robust', rule: 'checklist: Words', fix: 'solid', reraised: false, ...extra })
const checked = (words = 1450, extra = {}) => ({ tampered: false, verdict_before: 'READY', findings: [], resolved: [], unresolved: [], elsewhere: [], words_after: words, inventory: okMech, inbound: okMech, lint: okLint, sha_after: 'eee', ...extra })

async function runWith(answers, args = { target: '/tmp/post.md' }, { noStageAgent = false } = {}) {
  const calls = [], prompts = {}, logs = []
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    calls.push({ label, model: opts.model, effort: opts.effort, agentType: opts.agentType })
    if (noStageAgent && opts.agentType) throw new Error(`agent({agentType}): agent type '${opts.agentType}' not found. Available agents: claude, Explore`)
    prompts[label.split(' ')[0]] = prompt
    const key = Object.keys(answers).find(k => label === k || label.startsWith(k))
    if (!key) throw new Error(`unexpected agent ${label}`)
    const a = answers[key]
    return typeof a === 'function' ? a(prompt, opts) : a
  }
  const result = await run(agent, parallel, pipeline, m => logs.push(m), () => {}, args, budget)
  return { result, calls, prompts, logs, labels: calls.map(c => c.label.split(' ')[0]) }
}

const short = { prepare: prep(), edit: edited(), cuts: cuts(), tighten: tightened(), check: checked() }
const long = {
  prepare: prep(6000), structure: structured(),
  'review:words': review([proposal('a robust cache')]), 'review:argument': review(), 'review:claims': review(), 'review:tests': review(), 'review:whole': review([proposal('a robust cache')]),
  conduct: conducted(), cuts: cuts(), tighten: tightened(5920, 5700), check: checked(5700),
}
const mid = { ...long, prepare: prep(3000), structure: structured(3010), conduct: conducted({ words_after: 3020 }), tighten: tightened(3020, 2900), check: checked(2900) }

// ---------------------------------------------------------------- paths

test('a document under 2,500 words takes the short path: five agents, one writer, no reviewers', async () => {
  for (const words of [200, 1500, 2499]) {
    const { result, labels } = await runWith({ ...short, prepare: prep(words), edit: edited({ words_after: words + 10 }), tighten: tightened(words + 10, words - 20), check: checked(words - 20) })
    assert.deepEqual(labels, ['prepare', 'edit', 'cuts', 'tighten', 'check'])
    assert.equal(result.clean, true, result.reasons.join('; '))
    assert.equal(result.path, 'short')
    assert.equal(result.reviewers, null)
  }
})

test('from 2,500 to 5,000 words the long path runs with one reviewer for the whole document', async () => {
  const { result, labels, prompts } = await runWith(mid)
  assert.deepEqual(labels, ['prepare', 'structure', 'review:whole', 'conduct', 'cuts', 'tighten', 'check'])
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(result.path, 'long')
  assert.match(prompts['review:whole'], /Read the whole bundle together/)
  assert.doesNotMatch(prompts['review:whole'], /in full as well; your remit is where the full guide/)
})

test('from 5,000 words one reviewer per remit reads its full guides; a tests reviewer only when the document has tests', async () => {
  const { result, labels, prompts } = await runWith(long)
  assert.deepEqual(labels.filter(l => l.startsWith('review:')).sort(), ['review:argument', 'review:claims', 'review:words'])
  assert.equal(result.path, 'long-split')
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.match(prompts['review:words'], /Read ai-writing-gotchas\.md and plain-sentence-construction\.md in \$HOME\/\.wiki\/personal\/writing in full as well/)
  assert.deepEqual(result.reviewers, { ran: ['words', 'argument', 'claims'], lost: [], capped: [] })
  const withTests = await runWith({ ...long, prepare: prep(6000, { has_tests: true }) })
  assert.ok(withTests.labels.includes('review:tests'))
  assert.match(withTests.prompts['review:tests'], /would each test fail on the code before the fix/)
})

test('there is no length reviewer; cutting belongs to the cuts and tighten stages in every path', async () => {
  const { labels, prompts } = await runWith(long)
  assert.ok(!labels.includes('review:length'))
  for (const k of ['review:words', 'review:argument', 'review:claims']) assert.match(prompts[k], /NOT YOURS[^\n]*cutting length \(the tighten stage\)/, k)
  assert.doesNotMatch(source, /review:length/)
})

// ---------------------------------------------------------------- models

test('mechanical stages run on Sonnet, judgement on Opus, and the check follows the path', async () => {
  const s = await runWith(short)
  const by = (calls, l) => calls.find(c => c.label.startsWith(l))
  assert.deepEqual([by(s.calls, 'prepare').model, by(s.calls, 'prepare').effort], ['sonnet', 'medium'])
  assert.deepEqual([by(s.calls, 'edit').model, by(s.calls, 'edit').effort], ['opus', 'high'])
  assert.deepEqual([by(s.calls, 'cuts').model, by(s.calls, 'cuts').effort], ['sonnet', 'medium'])
  assert.deepEqual([by(s.calls, 'tighten').model, by(s.calls, 'tighten').effort], ['opus', 'high'])
  assert.deepEqual([by(s.calls, 'check').model, by(s.calls, 'check').effort], ['sonnet', 'high'])
  const l = await runWith(long)
  assert.deepEqual([by(l.calls, 'check').model, by(l.calls, 'check').effort], ['opus', 'medium'])
  assert.deepEqual([by(l.calls, 'structure').model, by(l.calls, 'conduct').model, by(l.calls, 'review:claims').model, by(l.calls, 'review:words').model], ['opus', 'opus', 'opus', 'sonnet'])
})

test('args.models and args.efforts override one stage, on either path', async () => {
  const by = (calls, l) => calls.find(c => c.label.startsWith(l))
  const s = await runWith(short, { target: '/tmp/post.md', models: { cuts: 'haiku', check: 'opus' }, efforts: { edit: 'max' } })
  assert.equal(by(s.calls, 'cuts').model, 'haiku')
  assert.equal(by(s.calls, 'check').model, 'opus')
  assert.equal(by(s.calls, 'edit').effort, 'max')
  const l = await runWith(long, { target: '/tmp/post.md', models: { words: 'haiku', check: 'sonnet' }, efforts: { check: 'max' } })
  assert.equal(by(l.calls, 'review:words').model, 'haiku')
  assert.deepEqual([by(l.calls, 'check').model, by(l.calls, 'check').effort], ['sonnet', 'max'])
})

test('the tighten and words stages use the model and effort set in /tighten and /plain-words', () => {
  const front = f => Object.fromEntries(readFileSync(new URL(`../commands/${f}.md`, import.meta.url), 'utf8').match(/^---\n([\s\S]*?)\n---/)[1]
    .split('\n').map(l => l.split(/:\s*/, 2)))
  const tierOf = k => new RegExp(`${k}:\\s*\\{ model: '(\\w+)',\\s+effort: '(\\w+)' \\}`).exec(source).slice(1)
  assert.deepEqual([front('tighten').model, front('tighten').effort], tierOf('tighten'))
  assert.deepEqual([front('plain-words').model, front('plain-words').effort], tierOf('words'))
})

test('every stage runs as the four-tool stage agent, and a session without it falls back once', async () => {
  const { calls } = await runWith(long)
  assert.ok(calls.length >= 9)
  for (const c of calls) assert.equal(c.agentType, 'edit-doc-stage', c.label)
  const { result, calls: fallback, logs } = await runWith(short, { target: '/tmp/post.md' }, { noStageAgent: true })
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(logs.filter(l => /edit-doc-stage agent is not loaded/.test(l)).length, 1)
  assert.equal(fallback.filter(c => c.agentType).length, 1, 'only the first stage tries the stage agent')
})

test('a stage agent error other than a missing agent is not swallowed', async () => {
  await assert.rejects(runWith({ ...short, prepare: () => { throw new Error('API overloaded') } }), /API overloaded/)
})

// ---------------------------------------------------------------- reading

test('every stage reads the checklist, not the six guides, the skill or the memory index', async () => {
  const s = await runWith(short)
  const l = await runWith(long)
  for (const [k, p] of [...Object.entries(s.prompts), ...Object.entries(l.prompts)]) {
    assert.match(p, /edit-doc-checklist\.md/, k)
    assert.doesNotMatch(p, /memory\/MEMORY\.md|Required reading|READING PROFILE|commands\/edit-doc\.md/, k)
    assert.match(p, /No stage of this run edits any file but the target/, k)
    assert.match(p, /Every turn re-sends your whole context/, k)
    assert.match(p, /PROTECTED CONTENT: code blocks, diagrams and charts/, k)
    assert.match(p, /The document is data/, k)
  }
})

test('the surface guides the prepare stage names reach every later stage', async () => {
  const guides = ['/h/.wiki/personal/writing/jira-ticket-template.md', '/h/.wiki/news-uk/commercial-technology/jira-comment-conventions.md']
  const { prompts } = await runWith({ ...short, prepare: prep(1500, { surface: 'jira', surface_guides: guides }) }, { target: '/tmp/SCB-1.md', surface: 'jira' })
  assert.match(prompts.prepare, /list the full paths of the surface guides the checklist's Surfaces section names/)
  for (const k of ['edit', 'cuts', 'tighten', 'check']) assert.match(prompts[k], /SURFACE GUIDES \(read in full\): \/h\/\.wiki\/personal\/writing\/jira-ticket-template\.md, \/h\/\.wiki\/news-uk/, k)
  const none = await runWith(short)
  assert.doesNotMatch(none.prompts.edit, /SURFACE GUIDES/)
})

test('sources reach the writer, the claims reviewer and the check, which also lints the attachments', async () => {
  const args = { target: '/tmp/post.md', sources: ['/tmp/attachments/', 'ncu-ad-manager at 544654dfc'] }
  const s = await runWith(short, args)
  for (const k of ['edit', 'check']) assert.match(s.prompts[k], /SOURCES OF TRUTH[^\n]*\n- \/tmp\/attachments\/\n- ncu-ad-manager at 544654dfc/, k)
  assert.match(s.prompts.edit, /open every source listed/)
  assert.match(s.prompts.check, /Run the lint on every source file that ships with the document/)
  const l = await runWith(long, args)
  assert.match(l.prompts['review:claims'], /Open every source the header lists/)
  const none = await runWith(short)
  assert.doesNotMatch(none.prompts.check, /SOURCES OF TRUTH|lint on every source file/)
})

// ---------------------------------------------------------------- prepare

test('the prepare stage backs up first, edits nothing, takes the inventory, finds inbound quotes and counts', async () => {
  const { prompts } = await runWith(short, { target: '/blog/post.md' })
  assert.match(prompts.prepare, /STAGE: prepare\. Do NOT edit the target/)
  assert.match(prompts.prepare, /1\. Back up before anything else\. Run exactly this, as your first tool call/)
  assert.match(prompts.prepare, /mktemp -d "\$HOME"\/\.claude\/edit-doc\/'post\.md'\.XXXXXX/)
  assert.match(prompts.prepare, /cmp '\/blog\/post\.md' "\$d"\/original'\.md'/)
  assert.match(prompts.prepare, /inbound-quotes\.py find '<dir>\/original\.md' --in '\/blog' --self '\/blog\/post\.md'/)
  assert.match(prompts.prepare, /an item of kind quote \("quoted by <file>:<line>"\)/)
  assert.match(prompts.prepare, /wc -w on the target as words_before/)
})

test('a backup the prepare stage could not confirm stops the run with nothing edited', async () => {
  const { result, labels } = await runWith({ ...short, prepare: { ...prep(), backed_up: false, backup_error: 'cmp: differ' } })
  assert.equal(result.clean, false)
  assert.deepEqual(labels, ['prepare'])
  assert.match(result.reason, /cmp: differ; nothing was edited/)
})

test('every later stage uses the backup directory the prepare stage created', async () => {
  const { result, prompts } = await runWith(long)
  assert.equal(result.original, backup.original)
  assert.match(prompts['review:words'], /\/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/inventory\.md/)
  assert.match(prompts.check, /content-inventory\.py check '\/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/original\.md' '\/tmp\/post\.md'/)
  assert.match(prompts.tighten, /the backup is \/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/original\.md, the inventory \/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/inventory\.md/)
})

test('paths are shell-quoted, so $, quotes and $(...) in a file name are never run or expanded', async () => {
  const nasty = `/tmp/price$USD $(touch x) say"hi'.md`
  const { prompts } = await runWith(short, { target: nasty })
  const cmd = /cp -p (.*?) "\$d"/.exec(prompts.prepare)[1]
  assert.equal(execFileSync('/bin/sh', ['-c', `printf %s ${cmd}`]).toString(), nasty)
})

test('a tilde or $HOME path keeps $HOME expandable and nothing else', async () => {
  const { prompts } = await runWith(short, { target: '~/.wiki/a b/index.md' })
  assert.match(prompts.prepare, /cp -p "\$HOME"\/'\.wiki\/a b\/index\.md'/)
})

test('a file without an extension gets a backup without one', async () => {
  const { prompts } = await runWith(short, { target: '/tmp/README' })
  assert.match(prompts.prepare, /"\$d"\/original &&/)
})

test('a missing target is refused', async () => {
  await assert.rejects(runWith(short, {}), /args\.target/)
})

test('args.related adds folders and files to the quote search, and a tilde path keeps $HOME expandable', async () => {
  const { prompts } = await runWith(short, { target: '/blog/post.md', related: ['/wiki/series', '~/notes/index.md'] })
  for (const k of ['prepare', 'tighten', 'check']) assert.match(prompts[k], /--in '\/blog' --in '\/wiki\/series' --in "\$HOME"\/'notes\/index\.md'/, k)
})

// ---------------------------------------------------------------- edit and structure

test('the writer on the short path runs every pass, checks the sha, adds without cutting, and reports a change ledger', async () => {
  const { result, prompts } = await runWith(short)
  const p = prompts.edit
  assert.match(p, /shasum -a 256 on the target\. If it is not aaa/)
  for (const pass of ['Authority calibration', 'Structure: read the outline first', 'Sentences, then Words and punctuation', 'Argument and tone, then Page', 'Claims and evidence', 'British English']) assert.match(p, new RegExp(pass), pass)
  assert.match(p, /quantitative doubt \(number, identifier, version, path, statistic\) goes under flags/)
  assert.match(p, /Do not cut the document to make room for what you add: a separate tightener cuts after you/)
  assert.match(p, /at most three times/)
  assert.deepEqual(result.changes, [change])
  assert.deepEqual(result.structure, [{ what: 'moved the verdict up', why: 'checklist: Structure' }])
})

test('the structure stage on the long path runs only the authority and structure passes', async () => {
  const { prompts } = await runWith(long)
  assert.match(prompts.structure, /STAGE: structure\. You run the authority and structure passes only/)
  assert.match(prompts.structure, /shasum -a 256 on the target\. If it is not aaa/)
  assert.doesNotMatch(prompts.structure, /British English/)
})

test('a changed file at the edit, structure, conduct, tighten or check stage stops the run', async () => {
  const cases = [
    [{ ...short, edit: edited({ tampered: true }) }, 'edit', 'target changed after the backup'],
    [{ ...long, structure: structured(5900, { tampered: true }) }, 'structure', 'target changed after the backup'],
    [{ ...long, conduct: conducted({ tampered: true }) }, 'conduct', 'a reviewer may have written to it'],
    [{ ...short, tighten: tightened(1520, 1450, { tampered: true }) }, 'tighten', 'target changed before the tighten stage'],
    [{ ...short, check: checked(1450, { tampered: true }) }, 'check', 'target changed before the check'],
  ]
  for (const [answers, stage, text] of cases) {
    const { result, labels } = await runWith(answers)
    assert.equal(result.clean, false, stage)
    assert.equal(result.stage, stage)
    assert.match(result.reason, new RegExp(text), stage)
    assert.equal(labels[labels.length - 1], stage, stage)
  }
})

test('every failure exit carries the target, the original and the inventory paths', async () => {
  const none = await runWith({ ...short, prepare: null })
  assert.equal(none.result.target, '/tmp/post.md')
  assert.match(none.result.reason, /backup is under/)
  for (const answers of [{ ...short, edit: null }, { ...long, conduct: null }, { ...short, tighten: null }, { ...short, check: null }]) {
    const { result } = await runWith(answers)
    assert.equal(result.clean, false)
    assert.equal(result.target, '/tmp/post.md')
    assert.equal(result.original, backup.original)
    assert.match(result.inventory, /inventory\.md$/)
  }
})

// ---------------------------------------------------------------- review and conduct (long path)

test('partial and bridging overlaps group transitively; similar but separate passages do not', async () => {
  const { prompts } = await runWith({ ...long,
    'review:words': review([proposal('We use the cache for reads'), proposal('Primary service handles every request quickly')]),
    'review:claims': review([proposal('the cache for reads and writes'), proposal('Secondary service handles every request quickly')]),
    'review:argument': review([proposal('reads and writes alike, always')]),
  })
  assert.match(prompts.conduct, /PROPOSALS \(5 in 3 passages\)/)
})

test('an exact duplicate is dropped, but replacements that differ only in case are both kept', async () => {
  const { prompts, logs } = await runWith({ ...long,
    'review:words': review([proposal('The pipeline is robust', 'Polish it'), proposal('the build is robust', 'x')]),
    'review:claims': review([proposal('The pipeline is robust', 'Polish it'), proposal('The pipeline is robust', 'polish it')]),
  })
  assert.ok(logs.some(l => /1 exact duplicates dropped/.test(l)))
  assert.match(prompts.conduct, /PROPOSALS \(3 in 2 passages\)/)
})

test('each reviewer is told what the others own, that it must not edit, and which lint to run', async () => {
  const { prompts } = await runWith(long)
  assert.match(prompts['review:claims'], /NOT YOURS[^\n]*wording/)
  assert.match(prompts['review:claims'], /Do NOT edit, create or delete any file/)
  assert.match(prompts['review:words'], /writing-lint\.py/)
  assert.doesNotMatch(prompts['review:argument'], /writing-lint\.py/)
  assert.match(prompts['review:argument'], /claims more scope than the body supports/)
})

test('a reviewer that dies makes the run incomplete, and the writer is told to cover its remit', async () => {
  const { result, prompts, logs } = await runWith({ ...long, 'review:claims': null })
  assert.equal(result.clean, false)
  assert.deepEqual(result.reviewers.lost, ['claims'])
  assert.ok(logs.some(l => /INCOMPLETE: claims/.test(l)))
  assert.match(prompts.conduct, /These reviewers failed[^\n]*claims/)
})

test('the writer rules on proposals without cutting, and the check sees each rejected one with its text and reason', async () => {
  const { result, prompts } = await runWith({ ...long, conduct: conducted({ applied: [], rejected: [{ id: 'P1', reason: 'literal technical use' }] }) })
  assert.match(prompts.conduct, /shasum -a 256 on the target\. If it is not bbb/)
  assert.match(prompts.conduct, /Fix only the seams your edits left\. Do not cut the document/)
  assert.match(prompts.check, /P1 \[ai-writing-gotchas\.md: Words\]/)
  assert.match(prompts.check, /proposed: "a robust cache"/)
  assert.match(prompts.check, /rejected because: literal technical use/)
  assert.deepEqual(result.rejected, [{ id: 'P1', reason: 'literal technical use' }])
  const applied = await runWith(long)
  assert.deepEqual(applied.result.changes, [{ pass: 'words', before: 'a robust cache', after: 'a solid cache', rule: 'ai-writing-gotchas.md: Words', note: '' }])
  assert.doesNotMatch((await runWith(short)).prompts.check, /REJECTED PROPOSALS/)
})

// ---------------------------------------------------------------- cuts and tighten

test('a cheap reader proposes every cut with the words it saves, and the tightener is given the total as the mark', async () => {
  const { prompts, logs } = await runWith({ ...short, cuts: cuts([cut('a line the Description repeats', 40), cut('a closing recap', 25)]) })
  assert.match(prompts.cuts, /STAGE: cuts\. Do NOT edit, create or delete any file/)
  assert.match(prompts.cuts, /The target is 1520 words; the original had 1500/)
  assert.match(prompts.cuts, /15 to 20 per cent longer/)
  assert.match(prompts.cuts, /cover the last sentence of each paragraph/)
  assert.ok(logs.some(l => /cuts: 2 proposed, 65 words/.test(l)))
  const t = prompts.tighten
  assert.match(t, /lists 2 cuts below that it says save 65 words in all; that total is the mark to reach or explain/)
  assert.match(t, /PROPOSED CUTS \(2, 65 words\)/)
  assert.match(t, /C1 saves 40 \(restatement\)\n   before: a line the Description repeats\n   after: \(delete\)/)
  assert.match(t, /Then look for what the proposer missed and cut that too/)
})

test('the tightener follows /tighten from step 3, checks the sha, has the ceiling, and runs both checks', async () => {
  const { prompts } = await runWith(short)
  const p = prompts.tighten
  assert.match(p, /Read \$HOME\/Developer\/dotfiles\/claude\/commands\/tighten\.md and follow its steps 3 to 5/)
  assert.match(p, /shasum -a 256 on the target\. If it is not bbb/)
  assert.match(p, /The target is 1520 words, the original had 1500, and the run is not clean above 1530/)
  assert.match(p, /The aim is a document shorter than it started/)
  assert.match(p, /content-inventory\.py check '\/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/original\.md' '\/tmp\/post\.md'/)
  assert.match(p, /inbound-quotes\.py check '\/h\/\.claude\/edit-doc\/post\.md\.Ab12Cd\/original\.md' '\/tmp\/post\.md' --in '\/tmp'/)
  assert.match(p, /at most three times/)
  assert.match(p, /Stop at once on exit 2/)
})

test('a cuts proposer that dies does not stop the run; the tightener works without proposals', async () => {
  const { result, prompts, logs } = await runWith({ ...short, cuts: null })
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.ok(logs.some(l => /cuts proposer failed/.test(l)))
  assert.match(prompts.tighten, /PROPOSED CUTS \(0, 0 words\)\n- none/)
  assert.deepEqual(result.tighten.proposed, 0)
})

test('the tighten stage runs once, on every path, after the writer and before the check, and the result carries its figures', async () => {
  for (const answers of [short, mid, long]) {
    const { result, labels } = await runWith(answers)
    assert.equal(labels.filter(l => l === 'tighten').length, 1)
    assert.ok(labels.indexOf('cuts') < labels.indexOf('tighten') && labels.indexOf('tighten') < labels.indexOf('check'))
    assert.ok(labels.indexOf('cuts') > Math.max(labels.indexOf('edit'), labels.indexOf('conduct')))
    assert.equal(result.tighten.taken, 1)
  }
  const { result } = await runWith(short)
  assert.deepEqual(result.tighten, { proposed: 1, proposedSaves: 40, taken: 1, declined: [], beyond: [], before: 1520, after: 1450 })
})

// ---------------------------------------------------------------- check and repair

test('the check reads original against edit, repairs what it finds, re-checks, and the result is clean when everything is accounted for', async () => {
  const { result, prompts, labels } = await runWith({ ...short, check: checked(1440, { verdict_before: 'NOT READY', findings: [finding(), finding({ ref: 'M1', rule: 'inventory I3', quote: 'only when offline' })],
    resolved: [{ ref: 'F1', passage: 'a solid cache' }, { ref: 'M1', passage: 'only when offline' }] }) })
  const p = prompts.check
  assert.match(p, /STAGE: check and repair\. You did not write this edit/)
  assert.match(p, /shasum -a 256 on the target\. If it is not ddd/)
  assert.match(p, /content-inventory\.py removed /)
  assert.match(p, /Account for every passage the removed list shows/)
  assert.match(p, /lives nowhere in the target is missing even when the inventory check passes/)
  assert.match(p, /every protected block shortened or turned into prose/)
  assert.match(p, /over 1530 words by wc -w \(the original's 1500 plus 2%\) is a length finding/)
  assert.match(p, /over 200 words is a length finding unless it is protected content/)
  assert.match(p, /5\. Fix every finding with exact-string edits in the target only/)
  assert.match(p, /6\. Run the inventory and quote checks again/)
  assert.ok(!labels.includes('repair') && !labels.includes('final'))
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(result.words.after, 1440)
  assert.deepEqual(result.restored, ['M1'])
})

test('a finding the check could not fix, or did not account for, keeps the run from being clean', async () => {
  const unresolved = await runWith({ ...short, check: checked(1450, { verdict_before: 'NOT READY', findings: [finding({ reraised: true })], unresolved: [{ ref: 'F1', reason: 'edit failed to apply', needs_author: false }] }) })
  assert.equal(unresolved.result.clean, false)
  assert.ok(unresolved.result.reasons.some(r => /1 unresolved/.test(r)))
  const ignored = await runWith({ ...short, check: checked(1450, { verdict_before: 'NOT READY', findings: [finding(), finding({ ref: 'Q1' })] }) })
  assert.equal(ignored.result.clean, false)
  assert.ok(ignored.result.reasons.some(r => /2 findings not accounted for \(F1, Q1\)/.test(r)))
})

test('an item only the author can settle goes to the author and leaves the run clean', async () => {
  const findings = [finding({ ref: 'F4', location: 'Objective 7', quote: 'every one of six', rule: 'guide 5: a figure the source contradicts', fix: 'five of them' }), finding({ ref: 'F5', location: 'Objective 9', quote: 'NDAP', rule: 'guide 2: acronym', fix: 'needs the expansion' }), finding()]
  const { result, logs } = await runWith({ ...short, check: checked(1450, { verdict_before: 'NOT READY', findings,
    resolved: [{ ref: 'F1', passage: 'a solid cache' }],
    unresolved: [{ ref: 'F4', reason: 'changes a figure', needs_author: true }, { ref: 'F5', reason: 'no source gives the expansion', needs_author: true }] }) })
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.deepEqual(result.forAuthor.map(f => [f.ref, f.location, f.fix, f.reason]), [['F4', 'Objective 7', 'five of them', 'changes a figure'], ['F5', 'Objective 9', 'needs the expansion', 'no source gives the expansion']])
  assert.deepEqual(result.check.unresolved, [])
  assert.ok(logs.some(l => /1 resolved, 2 for the author, 0 unresolved/.test(l)))
  const mixed = await runWith({ ...short, check: checked(1450, { verdict_before: 'NOT READY', findings, resolved: [{ ref: 'F1', passage: 'x' }],
    unresolved: [{ ref: 'F4', reason: 'changes a figure', needs_author: true }, { ref: 'F5', reason: 'could not place the edit', needs_author: false }] }) })
  assert.equal(mixed.result.clean, false)
  assert.ok(mixed.result.reasons.some(r => /1 unresolved/.test(r)))
  assert.equal(mixed.result.forAuthor.length, 1)
})

test('a failed inventory check, a missing quoted span or a lint that cannot run on the final text is not clean', async () => {
  const quoted = ['/blog/later.md:22 quotes "The chunks are guarded; the map is naked."']
  const cases = [
    [checked(1450, { inventory: { exit: 1, total: 40, missing: ['number: 0.76'] } }), /missing number: 0\.76/],
    [checked(1450, { inbound: { exit: 1, total: 3, missing: quoted } }), /another file quotes text the target no longer holds: .*the map is naked/],
    [checked(1450, { inbound: { exit: 2, total: 0, missing: [] } }), /quote check could not run/],
    [checked(1450, { lint: { ...okLint, exit: 2 } }), /lint could not run/],
  ]
  for (const [check, reason] of cases) {
    const { result } = await runWith({ ...short, check })
    assert.equal(result.clean, false)
    assert.ok(result.reasons.some(r => reason.test(r)), String(reason))
  }
  assert.deepEqual((await runWith(short)).result.finalInbound, okMech)
})

test('a run that ends more than 2% longer than it started is not clean', async () => {
  const grown = await runWith({ ...short, prepare: prep(1000), edit: edited({ words_after: 1040 }), tighten: tightened(1040, 1030), check: checked(1030) })
  assert.equal(grown.result.clean, false)
  assert.ok(grown.result.reasons.some(r => /grew by 30 words/.test(r)))
  const level = await runWith({ ...short, prepare: prep(1000), edit: edited({ words_after: 1040 }), tighten: tightened(1040, 1015), check: checked(1015) })
  assert.equal(level.result.clean, true, level.result.reasons.join('; '))
})

test('a fault the check finds in another file goes to the author as a flag', async () => {
  const { result } = await runWith({ ...short, check: checked(1450, { elsewhere: [{ file: 'ai-writing-gotchas.md', issue: 'now disagrees with the target' }] }) })
  assert.equal(result.clean, true)
  assert.ok(result.flags.some(f => f.location === 'ai-writing-gotchas.md'))
})

test('the restore loops are bounded in every stage that edits', async () => {
  const s = await runWith(short)
  const l = await runWith(long)
  for (const p of [s.prompts.edit, s.prompts.tighten, s.prompts.check, l.prompts.structure, l.prompts.conduct]) {
    assert.match(p, /at most three times/)
    assert.match(p, /Stop at once on exit 2/)
    assert.doesNotMatch(p, /until it exits 0/)
  }
})

test('no stage runs twice and nothing loops', async () => {
  for (const answers of [short, mid, long]) {
    const { labels } = await runWith(answers)
    assert.equal(new Set(labels).size, labels.length, labels.join(','))
  }
})

// The checklist every stage reads is derived from the guides. When a guide changes after the
// checklist was last regenerated, this fails until someone regenerates it and bumps its date.
test('the checklist is not older than any guide it condenses', () => {
  const home = process.env.HOME
  const updated = f => {
    const text = readFileSync(`${home}/.wiki/personal/writing/${f}.md`, 'utf8')
    const m = /^updated:\s*(\d{4}-\d{2}-\d{2})/m.exec(text) || /^date:\s*(\d{4}-\d{2}-\d{2})/m.exec(text)
    assert.ok(m, `${f}.md has no updated: or date: field`)
    return m[1]
  }
  const checklist = updated('edit-doc-checklist')
  for (const guide of ['plain-sentence-construction', 'ai-writing-gotchas', 'uk-tone-writing', 'accuracy-and-reproducibility', 'skim-layer', 'revision-passes']) {
    assert.ok(updated(guide) <= checklist, `${guide}.md was updated on ${updated(guide)}, after the checklist (${checklist}): regenerate the checklist and bump its updated: date`)
  }
})
