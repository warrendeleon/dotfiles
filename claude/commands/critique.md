Developmental edit of one document: does it work on its reader? Readers object, a judge checks every objection against the record and applies what the record answers, a verifier opens every source. Nothing invented passes. Wording and house style are `/edit-doc`'s job; `/finish-doc` runs both.

If the user specifies a file, edit that one. Otherwise, prompt for the file.

## How to run it

Run the critique workflow on the file: the Workflow tool with `scriptPath: ~/Developer/dotfiles/claude/workflows/critique.js` and `args: {target, surface?, reader?, sources?, related?, repo?, decisions?, notes?, lenses?}`.

- `reader`: who reads it and what they do with it, in a sentence. Derived from `surface` when absent (a Jira ticket's developer, tester and business analyst; a post's senior engineer deciding whether to adopt; an email's recipient).
- `sources`: the evidence behind the document (attachments, drafts, the archive it was built from, code at a commit). The judge checks objections against these first.
- `related`: the record the document came from (a drafts folder, an archive, a database), searched after the sources and the RAG index.
- `repo`: the repository the document is about, searched last.
- `decisions`: author framings the critics never object to and the judge never changes.
- `lenses`: 2 by default (the intended reader and a hostile reviewer); 1 for a short text.

Before launching, say the reader seat and the agent count in one line: three agents, four when the judge applies anything.

**What happens.** Two read-only critics (Sonnet) read the document in their seat and raise substance only: a claim the reader would dispute, evidence missing, something the reader needs and does not get, a cause asserted where only an observation is shown, a conclusion the evidence does not reach, an order that hides the point, a contradiction. The judge (Opus) backs the file up to a fresh directory under `~/.claude/critique/`, then rules on each objection: one the document or its sources refute is dropped with the reason; one the record answers is applied, with the source on the edit (`path:line`, a RAG chunk, or a passage of the document) and the source's own words; one no source answers, or that the record shows you have left open, becomes a question with every place searched. The search order is the document, the sources, RAG, the wiki, the related paths, the repository. The judge never removes content and never writes a value a source does not hold byte for byte. A verifier (Sonnet) opens every cited source, diffs the protected values against the original, and puts back the exact before text of any edit it cannot confirm.

Clean means: both critics ran, every objection was ruled on, every applied edit was confirmed or reverted, every new value has a source, and the inventory check exits 0. Questions do not make a run unclean; they are the residue the record could not answer.

## Output

Report under 400 words from the result:

```
**Reader**: the seat the critics sat in
**Objections**: N (M block, K weaken, J minor), from the reader and the hostile lens
**Clean**: yes | no (reason; original at <path>)

**Applied** (each: where; what it now says; the source and its words)
**Dropped** (each: the objection; what refutes it)
**Reverted by the verifier** (each: the edit; why the source did not hold it)
**Questions for Warren** (each: where; the question; what was searched and what it returned)
```

Every applied entry names its source. An entry without one is a failed run, not a change log.

## What not to do

- Don't raise or apply wording, tone, spelling or house-style points; that is `/edit-doc`.
- Don't answer a question the record could not: a plausible figure, reason or name is invention.
- Don't cut, shorten or merge content; an objection that the reader does not need a passage goes to Warren.
- Don't touch an author decision.
- Don't post, send or publish the result; that stays the author's call.
