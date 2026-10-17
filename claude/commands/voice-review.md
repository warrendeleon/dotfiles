Edit a document in place against Warren's writing conventions, then report a structured change log so he can absorb the patterns.

If the user specifies a file, voice-review that. Otherwise, prompt for the file. If the user says "as a learning post" or "--learning", run in learning-post mode (see Mode section).

## How to run it

Run the voice-review workflow on the file, every time, whatever its length: the Workflow tool with `scriptPath: ~/Developer/dotfiles/claude/workflows/voice-review.js` and `args: {target, surface?, mode?, notes?, decisions?}`. Before launching, say the model plan and the expected agent count in one line (4 to 6 agents under 600 words, 7 to 9 above).

The workflow is how a document is held to the guides. The conductor's first act is a backup to a fresh directory under `~/.claude/voice-review/`, so a rerun never overwrites an earlier original; if the backup fails it edits nothing. The conductor is the only writer and edits only the target: it takes the content inventory and does Passes 1 and 2. Read-only reviewers, one remit each, propose edits for Passes 3 to 8, and duplicate proposals are merged. The conductor rules on every proposal, applies them, tightens, and checks the inventory. A fresh reader then checks the result against the guides and the inventory, alongside `writing-lint.py` and `content-inventory.py`. The inventory script protects values that must survive byte for byte (numbers, code, links, footnotes, publishing fields); claims, qualifiers and reasons are the readers' job. At most one repair follows, and one final agent confirms exactly what it touched, so the run never loops. A run that ends more than 2% longer than it started is not clean: additions such as a named source are paid for by cuts in the same passage. A fault the reader finds in another file goes to Warren as a flag; the run edits one file only.

When it returns, write the change log below from its result, in under 500 words. If `clean` is false, say why in one line and give the `original` path, which holds the backup. Flags and structure gaps go to Warren in the change log; nothing else is asked of him.

Several files: one run per file, one at a time. Run the passes below inline only when the Workflow tool is unavailable. Every agent in the workflow also reads the sections below as its standard.

## This is AI judgement, not a substitution script

The wiki gotchas page contains a table of banned-term → replacement entries. **Do not treat this table as a sed script.** Each occurrence of a flagged term must be read in its sentence context and assessed before any change is made:

- Is the word being used in its **literal technical sense** (the judgement clause applies, keep the word, note in "Banned-but-kept")?
- Is it **filler / marketing colour** (replace, but pick the replacement that fits the sentence's rhythm and register — not always the first column of the table)?
- Does the **sentence as a whole** need rewriting because the banned term is load-bearing? Then rewrite the sentence rather than swap the word.

The table is reference material. The work happens between your eye reading the sentence and your hand making the edit. If the change-log's "Banned-but-kept" section is empty across a long document, that's a red flag: you weren't reading carefully enough. Real prose has technical uses of banned words; the skill should catch and preserve them.

Same principle applies to every other pass — authority calibration, UK-tone, correctness, engagement. Every change is a judgement made in context, never a mechanical find-and-replace.

## Required reading (load before touching the document)

This list is for an inline run and for the conductor. In the workflow, every other agent reads only what its stage names, within the reading profile the conductor resolved.

- `~/.wiki/personal/writing/writing-guides.md` — the router: its "Draft or edit English prose" profile sets the guides below, and its "Reading as written by a person" section sets the aim
- `~/.wiki/personal/writing/plain-sentence-construction.md` — guide 1: sentence and paragraph construction, stock constructions, meaning spelled out
- `~/.wiki/personal/writing/ai-writing-gotchas.md` — guide 2: banned words, expressions, stock phrases, constructions, em-dashes, judgement clause
- `~/.wiki/personal/writing/uk-tone-writing.md` — guide 3: steelman framework, hedge non-absolutes, no defensive openers, argument shape
- `~/.wiki/personal/writing/accuracy-and-reproducibility.md` — guide 5: evidence for every claim, including significance, attribution and named specifics
- `~/.wiki/personal/writing/skim-layer.md` — guide 6: bold anchors, template structure
- `~/.wiki/personal/writing/revision-passes.md` — guide 7: the whole read, the leftovers search, the structural pass and the tightening pass
- `~/Developer/warrendeleon/warrendeleon.com/src/data/workxp-en.json` — Warren's actual work-experience data (use this to verify any authority claims; never embed a specific year if it can be checked here)
- The target document, in full, before editing

If any required file is missing, flag it and proceed with the others. Don't fabricate authority claims from gaps.

## Mode

**Default mode: senior expertise.** Warren is a Senior Software Engineer with significant industry experience and an Engineering Manager. The voice reads from that seat: observation, teaching, comparison, authority. He shares knowledge; he is not the cautionary tale.

**Learning-post mode (opt-in only)**: invoked when Warren explicitly says "as a learning post", "--learning", or "this is a learning piece". In learning-post mode, the journey from learning to applying is the explicit narrative. The RAG / wiki series is the canonical example: that journey is the subject. Outside this mode, never write Warren learning a thing as an excuse to write about it.

When unclear, default to senior expertise.

## Rules

1. **Edit the document in place** for qualitative passes (voice, AI tells, UK tone, engagement, British English). These are the passes where the model performs well.
2. **DEFAULT TO FLAGGING, not fixing, for Pass 5 (correctness)**. Numeric claims, identifier names, version numbers, statistics. **Do not auto-correct these.** Open the relevant file, read it, write your finding in the Pass 5 Evidence section of the change log, and let Warren decide whether to apply the change. The skill has historically been 70% wrong on numeric "corrections" — silent edits to numbers and identifiers are how that hallucination ships under Warren's name. Flag-not-fix is the default.
3. **Take the content inventory, then run all eight passes in order.** Each pass has a clear remit; don't skip.
4. **Never fabricate to fix a problem.** If you'd have to invent a fact, flag it instead.
5. **Don't make Warren the cautionary tale** outside learning-post mode. He has been criticised for being too direct or dismissive; the steelman framework is how that gets calibrated, not by inserting self-deprecation.
6. **Tags, publishDate, slug, campaign, series, heroImage, heroAlt, locale, draft, relatedPosts** in frontmatter are hands-off. Title and description are in scope; stay within the original character budget for description.
7. **Em-dashes near zero in prose**, judged sentence by sentence by density and function as guide 2 sets out; `term — definition` rows stay. Same judgement in every language; don't strip by count.
8. **Every correctness-pass entry in the change log MUST cite the file path you read and an excerpt or paraphrase of what you saw.** If you cannot cite a specific file you opened, the claim is unverified and must be flagged, not fixed. Hand-waving "verified against codebase" is not acceptable. This is the verification gate.

## Passes (run in order, edit in place)

### Before Pass 1 — Content inventory

Before any edit, list every item the original carries, as guide 7's "Tighten without losing content" sets out: each claim, number, name, identifier, date, link, example, step, caveat, qualifier, condition, reason and decision. Context is content: the reason a step exists and the condition a claim holds under are items. Keep the list in working notes. Every later pass is checked against it, the structure pass included, because that pass cuts too.

### Pass 1 — Authority calibration

The first and most important pass. Strip framings that undermine Warren's seniority:

- "I made the mistake of..."
- "I tried obvious things and they were all wrong"
- "It cost me a job / a client / every interview"
- "I didn't know X and had to figure it out"
- "I just learned this"
- "I bombed", "I failed", "I didn't pass" italicised confession lines
- Any "I was the candidate who didn't know X" framing for industry-standard libraries or patterns

Replace with senior-practitioner framings:

- **Observation**: "Most React Native apps do X. It works until..."
- **Teaching**: "Your token expires. The app makes a call." (No "Here's".)
- **Comparison**: "The SDK does this in three lines. The custom version takes 600."
- **Authority**: "I've used this pattern across several projects. The reason it works is..."

Exceptions:

- **Management content**: light "I'm still calibrating the manager side" framing is honest (Warren has been EM since 2024). Don't overdo it.
- **Learning-post mode**: keep the journey framing. Even here, calibrate so the journey reads as deliberate exploration, not as ignorance.

Cross-check authority claims against `workxp-en.json` if specific years or roles are mentioned. Never embed a hard-coded date for "EM since X" — read it. If a piece of authority is asserted but the CV doesn't back it, flag it.

**Hard rule**: industry-standard tools (TanStack Query, Zustand, RTK Query, Redux Toolkit, MSW, Detox, Cucumber, Zod, Axios, etc.) are NOT framed as things Warren just learned. Even if a particular post emerged from a learning moment, the framing is senior comparison, not novice discovery. Strip any line that reads "I didn't know X exists" for any tool that's industry-standard.

### Pass 2 — Structure

Run this before any word-level pass: rewriting a section removes many flagged words anyway, and a word pass never changes the structure. Read the outline first (headings and the first sentence of each section), then apply the structural pass in guide 7, argument shape and register in guide 3, the eighth habit in guide 1 and template structure in guide 6.

- **Order.** Does the piece open where the reader's problem is, and is its outline the one this material needs rather than the default context, problem, solution, lesson? Reorder sections when it is not. Tutorial steps keep their execution order.
- **Endings.** Cut a stated lesson at the end of a section and any epilogue. The piece ends on its last substantive point.
- **Real shape.** The dead end that changed the decision, a cause that came from outside, the cost of the choice and a question still open. Restore one the draft tidied away when the document or its sources contain it. When they do not, flag the gap for Warren; never write one.
- **Named specifics.** Where the draft alludes ("a popular library", "some teams"), name the thing if a source you opened gives it; otherwise flag.
- **Register.** The piece sounds like its surface: a blog post, an email, a Slack reply, an ADR or a deck.
- **Template structure.** Bold-label bullets in an argument, template headings, small tables of prose facts that should be sentences (never a table of raw data), a closing challenges section.
- **Protected content.** A code block, diagram, chart, data table, log, console output, data excerpt (JSON, CSV, YAML) or quoted record may move with its section. No structural change removes, shortens or summarises one.

A structural change rewrites whole sections. Record each one in the change log: what moved or went, and why.

### Pass 3 — AI tells

Scan the document against guide 2 (`ai-writing-gotchas.md`) and the sentence habits in guide 1. Guide 2's tables are the canonical list, including the stock phrases, the model-era vocabulary and the change-summary rules; the bullets below are reminders, not the list.

Start by running `python3 ~/Developer/dotfiles/claude/hooks/writing-lint.py <file>`. It prints every place a guide 2 term or a leftovers-search pattern appears, plus the em-dash density. Each hit is a pointer: read it in its sentence and apply the judgement clause before changing anything. If it exits 2, a guide is missing or no longer parses; say so in the change log and scan by hand. Then strip:

- **Em-dashes, near zero in prose.** Judge each one by density and by function: where a colon, semicolon, parentheses, comma or full stop serves as well, use it, and keep the punctuation varied rather than falling back on commas and full stops alone. Keep `term — definition` rows. Never strip by count
- **Stock constructions and the dense noun style** (guide 1, seventh and ninth habits): "serves as" for "is", negative parallelism in every form, reflex lists of three, significance tails, nominalisations and stacked "-ing" clauses
- **Banned words** from the canonical list (moreover, furthermore, however, therefore, additionally, leverage, robust, seamless, ensure, delve, foster, and the rest)
- **Banned expressions** ("It's important to note", "That being said", "dive into", "In conclusion", and the rest)
- **Banned constructions** ("It's not X, it's Y" → state the positive)
- **Marketing-adjective compounds** (production-grade, enterprise-grade, mission-critical, future-proof, etc.)
- **Templated openers** ("Let me explain", "Picture this", "Here's the thing", "Imagine this")
- **Templated closers** ("In conclusion", "To summarise", "Hopefully this helped", "Happy coding")
- **Uniform paragraph rhythm**: intro / bold hook / body / blockquote, repeated. Mix short and long. Drop fragments occasionally.
- **Over-bolding**: one bold per paragraph is too many. Keep bolds that act as search anchors in pitfalls / error-message / troubleshooting sections.
- **Recurring 💡 / 🚩 / ⚠️ blockquote rhythm**: fold most into prose. One earned section-closing punchline blockquote at the end of the post is fine if it isn't preceded by 💡 and isn't part of a recurring rhythm.

Apply the judgement clause: keep a banned word only when used in its **literal technical sense** (e.g. "framework" as a software framework, "dynamic" as dynamic dispatch). Note the keep in the change log. Marketing uses of the same word always get replaced.

### Pass 4 — UK tone

Apply the framework from the UK-tone wiki page. Warren's specific calibration matters here: he has been criticised for being too direct or dismissive of other opinions. The steelman framework is how that is corrected; it is not optional.

- **Steelman the opposing view before disagreeing.** Credit what the alternative gets right. Then explain where it stops working for the case at hand. The disagreement still has to land — this isn't about disappearing the opinion.
- **Hedge non-absolute claims.** "X never works" becomes "X's design wasn't shaped around Y". Avoid "never", "always", "impossible" when softer is accurate.
- **Reframe oppositional headers.** "Why X fails" becomes "Where X has limits" or "Where X's design fits a different shape".
- **Frame challenges as questions** where appropriate.
- **No defensive openers.** Drop "To be clear", "Just to clarify", "I want to pre-empt the obvious objection".
- **Bring the reader to Warren's side** rather than dismissing alternatives. The goal of a piece advocating a position is to make the reader want to follow; combative framing makes the reader defensive.

Concrete pattern for any section where Warren is arguing for a choice: first paragraph credits the alternative; second paragraph names the trade-off that shifts; third paragraph defends Warren's pick on its own terms.

### Pass 5 — Correctness (hallucination prevention)

**Read this first: the historical failure rate on Pass 5 is ~70%.** Voice-review previously shipped hallucinated "corrections" (renaming real identifiers, replacing correct counts with arbitrary ones, swapping methodology mid-document). All of those failures had the same root cause: I ran a grep, didn't open the matching files, and substituted my count for the deck's. **This pass defaults to flagging, not fixing.**

**Default behaviour for Pass 5:**

- **Qualitative correctness** (does this sentence make sense, is the argument structurally sound, is the punctuation right): fix in place, normal.
- **Quantitative correctness** (numeric counts, identifier names, version numbers, file paths, percentages, statistics, performance claims): **flag, do not fix**, unless the change log can cite a specific file you opened and read.

The asymmetry is deliberate. A flagged claim is recoverable (Warren reviews, decides, applies). A silently-edited wrong claim ships under his name. Fail toward the recoverable outcome.

This pass should read like human review: open the file, scan the surrounding code, confirm or refute the claim, write up what you found. Speed at this pass is not a virtue. Skipping the read step is the failure to guard against.

**Required workflow for every concrete claim** (code identifier, library API, version, file path, statistic, count, performance number):

1. **Find candidate evidence with grep, using multiple patterns.** Identifier-style claims need a *bare-word* search (`grep -rE "\bIdentifier\b"`) AND a declaration search (`class X`, `function X`, `const X =`, `export X`) AND an import-side search (`from '...'`). One pattern returning nothing doesn't mean the thing doesn't exist; it means *that pattern* found nothing.

2. **OPEN the files grep returned and read them.** Not the line grep matched in isolation — the surrounding 20-50 lines. Confirm the match is the thing the deck is talking about, not a mock, not a test stub, not a same-named-different-thing, not a comment.

3. **Trace identifiers to their source.** If the deck names `Foo`, find where `Foo` is *defined*, not just mentioned. Read the import path. Open the file the import points at. Confirm the actual class/hook/type.

4. **For numeric claims, count via at least two methodologies, then open files to verify.** A directory can hold one, two, or zero wrappers. Grep counts lines, not files, not consumers. Open a sample.

5. **Cross-check against the deck's neighbouring numbers.** If the deck says "3 Apollo + 18 TanStack + 0 RTK" and your methodology gives 3 for Apollo (matches) but 14 for TanStack (doesn't), the methodology in use is whatever produces 3 for Apollo. Use that same methodology for TanStack — or don't substitute at all.

6. **Decide: leave-as-is, flag, or fix-with-evidence.**
   - **Leave-as-is** is the default for any numeric or identifier claim where you can match the deck's methodology and the deck's number stands under it.
   - **Flag** is the next default. Most claims you can't verify confidently belong here. Pass the question to Warren with what you checked and what you couldn't.
   - **Fix-with-evidence** is the *last* option, and it requires:
     - You opened a specific file and read it
     - The file's content unambiguously contradicts the deck's claim
     - Your fix is consistent with the deck's methodology elsewhere
     - The change-log Evidence section cites the file path AND an excerpt/paraphrase of what you saw
   - If any of those conditions isn't met, flag instead of fix. Wrong-correction-shipped is worse than annoying-flag-for-review.

**The failure modes to avoid (from real incidents):**

- *"I greped for `class StateManager` and found nothing, so the identifier doesn't exist."* — Wrong. The class was in a workspace package (`@hlmobile/domain`), imported across many files. The right grep would have been `\bStateManager\b`. The right *next step* after grep would have been to open one of the importing files and follow the import path.

- *"I counted 6 sub-directories + 1 root file = 7 wrappers."* — Wrong. Sub-directories can contain multiple wrappers. The right next step is `ls` each sub-directory to verify one-wrapper-per-directory.

- *"I counted 15 matching grep lines from `@tanstack/react-query` imports."* — Off by one. One file had two import statements. Line count ≠ file count. The right next step is `grep -rl` (files) AND open a few to confirm they're all genuine consumers.

- *"I counted hook import sites for `useInvestmentsPriceManager` and called those 'consumers'."* — Wrong frame. The deck was counting consumers of the underlying `StateManager` primitive (the prop the hook returns). Different denominator. The right next step is to open the hook, see what it returns, then grep for *that* shape.

**Known codebase locations to check before flagging anything as "unverified":**

- `~/Developer/warrendeleon/rn-warrendeleon/` — Warren's RN portfolio app
- `~/Developer/warrendeleon/warrendeleon.com/` — Warren's blog/website (+ `src/data/workxp-en.json` for career facts)
- `~/Developer/HL/hl-mobile-app/` — HL mobile codebase (features, common/, core/)
- `~/Developer/HL/hl-portal-web/` — HL web codebase
- `~/Developer/HL/ucx-core-mobile-platform-docs/` — HL platform docs and ADRs
- `~/Developer/dotfiles/` — Warren's dotfiles (RAG, scripts, configs)
- `~/.wiki/hl/` and `~/.wiki/personal/` — curated wiki for facts and decisions

For library API claims, check the installed package's `package.json` for the version, then **open the package's `node_modules/<pkg>/dist/*.d.ts` types** and read the actual exported shape. Don't trust your memory of an API; the version installed might pre-date or post-date the API you're thinking of.

For code blocks specifically:
- Verify identifiers (function names, class names, exports) exist in the linked repo *by opening the file they're defined in*, not just by grep
- Verify imports resolve to real packages (open `node_modules/<pkg>/package.json`)
- Verify API shapes match the current installed version (read the `.d.ts`)
- Verify file paths exist (`ls` the path, don't assume)

**Be honest in the change log about what you actually checked.** "Verified against `~/Developer/HL/hl-mobile-app/features/account/src/hooks/useInvestmentsPriceManager.ts` lines 1-50" beats "verified against codebase" because it tells the user *what file you read* and lets them check your work.

### Pass 6 — Engagement / retention

For blog posts and slide decks especially, but applies to any longer-form artefact. Without changing the core argument:

- **First paragraph hooks with the concrete payoff.** State what the reader gets if they stay. No long preamble. No "let me set the stage".
- **Front-load the most useful idea.** Don't bury under setup. The reader's attention is highest in the first 100 words.
- **Subheadings signal payoff, not topic.** "How the token refresh actually works" beats "Token refresh". "Where one-store hits its limits" beats "Limitations".
- **Cut padding.** If a paragraph repeats the previous one in different words, delete it.
- **Break up walls of text** with short sentences, fragments, or a code block.
- **Tutorials**: signpost the journey. Number the steps. State what the reader has built at each milestone. Readers drop off when they lose the thread.
- **Slide decks**: each slide should earn its place. Bullets should land payoffs, not list topics. Presenter notes are spoken scripts (follow existing convention; not editorial commentary).
- **End on the last substantive point**: a working result, or the question still open. Not a stated lesson, an epilogue or "Hopefully this helped" (Pass 2). A single earned punchline blockquote is fine where the prose runs thickest, per guide 6.

If Warren tags the doc with retention concerns ("readers aren't reaching the end", "this feels dry"), elevate this pass: be more aggressive on padding, more deliberate on signposting.

### Pass 7 — British English

Behaviour, colour, organisation, optimised, recognise, licence, analyse, modelled, prioritise, organisation, behaviour, favourite, defence, programme (in the BBC sense, not software-programme). Match across the document; don't touch quoted code, library names, or upstream identifiers (`color` in CSS stays `color`).

### Pass 8 — Tighten

Apply guide 7's "Tighten without losing content" to the whole document. Say each inventory item once, in the fewest words that keep it exact: shorten wordy phrasing, cut framing that announces what comes next, merge passages that cover the same ground (keeping the fuller detail) and cut restatements. Numbers, identifiers, code, commands, quotations and link targets stay byte-for-byte. Tighten prose only: never shorten, cut, merge, summarise or turn into prose a code block, diagram, chart, data table, log, console output, data excerpt or quoted record. Keep the sentences plain and connected; a shorter document comes from saying each thing once, not from a telegraphic style.

Then verify: tick every inventory item against the edited text. Put back anything missing or weakened (a dropped qualifier, "may" turned into "will", a lost condition) in its shortest exact form.

**You decide every cut. Never refer one to Warren.** When shortening a passage would lose an item, the item stays: rewrite around it, or leave the passage as it was. There is no target length, and a document that is already as short as its content allows is a valid result.

## Output — structured change log

After editing, report under 500 words. Be specific so Warren can absorb the pattern and double-check the correctness work.

```
**Mode**: senior expertise | learning post
**Word-count delta**: +X / -X
**Document type tag**: tutorial / easy-style / essay / deck / artefact

**Authority calibration**:
- Cautionary-tale framings stripped (line N → senior observation)
- Authority claims cross-checked (against workxp-en.json: ...)

**Structure**:
- Sections reordered, endings cut, template structures removed (what moved or went, and why)
- Gaps flagged for Warren: missing dead end, outside cause, cost, open question or named specific

**AI tells removed** (rough count by category):
- Clause-stitching em-dashes fixed: N (legitimate em-dashes kept) · Banned words/expressions: N · Templated openers/closers: N
- Marketing-adjective compounds: N · Decorative blockquotes folded: N · Stylistic bolds stripped: N

**UK-tone fixes**:
- Steelmans added (which alternatives, which sections)
- Oppositional headers reframed (which → which)
- Defensive openers dropped

**Correctness — fixed** (evidence required for each entry, otherwise demote to "flagged"):
- [Claim that was changed] → [new value]
  - File read: `path/to/file.ts` lines N–M
  - What I saw: [excerpt or one-line paraphrase]
  - Why my fix matches the deck's methodology: [...]
- [next entry]

**Correctness — flagged, NOT fixed** (default for most numeric/identifier claims):
- [Claim in the deck] → [my measurement] under [methodology I tried]; under [alternative methodology] I got [different number]. Methodology mismatch means I can't substitute confidently. Recommend Warren verify under his original methodology.
- [Suspect claim] → opened `path/to/file` but couldn't find the referenced thing. Possibly: [hypothesis]. Flagging for review.

**Engagement restructure**:
- Opening reshaped (was → now)
- Subheadings sharpened
- Padding cut

**British English**: count of Americanisms fixed

**Tightening**:
- Word-count delta from this pass, and the inventory result ("43 of 43 items kept")
- Items restored after the verify step, if any

**Banned-but-kept** (judgement clause):
- Banned words kept for literal technical use, with reasoning

**Out of scope / unverifiable**:
- External claims (release dates, vendor policies, CVE scores)
- Bundle-size or perf claims needing instrumentation
- Self-hosted infra config not in this repo
```

**The verification gate**: every entry under "Correctness — fixed" MUST have an Evidence section (file read + what you saw). If you can't produce that, the entry belongs under "Correctness — flagged" instead. No exceptions. A change log with five fixed entries and zero Evidence subsections is a failed run — go back to Pass 5 and either gather the evidence or move them to flagged.

## What NOT to do

- Don't invent or speculate. Flag, never fabricate. This applies especially to dates, statistics, code identifiers, and personal facts.
- Don't invent a dead end, source, opinion or experience to make a piece read as written by a person. The structure pass restores what the material holds and flags what it lacks.
- Don't add new sections or new examples. Clean, calibrate, correct, tighten. Restructure within the existing scope.
- Don't shorten code, charts or raw data. Tightening is for prose; the content-inventory check reports a changed code block, chart or data row as missing.
- Don't make Warren the cautionary tale outside learning-post mode.
- Don't add AI / Claude / ChatGPT references in the body of any document, except posts that are literally about those tools (the Claude RAG series, MCP server tutorial, etc.).
- Don't touch `tags`, `publishDate`, `slug`, `campaign`, `series`, `heroImage`, `heroAlt`, `locale`, `draft`, `relatedPosts` in frontmatter.
- Don't downgrade the technical claim to make a sentence read more humble. The voice softens; the expertise doesn't.
- Don't ask Warren to approve a cut, and don't drop content to hit a length. The inventory decides: an item a cut would lose stays.
- Don't summarise back what Warren said as if it were a finding. The summary is for new information he can learn from.
