Finish one document in one go: `/critique` (does it work on its reader?) and then `/edit-doc` (does it read to the house standard?), one report at the end. Each can still be run on its own.

If the user specifies a file, finish that one. Otherwise, prompt for the file.

## How to run it

Run the finish-doc workflow on the file: the Workflow tool with `scriptPath: ~/Developer/dotfiles/claude/workflows/finish-doc.js` and the union of the two workflows' args: `{target, surface?, reader?, sources?, related?, repo?, decisions?, notes?, mode?, lenses?}`. Pass `sources` and `related` whenever the document rests on evidence; both workflows check against them. Before launching, say the reader seat and the agent count in one line: three or four for the critique, then five under 2,500 words or seven to ten above.

The critique runs first, because a developmental change makes a copy edit stale. The questions the judge leaves for Warren are passed to edit-doc as author decisions, so the copy edit leaves those passages alone. If the critique is not clean (an edit the verifier could not confirm, an objection not ruled on, a lost critic), the copy edit does not run and the report says why; the critique's original is under `~/.claude/critique/`, edit-doc's under `~/.claude/edit-doc/`.

## Output

The `/critique` report, then the `/edit-doc` change log, under 800 words together. The questions for Warren appear once, in the critique section. If either is not clean, say why in one line at the top with the original paths.
