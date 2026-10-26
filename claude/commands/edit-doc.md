Edit a document in place against Warren's writing conventions, then report a structured change log so he can absorb the patterns.

If the user specifies a file, edit that one. Otherwise, prompt for the file. If the user says "as a learning post" or "--learning", run in learning-post mode (see Mode).

## How to run it

Run the edit-doc workflow on the file, every time, whatever its length: the Workflow tool with `scriptPath: ~/Developer/dotfiles/claude/workflows/edit-doc.js` and `args: {target, surface?, mode?, notes?, decisions?, sources?, related?}`. Pass `sources` whenever the document rests on evidence: its attachments, the drafts it came from, and the code at the commit it cites. Without them the claims are checked against the document alone, which is how a wrong ticket key or an untested case stated as fact gets through. Pass `related` (files or folders) when something outside the document's own folder may quote it; the run already searches that folder. Before launching, run `wc -w` on the file and say the path and the agent count in one line: under 2,500 words, the short path with five agents; from 2,500, the long path with seven, or up to ten from 5,000 words.

The standard every agent reads is `~/.wiki/personal/writing/edit-doc-checklist.md`: the six prose guides condensed one rule per line, with the rules below folded in. It is about 3,000 tokens against about 25,000 for the guides, which is what made a run cost 630,000 tokens and 15 minutes for a 2,000-word ticket. A Jira or email surface adds its surface guide, read in full. Only the per-remit reviewers on a document over 5,000 words read their remit's full guides.

**Short path (under 2,500 words).** Prepare (Sonnet) backs up the file to a fresh directory under `~/.claude/edit-doc/`, takes the content inventory, finds text other files quote, counts the words and edits nothing. Edit (Opus) runs every pass of the checklist in place and adds without cutting. Cuts (Sonnet, read-only) lists every cut the document can take with the words each saves. Tighten (Opus) rules on those, cuts beyond them with `/tighten`, and must reach the proposer's total or explain. Check (Sonnet) runs the mechanical checks, reads the original against the edit, lists everything lost, weakened or in breach, repairs it, and re-runs the checks. Five agents, one writer at a time, no stage twice.

**Long path (from 2,500 words).** Prepare, then Structure (Opus: authority and structure passes), then Review (one read-only reviewer for the whole document; from 5,000 words one per remit: words, argument, claims, and tests when the document carries any), then Conduct (Opus rules on every proposal and applies it), then the same Cuts, Tighten and Check (Opus here).

An item the check may not settle (a figure, a specific no source gives, a flag-only doubt) goes to Warren under `forAuthor` and leaves the run clean; only a fix the reader was allowed to make and could not complete fails it. Every stage checks the file's sha256 before editing and stops the run if something else wrote to it. A run that ends more than 2% longer than it started is not clean: additions such as a named source are paid for by cuts. The inventory script protects values that must survive byte for byte (numbers, code, links, footnotes, publishing fields); claims, qualifiers and reasons are the readers' job. `inbound-quotes.py` protects text other files quote from the document. A fault in another file goes to Warren as a flag; the run edits one file only.

When it returns, write the change log below from its result, in under 500 words. If `clean` is false, say why in one line and give the `original` path, which holds the backup. Flags and structure gaps go to Warren in the change log; nothing else is asked of him.

Several files: one run per file, one at a time. Run the passes inline only when the Workflow tool is unavailable: read the checklist and the surface guide, back up the file with the command in `/tighten`, take the inventory, run the passes in the checklist's order, then `/tighten`, then the three scripts in `~/Developer/dotfiles/claude/hooks/` (`writing-lint.py`, `content-inventory.py check`, `inbound-quotes.py check`).

## Mode

**Default mode: senior expertise.** Warren is a Principal Engineer with significant industry experience and a former Engineering Manager. The voice reads from that seat: observation, teaching, comparison, authority. He shares knowledge; he is not the cautionary tale.

**Learning-post mode (opt-in only)**: invoked when Warren explicitly says "as a learning post", "--learning", or "this is a learning piece". The journey from learning to applying is the explicit narrative; the RAG and wiki series is the canonical example. Even here the journey reads as deliberate exploration, not ignorance. Outside this mode, never write Warren learning a thing as an excuse to write about it.

When unclear, default to senior expertise.

## Rules

1. **Edit in place** for the qualitative passes (voice, structure, AI tells, UK tone, engagement, British English).
2. **Flag, do not fix, every number, identifier, version, path and statistic.** A fix needs a file the editor opened whose content unambiguously contradicts the text, a fix consistent with the document's own methodology, and a change-log entry citing the file and what it says. Earlier runs shipped silent "corrections" that renamed real identifiers and replaced correct counts, every one from a grep that was never read; a flagged claim is recoverable and a silently edited wrong one ships under Warren's name.
3. **Never fabricate to fix a problem.** No invented fact, source, example, dead end or experience. Flag the gap.
4. **Hands-off frontmatter:** `tags`, `publishDate`, `slug`, `campaign`, `series`, `heroImage`, `heroAlt`, `locale`, `draft`, `relatedPosts`. Title and description are in scope within the original character budget.
5. **Protected content** (code blocks, diagrams, charts, data tables, logs, console output, data excerpts, quoted records) may move with its section and is never shortened, cut, merged or turned into prose.
6. **The inventory decides every cut.** Don't ask Warren to approve one, and don't drop content to hit a length.
7. **Every change is a judgement in context,** never a mechanical find-and-replace. The lint prints pointers; the judgement clause keeps a listed word in its literal technical sense, and the change log says so.

## Output: structured change log

After the run, report under 500 words, specific enough for Warren to absorb the pattern and double-check the correctness work.

```
**Mode**: senior expertise | learning post
**Path**: short | long | long-split; agents: N
**Word count**: before → after (delta); tighten took N of N proposed cuts, M beyond them
**Clean**: yes | no (reason; original at <path>)
**For Warren**: each item the check left for you (a figure, an expansion no source gives, a flag): where, what it says now, what the check proposes, why it did not change it

**Authority calibration**: framings stripped (line → senior observation); claims cross-checked against workxp-en.json
**Structure**: what moved or went, and why; gaps flagged for Warren (missing dead end, outside cause, cost, open question, named specific)
**AI tells removed** (rough count by category): em-dashes converted · listed words and expressions · templated openers and closers · marketing compounds · decorative blockquotes folded · stylistic bolds stripped
**UK-tone fixes**: steelmans added, oppositional headers reframed, defensive openers dropped
**Correctness — fixed** (each entry: claim → new value; file read with lines; what it says; why the fix matches the document's methodology)
**Correctness — flagged, not fixed**: claim → what was measured under which method, what differed, what Warren should verify
**Engagement**: opening reshaped (was → now), subheadings sharpened, padding cut
**British English**: Americanisms fixed
**Check**: findings before repair, resolved, unresolved; inventory and quote checks; lint hits and em-dash density
**Banned-but-kept** (judgement clause): word, location, reason
**Out of scope / unverifiable**: external claims, performance claims needing instrumentation, infrastructure not in this repo
```

**The verification gate**: every entry under "Correctness — fixed" has its file and excerpt, or it moves to "flagged". A change log with fixed entries and no evidence is a failed run.

## What not to do

- Don't invent or speculate; flag. Dates, statistics, identifiers and personal facts above all.
- Don't add new sections or examples. Clean, calibrate, correct, tighten.
- Don't shorten code, charts or raw data; tightening is for prose.
- Don't make Warren the cautionary tale outside learning-post mode.
- Don't add AI, Claude or ChatGPT references in the body, except in posts about those tools.
- Don't downgrade the technical claim to make a sentence read more humble. The voice softens; the expertise doesn't.
- Don't summarise back what Warren said as if it were a finding. The change log is for what he can learn from.
