export const meta = {
  name: 'finish-doc',
  description: 'Finish one document: the critique workflow (readers object, a judge applies what the record answers), then the edit-doc workflow (the copy edit, tightened and checked), one report',
  whenToUse: 'A document that has to work on its reader and then read to the house standard, in one go: a ticket, a plan, a post, an email, a pull request description. args: the union of the critique and edit-doc args: {target, surface?, reader?, sources?, related?, repo?, decisions?, notes?, mode?, lenses?, models?: {critique?: {...}, editDoc?: {...}}, efforts?: {same}}. Runs critique first, because a developmental change makes a copy edit stale, and stops before edit-doc when the critique could not confirm its edits. Each workflow can also be run on its own: /critique and /edit-doc. Launch by scriptPath (~/Developer/dotfiles/claude/workflows/finish-doc.js).',
  phases: [
    { title: 'Critique', detail: 'the critique workflow: objections, judge, verifier' },
    { title: 'Edit', detail: 'the edit-doc workflow: every pass, tighten, check' },
  ],
}

if (!args || !args.target) throw new Error('args.target must name the one file to finish')
const SCRIPTS = '/Users/warrendeleon/Developer/dotfiles/claude/workflows'
const pick = (keys, extra) => Object.fromEntries(keys.filter(k => args[k] !== undefined).map(k => [k, args[k]]).concat(Object.entries(extra || {})))
const sub = (k, m) => (args[m] && args[m][k]) || undefined

phase('Critique')
const critique = await workflow({ scriptPath: `${SCRIPTS}/critique.js` },
  pick(['target', 'surface', 'reader', 'sources', 'related', 'repo', 'decisions', 'notes', 'lenses'], { models: sub('critique', 'models'), efforts: sub('critique', 'efforts') }))
if (!critique || critique.clean === undefined) return { target: args.target, clean: false, stage: 'critique', reason: 'the critique workflow returned nothing', critique }
log(`critique: ${critique.clean ? 'clean' : 'not clean: ' + (critique.reasons || [critique.reason]).join('; ')}; ${(critique.applied || []).length} edits stand, ${(critique.questions || []).length} questions`)
if (!critique.clean) return { target: args.target, clean: false, stage: 'critique', reason: `the critique is not clean, so the copy edit did not run: ${(critique.reasons || [critique.reason]).join('; ')}`, critique }

// The questions the judge left are for the author; the copy edit must not answer them.
const decisions = [...(args.decisions || []), ...(critique.questions || []).map(qn => `Open question for the author, leave the passage as it is: ${qn.location}: ${qn.question}`)]

phase('Edit')
const edit = await workflow({ scriptPath: `${SCRIPTS}/edit-doc.js` },
  pick(['target', 'surface', 'sources', 'related', 'notes', 'mode'], { decisions, models: sub('editDoc', 'models'), efforts: sub('editDoc', 'efforts') }))
if (!edit || edit.clean === undefined) return { target: args.target, clean: false, stage: 'edit-doc', reason: 'the edit-doc workflow returned nothing', critique, edit }
log(`edit-doc: ${edit.clean ? 'clean' : 'not clean: ' + (edit.reasons || [edit.reason]).join('; ')}; ${edit.words ? `${edit.words.before} to ${edit.words.after} words` : ''}`)

return {
  target: args.target,
  clean: critique.clean && edit.clean,
  reasons: [...(critique.reasons || []), ...(edit.reasons || [])],
  originals: { critique: critique.original, editDoc: edit.original },
  words: { before: critique.words && critique.words.before, afterCritique: critique.words && critique.words.after, after: edit.words && edit.words.after },
  critique: { objections: critique.objections, dropped: critique.dropped, applied: critique.applied, reverted: critique.reverted, questions: critique.questions },
  edit,
}
