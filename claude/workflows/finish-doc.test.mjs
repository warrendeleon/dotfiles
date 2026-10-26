// Runs finish-doc.js with the two child workflows stubbed.
//
//   node --test claude/workflows/finish-doc.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('./finish-doc.js', import.meta.url), 'utf8').replace('export const meta =', 'const meta =')
const run = new Function('agent', 'parallel', 'pipeline', 'log', 'phase', 'args', 'budget', 'workflow', `return (async () => {\n${source}\n})()`)

const critiqueOk = { clean: true, reasons: [], original: '/h/.claude/critique/plan.md.A/original.md', words: { before: 2045, after: 2050 }, objections: 4, dropped: [], applied: [{ ref: 'O1' }], reverted: [], questions: [{ ref: 'O3', location: 'Objective 9', question: 'What does NDAP stand for?', searched: ['rag: nothing'] }] }
const editOk = { clean: true, reasons: [], original: '/h/.claude/edit-doc/plan.md.B/original.md', words: { before: 2050, after: 2001 } }

async function runWith(answers, args = { target: '/tmp/plan.md' }) {
  const calls = [], logs = []
  const workflow = async (ref, a) => {
    const name = ref.scriptPath.split('/').pop().replace('.js', '')
    calls.push({ name, args: a })
    const r = answers[name]
    return typeof r === 'function' ? r(a) : r
  }
  const result = await run(() => { throw new Error('no agents here') }, null, null, m => logs.push(m), () => {}, args, null, workflow)
  return { result, calls, logs }
}

test('critique runs first, then edit-doc, and the report carries both', async () => {
  const { result, calls } = await runWith({ critique: critiqueOk, 'edit-doc': editOk })
  assert.deepEqual(calls.map(c => c.name), ['critique', 'edit-doc'])
  assert.equal(result.clean, true)
  assert.deepEqual(result.words, { before: 2045, afterCritique: 2050, after: 2001 })
  assert.deepEqual(result.originals, { critique: critiqueOk.original, editDoc: editOk.original })
  assert.equal(result.critique.questions.length, 1)
})

test('each child gets its own args and model overrides, and the judge\'s questions reach edit-doc as decisions', async () => {
  const { calls } = await runWith({ critique: critiqueOk, 'edit-doc': editOk },
    { target: '/tmp/plan.md', surface: 'other', reader: 'HR', sources: ['/s'], related: ['/r'], repo: '/repo', decisions: ['Objective 9 stays.'], notes: 'n', mode: 'senior', lenses: 1, models: { critique: { judge: 'sonnet' }, editDoc: { edit: 'sonnet' } } })
  const [c, e] = calls
  assert.deepEqual(c.args, { target: '/tmp/plan.md', surface: 'other', reader: 'HR', sources: ['/s'], related: ['/r'], repo: '/repo', decisions: ['Objective 9 stays.'], notes: 'n', lenses: 1, models: { judge: 'sonnet' }, efforts: undefined })
  assert.equal(e.args.target, '/tmp/plan.md')
  assert.equal(e.args.mode, 'senior')
  assert.equal(e.args.reader, undefined)
  assert.deepEqual(e.args.models, { edit: 'sonnet' })
  assert.deepEqual(e.args.decisions, ['Objective 9 stays.', 'Open question for the author, leave the passage as it is: Objective 9: What does NDAP stand for?'])
})

test('a critique that is not clean stops the run before edit-doc', async () => {
  const { result, calls } = await runWith({ critique: { ...critiqueOk, clean: false, reasons: ['1 edits neither confirmed nor reverted (O1)'] }, 'edit-doc': editOk })
  assert.deepEqual(calls.map(c => c.name), ['critique'])
  assert.equal(result.clean, false)
  assert.equal(result.stage, 'critique')
  assert.match(result.reason, /copy edit did not run: 1 edits neither confirmed/)
})

test('an edit-doc that is not clean makes the whole run not clean, with its reasons', async () => {
  const { result } = await runWith({ critique: critiqueOk, 'edit-doc': { ...editOk, clean: false, reasons: ['2 unresolved'] } })
  assert.equal(result.clean, false)
  assert.deepEqual(result.reasons, ['2 unresolved'])
})

test('a child that returns nothing is reported, not thrown', async () => {
  const { result } = await runWith({ critique: null, 'edit-doc': editOk })
  assert.equal(result.clean, false)
  assert.match(result.reason, /critique workflow returned nothing/)
})

test('a missing target is refused', async () => {
  await assert.rejects(runWith({ critique: critiqueOk, 'edit-doc': editOk }, {}), /args\.target/)
})
