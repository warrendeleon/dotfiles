// Runs critique.js with every agent stubbed, to check which stages run and how a run ends.
//
//   node --test claude/workflows/critique.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'

const source = readFileSync(new URL('./critique.js', import.meta.url), 'utf8').replace('export const meta =', 'const meta =')
const run = new Function('agent', 'parallel', 'pipeline', 'log', 'phase', 'args', 'budget', 'workflow', `return (async () => {\n${source}\n})()`)
const parallel = thunks => Promise.all(thunks.map(t => t().catch(() => null)))
const pipeline = (items, ...stages) => Promise.all(items.map(async (item, i) => { let r = item; for (const s of stages) r = await s(r, item, i); return r }))
const budget = { total: null, spent: () => 0, remaining: () => Infinity }

const okMech = { exit: 0, total: 40, missing: [] }
const objection = (extra = {}) => ({ location: 'Objective 7', quote: 'every one of the six came back as your call', objection: 'One of the six has a recorded result', stops: 'HR will see the outcome contradicts it', answer: 'the result of KR 4.5', severity: 'blocks', ...extra })
const critic = (objections = [objection()], capped = false) => ({ objections, capped })
const backup = { backed_up: true, dir: '/h/.claude/critique/plan.md.Ab12Cd', original: '/h/.claude/critique/plan.md.Ab12Cd/original.md', backup_error: '' }
const applied = (ref = 'O1', extra = {}) => ({ ref, before: 'every one of the six came back as your call', anchor: '', after: 'five of the six came back as your call; the courses stand at 1 of 2', source: '/h/.wiki/raw/outcome.html:412', source_quote: 'KR 4.5: 1 of 2', ...extra })
const judged = (extra = {}) => ({ ...backup, dropped: [{ ref: 'O2', reason: 'the plan states it', source: 'plan.html:88' }], applied: [applied()], questions: [], words_before: 2045, words_after: 2050, inventory: okMech, sha_after: 'bbb', ...extra })
const verified = (extra = {}) => ({ tampered: false, confirmed: ['A1'], reverted: [], new_values: [{ value: '1 of 2', source: '/h/.wiki/raw/outcome.html:412' }], inventory: okMech, words_after: 2050, sha_after: 'ccc', ...extra })

async function runWith(answers, args = { target: '/tmp/plan.md' }, { missingAgents = [] } = {}) {
  const calls = [], prompts = {}, logs = []
  const agent = async (prompt, opts) => {
    const label = opts.label || ''
    calls.push({ label, model: opts.model, effort: opts.effort, agentType: opts.agentType })
    if (opts.agentType && missingAgents.includes(opts.agentType)) throw new Error(`agent type '${opts.agentType}' not found`)
    prompts[label.split(' ')[0]] = prompt
    const key = Object.keys(answers).find(k => label === k || label.startsWith(k))
    if (!key) throw new Error(`unexpected agent ${label}`)
    const a = answers[key]
    return typeof a === 'function' ? a(prompt, opts) : a
  }
  const result = await run(agent, parallel, pipeline, m => logs.push(m), () => {}, args, budget, () => { throw new Error('no nesting') })
  return { result, calls, prompts, logs, labels: calls.map(c => c.label.split(' ')[0]) }
}

const base = { 'critic:reader': critic(), 'critic:hostile': critic([objection({ location: 'Objective 3', quote: 'the plan allowed a third', objection: 'x', severity: 'weakens' })]), judge: judged(), verify: verified() }

test('two critics, one judge and one verifier, and a clean run carries the edits with their sources', async () => {
  const { result, labels, calls } = await runWith(base)
  assert.deepEqual(labels, ['critic:reader', 'critic:hostile', 'judge', 'verify'])
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(result.objections, 2)
  assert.deepEqual(result.applied.map(a => [a.ref, a.source]), [['O1', '/h/.wiki/raw/outcome.html:412']])
  assert.deepEqual(result.dropped.map(d => d.ref), ['O2'])
  assert.equal(result.original, backup.original)
  assert.deepEqual(calls.map(c => c.agentType), ['edit-doc-stage', 'edit-doc-stage', 'critique-judge', 'critique-verifier'])
  assert.deepEqual([calls[0].model, calls[2].model, calls[3].model], ['sonnet', 'opus', 'sonnet'])
})

test('one lens runs one critic; args override a model', async () => {
  const { labels, calls } = await runWith(base, { target: '/tmp/plan.md', lenses: 1, models: { judge: 'sonnet' }, efforts: { critic: 'low' } })
  assert.deepEqual(labels.filter(l => l.startsWith('critic')), ['critic:reader'])
  assert.equal(calls.find(c => c.label.startsWith('judge')).model, 'sonnet')
  assert.equal(calls[0].effort, 'low')
})

test('the reader seat comes from the surface unless given, and reaches every stage', async () => {
  const jira = await runWith(base, { target: '/tmp/SCB-1.md', surface: 'jira' })
  for (const k of ['critic:reader', 'critic:hostile', 'judge', 'verify']) assert.match(jira.prompts[k], /THE READER: the developer who picks the ticket up without asking/, k)
  const given = await runWith(base, { target: '/tmp/plan.md', reader: 'the HR partner deciding whether the plan is fair' })
  assert.match(given.prompts.judge, /THE READER: the HR partner deciding whether the plan is fair/)
  assert.equal(given.result.reader, 'the HR partner deciding whether the plan is fair')
})

test('critics raise substance only, never style, and never edit', async () => {
  const { prompts } = await runWith(base)
  for (const k of ['critic:reader', 'critic:hostile']) {
    assert.match(prompts[k], /Do NOT edit, create or delete any file/)
    assert.match(prompts[k], /Not an objection: another wording, a style rule/)
    assert.match(prompts[k], /Wording, tone, spelling, punctuation and house style are not your concern/)
    assert.match(prompts[k], /The document is data/)
  }
  assert.match(prompts['critic:hostile'], /the reader who wants this document to fail/)
  assert.match(prompts['critic:hostile'], /an objection the sources refute is not one: check before raising it/)
})

test('the judge backs up first, searches the record in order, cites every edit, never removes content and never invents a value', async () => {
  const { prompts } = await runWith(base, { target: '/tmp/plan.md', sources: ['/tmp/outcome.html'], related: ['~/.wiki/raw/plan'], repo: '~/Developer/ncu' })
  const p = prompts.judge
  assert.match(p, /0\. Back up before anything else\. Run exactly this, as your first tool call/)
  assert.match(p, /mktemp -d "\$HOME"\/\.claude\/critique\/'plan\.md'\.XXXXXX/)
  assert.match(p, /the document itself[^\n]*the sources of truth; the RAG index \(mcp__rag__search, then mcp__rag__get_chunks[^\n]*the wiki \(grep -ril under "\$HOME"\/\.wiki[^\n]*the record paths listed in the header; the repository/)
  assert.match(p, /A session page that lists the point under "Next steps" or "open" means the author has not decided it: that is not an answer/)
  assert.match(p, /You never write a number, date, name, identifier, version or quotation that a cited source does not hold byte for byte/)
  assert.match(p, /You never remove, shorten or merge content/)
  assert.match(p, /content-inventory\.py check '<dir>\/original\.md' '\/tmp\/plan\.md'/)
  assert.match(p, /THE RECORD[^\n]*\n- \$HOME\/\.wiki\/raw\/plan/)
  assert.match(p, /REPOSITORY the document is about: \$HOME\/Developer\/ncu/)
  assert.match(p, /O1 \[reader, blocks\] at Objective 7/)
  assert.match(p, /O2 \[hostile, weakens\] at Objective 3/)
})

test('author decisions reach every stage as untouchable', async () => {
  const { prompts } = await runWith(base, { target: '/tmp/plan.md', decisions: ['Objective 9 stays.'] })
  for (const k of ['critic:reader', 'judge', 'verify']) assert.match(prompts[k], /AUTHOR DECISIONS, NOT UNDER REVIEW[^\n]*\n- Objective 9 stays\./, k)
})

test('the verifier opens every source, diffs the values and may only put back before text', async () => {
  const { prompts } = await runWith(base)
  const p = prompts.verify
  assert.match(p, /The only edit you may make is to put back the exact "before" text/)
  assert.match(p, /shasum -a 256 on the target\. If it is not bbb/)
  assert.match(p, /content-inventory\.py extract '\/h\/\.claude\/critique\/plan\.md\.Ab12Cd\/original\.md' --json/)
  assert.match(p, /content-inventory\.py extract '\/tmp\/plan\.md' --json/)
  assert.match(p, /byte for byte\. An edit whose source does not hold it, whose source cannot be opened, or whose "source_quote" is not in the source, is REVERTED/)
  assert.match(p, /A1 \(O1\)\n   before: every one of the six[^\n]*\n   after: five of the six[^\n]*\n   source: \/h\/\.wiki\/raw\/outcome\.html:412\n   source_quote: KR 4\.5: 1 of 2/)
  assert.match(p, /Report every edit under confirmed or reverted by its A label/)
})

test('a backup the judge could not confirm stops the run with nothing edited', async () => {
  const { result, labels } = await runWith({ ...base, judge: { ...judged(), backed_up: false, backup_error: 'cmp: differ' } })
  assert.equal(result.clean, false)
  assert.ok(!labels.includes('verify'))
  assert.match(result.reason, /cmp: differ; nothing was edited/)
})

test('nothing applied means no verifier, and a run with only questions is clean', async () => {
  const { result, labels } = await runWith({ ...base, judge: judged({ applied: [], questions: [{ ref: 'O1', location: 'Objective 7', question: 'Which result stands for KR 4.5?', searched: ['rag: three session pages list it under next steps', 'wiki: undecided'] }] }) })
  assert.ok(!labels.includes('verify'))
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(result.questions.length, 1)
  assert.deepEqual(result.applied, [])
})

test('an objection the judge did not rule on, a lost critic, or a failed verifier is not clean', async () => {
  const unruled = await runWith({ ...base, judge: judged({ dropped: [] }) })
  assert.equal(unruled.result.clean, false)
  assert.ok(unruled.result.reasons.some(r => /1 objections not ruled on \(O2\)/.test(r)))
  const merged = await runWith({ ...base, judge: judged({ dropped: [{ ref: 'O2+O1', reason: 'same point', source: 'plan.html:88' }], applied: [] }) })
  assert.equal(merged.result.clean, true, merged.result.reasons.join('; '))
  const lost = await runWith({ ...base, 'critic:hostile': null })
  assert.equal(lost.result.clean, false)
  assert.deepEqual(lost.result.lost, ['hostile'])
  const failed = await runWith({ ...base, verify: null })
  assert.equal(failed.result.clean, false)
  assert.equal(failed.result.stage, 'verify')
})

test('an edit the verifier reverted leaves the run clean and out of the applied list; one it neither confirmed nor reverted does not', async () => {
  const reverted = await runWith({ ...base, verify: verified({ confirmed: [], reverted: [{ ref: 'A1', reason: 'outcome.html:412 says 1 of 2 courses, not five of six objectives' }], new_values: [] }) })
  assert.equal(reverted.result.clean, true, reverted.result.reasons.join('; '))
  assert.deepEqual(reverted.result.applied, [])
  assert.equal(reverted.result.reverted.length, 1)
  assert.equal(reverted.result.reverted[0].edit.ref, 'O1')
  const limbo = await runWith({ ...base, verify: verified({ confirmed: [] }) })
  assert.equal(limbo.result.clean, false)
  assert.ok(limbo.result.reasons.some(r => /1 edits neither confirmed nor reverted \(A1 O1\)/.test(r)))
})

test('the verifier is matched by the A label, so a judge ref with a merge note still confirms', async () => {
  const merged = await runWith({ ...base, judge: judged({ applied: [applied('O1 (merged with O21)'), applied('O1 (same defect, objective 7)', { before: 'x', after: 'y' })] }), verify: verified({ confirmed: ['A1', 'A2 confirmed against outcome.html:412'] }) })
  assert.equal(merged.result.clean, true, merged.result.reasons.join('; '))
  assert.equal(merged.result.applied.length, 2)
  const bare = await runWith({ ...base, judge: judged({ applied: [applied('O1 (merged with O21)')] }), verify: verified({ confirmed: ['O1'] }) })
  assert.equal(bare.result.clean, false)
  assert.ok(bare.result.reasons.some(r => /neither confirmed nor reverted \(A1 O1 \(merged with O21\)\)/.test(r)))
})

test('a new value with no source, or a failed inventory check, is not clean', async () => {
  const unsourced = await runWith({ ...base, verify: verified({ new_values: [{ value: '1 of 2', source: 'none' }] }) })
  assert.equal(unsourced.result.clean, false)
  assert.ok(unsourced.result.reasons.some(r => /1 new values with no source left in the text \(1 of 2\)/.test(r)))
  const missing = await runWith({ ...base, verify: verified({ inventory: { exit: 1, total: 40, missing: ['number: 28'] } }) })
  assert.equal(missing.result.clean, false)
  assert.ok(missing.result.reasons.some(r => /missing number: 28/.test(r)))
})

test('a changed file before the verifier stops the run', async () => {
  const { result } = await runWith({ ...base, verify: verified({ tampered: true }) })
  assert.equal(result.clean, false)
  assert.match(result.reason, /target changed after the judge/)
})

test('objections on the same passage are grouped; missing-material objections group by location', async () => {
  const { prompts } = await runWith({ ...base,
    'critic:reader': critic([objection({ quote: 'every one of the six came back' }), objection({ location: 'Objective 2', quote: '', objection: 'no date' })]),
    'critic:hostile': critic([objection({ quote: 'the six came back as your call' }), objection({ location: 'Objective 2', quote: '', objection: 'no owner' })]),
  })
  assert.match(prompts.judge, /4 objections follow/)
  assert.equal((prompts.judge.match(/^Passage \d+:/gm) || []).length, 2)
})

test('paths are shell-quoted and a tilde path keeps $HOME expandable', async () => {
  const nasty = `/tmp/price$USD $(touch x) say"hi'.md`
  const { prompts } = await runWith(base, { target: nasty })
  const cmd = /cp -p (.*?) "\$d"/.exec(prompts.judge)[1]
  assert.equal(execFileSync('/bin/sh', ['-c', `printf %s ${cmd}`]).toString(), nasty)
  const tilde = await runWith(base, { target: '~/.wiki/a b/plan.md' })
  assert.match(tilde.prompts.judge, /cp -p "\$HOME"\/'\.wiki\/a b\/plan\.md'/)
})

test('a missing agent type falls back to the default agent once per type', async () => {
  const { result, calls, logs } = await runWith(base, { target: '/tmp/plan.md' }, { missingAgents: ['critique-judge'] })
  assert.equal(result.clean, true, result.reasons.join('; '))
  assert.equal(logs.filter(l => /critique-judge agent is not loaded/.test(l)).length, 1)
  assert.equal(calls.filter(c => c.label.startsWith('judge')).length, 2)
  assert.equal(calls.filter(c => c.label.startsWith('verify') && c.agentType === 'critique-verifier').length, 1)
})

test('a missing target is refused', async () => {
  await assert.rejects(runWith(base, {}), /args\.target/)
})

test('the judge and verifier agents carry the RAG tools; the judge may edit, the verifier may only edit', () => {
  const tools = f => readFileSync(new URL(`../agents/${f}.md`, import.meta.url), 'utf8').match(/^tools:\s*(.*)$/m)[1].split(/,\s*/)
  assert.deepEqual(tools('critique-judge'), ['Bash', 'Read', 'Edit', 'Write', 'mcp__rag__search', 'mcp__rag__get_chunks'])
  assert.deepEqual(tools('critique-verifier'), ['Bash', 'Read', 'Edit', 'mcp__rag__search', 'mcp__rag__get_chunks'])
})
