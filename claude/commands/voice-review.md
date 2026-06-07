Edit a document in place against Warren's writing conventions, then report a structured change log so he can absorb the patterns.

If the user specifies a file, voice-review that. Otherwise, prompt for the file. If the user says "as a learning post" or "--learning", run in learning-post mode (see Mode section).

## This is AI judgement, not a substitution script

The wiki gotchas page contains a table of banned-term → replacement entries. **Do not treat this table as a sed script.** Each occurrence of a flagged term must be read in its sentence context and assessed before any change is made:

- Is the word being used in its **literal technical sense** (the judgement clause applies, keep the word, note in "Banned-but-kept")?
- Is it **filler / marketing colour** (replace, but pick the replacement that fits the sentence's rhythm and register — not always the first column of the table)?
- Does the **sentence as a whole** need rewriting because the banned term is load-bearing? Then rewrite the sentence rather than swap the word.

The table is reference material. The work happens between your eye reading the sentence and your hand making the edit. If the change-log's "Banned-but-kept" section is empty across a long document, that's a red flag: you weren't reading carefully enough. Real prose has technical uses of banned words; the skill should catch and preserve them.

Same principle applies to every other pass — authority calibration, UK-tone, correctness, engagement. Every change is a judgement made in context, never a mechanical find-and-replace.

## Required reading (load before touching the document)

- `~/.wiki/personal/ai-writing-gotchas.md` — banned words, expressions, constructions, em-dashes, judgement clause
- `~/.wiki/personal/uk-tone-writing.md` — steelman framework, hedge non-absolutes, no defensive openers
- `~/Developer/warrendeleon/warrendeleon.com/src/data/workxp-en.json` — Warren's actual work-experience data (use this to verify any authority claims; never embed a specific year if it can be checked here)
- The target document, in full, before editing

If any required file is missing, flag it and proceed with the others. Don't fabricate authority claims from gaps.

## Mode

**Default mode: senior expertise.** Warren is a Senior Software Engineer with significant industry experience and an Engineering Manager. The voice reads from that seat: observation, teaching, comparison, authority. He shares knowledge; he is not the cautionary tale.

**Learning-post mode (opt-in only)**: invoked when Warren explicitly says "as a learning post", "--learning", or "this is a learning piece". In learning-post mode, the journey from learning to applying is the explicit narrative. The RAG / wiki series is the canonical example: that journey is the subject. Outside this mode, never write Warren learning a thing as an excuse to write about it.

When unclear, default to senior expertise.

## Rules

1. **Edit the document in place** for qualitative passes (voice, AI tells, UK tone, engagement, British English). These are the passes where the model performs well.
2. **DEFAULT TO FLAGGING, not fixing, for Pass 4 (correctness)**. Numeric claims, identifier names, version numbers, statistics. **Do not auto-correct these.** Open the relevant file, read it, write your finding in the Pass 4 Evidence section of the change log, and let Warren decide whether to apply the change. The skill has historically been 70% wrong on numeric "corrections" — silent edits to numbers and identifiers are how that hallucination ships under Warren's name. Flag-not-fix is the default.
3. **Run all six passes in order.** Each pass has a clear remit; don't skip.
4. **Never fabricate to fix a problem.** If you'd have to invent a fact, flag it instead.
5. **Don't make Warren the cautionary tale** outside learning-post mode. He has been criticised for being too direct or dismissive; the steelman framework is how that gets calibrated, not by inserting self-deprecation.
6. **Tags, publishDate, slug, campaign, series, heroImage, heroAlt, locale, draft, relatedPosts** in frontmatter are hands-off. Title and description are in scope; stay within the original character budget for description.
7. **No em-dashes connecting clauses**, in any language, including languages where they're natural typography.
8. **Every correctness-pass entry in the change log MUST cite the file path you read and an excerpt or paraphrase of what you saw.** If you cannot cite a specific file you opened, the claim is unverified and must be flagged, not fixed. Hand-waving "verified against codebase" is not acceptable. This is the verification gate.

## Passes (run in order, edit in place)

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

### Pass 2 — AI tells

Scan the document against the gotchas wiki page. Strip:

- **Em-dashes connecting clauses** in every language; replace with period, colon, comma, or parenthesis
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

### Pass 3 — UK tone

Apply the framework from the UK-tone wiki page. Warren's specific calibration matters here: he has been criticised for being too direct or dismissive of other opinions. The steelman framework is how that is corrected; it is not optional.

- **Steelman the opposing view before disagreeing.** Credit what the alternative gets right. Then explain where it stops working for the case at hand. The disagreement still has to land — this isn't about disappearing the opinion.
- **Hedge non-absolute claims.** "X never works" becomes "X's design wasn't shaped around Y". Avoid "never", "always", "impossible" when softer is accurate.
- **Reframe oppositional headers.** "Why X fails" becomes "Where X has limits" or "Where X's design fits a different shape".
- **Frame challenges as questions** where appropriate.
- **No defensive openers.** Drop "To be clear", "Just to clarify", "I want to pre-empt the obvious objection".
- **Bring the reader to Warren's side** rather than dismissing alternatives. The goal of a piece advocating a position is to make the reader want to follow; combative framing makes the reader defensive.

Concrete pattern for any section where Warren is arguing for a choice: first paragraph credits the alternative; second paragraph names the trade-off that shifts; third paragraph defends Warren's pick on its own terms.

### Pass 4 — Correctness (hallucination prevention)

**Read this first: the historical failure rate on Pass 4 is ~70%.** Voice-review previously shipped hallucinated "corrections" (renaming real identifiers, replacing correct counts with arbitrary ones, swapping methodology mid-document). All of those failures had the same root cause: I ran a grep, didn't open the matching files, and substituted my count for the deck's. **This pass defaults to flagging, not fixing.**

**Default behaviour for Pass 4:**

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

### Pass 5 — Engagement / retention

For blog posts and slide decks especially, but applies to any longer-form artefact. Without changing the core argument:

- **First paragraph hooks with the concrete payoff.** State what the reader gets if they stay. No long preamble. No "let me set the stage".
- **Front-load the most useful idea.** Don't bury under setup. The reader's attention is highest in the first 100 words.
- **Subheadings signal payoff, not topic.** "How the token refresh actually works" beats "Token refresh". "Where one-store hits its limits" beats "Limitations".
- **Cut padding.** If a paragraph repeats the previous one in different words, delete it.
- **Break up walls of text** with short sentences, fragments, or a code block.
- **Tutorials**: signpost the journey. Number the steps. State what the reader has built at each milestone. Readers drop off when they lose the thread.
- **Slide decks**: each slide should earn its place. Bullets should land payoffs, not list topics. Presenter notes are spoken scripts (follow existing convention; not editorial commentary).
- **End on something concrete**: a takeaway, a working result, a question worth thinking about. Not "Hopefully this helped". A single earned punchline blockquote at the close is fine.

If Warren tags the doc with retention concerns ("readers aren't reaching the end", "this feels dry"), elevate this pass: be more aggressive on padding, more deliberate on signposting.

### Pass 6 — British English

Behaviour, colour, organisation, optimised, recognise, licence, analyse, modelled, prioritise, organisation, behaviour, favourite, defence, programme (in the BBC sense, not software-programme). Match across the document; don't touch quoted code, library names, or upstream identifiers (`color` in CSS stays `color`).

## Output — structured change log

After editing, report under 500 words. Be specific so Warren can absorb the pattern and double-check the correctness work.

```
**Mode**: senior expertise | learning post
**Word-count delta**: +X / -X
**Document type tag**: tutorial / easy-style / essay / deck / artefact

**Authority calibration**:
- Cautionary-tale framings stripped (line N → senior observation)
- Authority claims cross-checked (against workxp-en.json: ...)

**AI tells removed** (rough count by category):
- Em-dashes: N · Banned words/expressions: N · Templated openers/closers: N
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

**Banned-but-kept** (judgement clause):
- Banned words kept for literal technical use, with reasoning

**Out of scope / unverifiable**:
- External claims (release dates, vendor policies, CVE scores)
- Bundle-size or perf claims needing instrumentation
- Self-hosted infra config not in this repo
```

**The verification gate**: every entry under "Correctness — fixed" MUST have an Evidence section (file read + what you saw). If you can't produce that, the entry belongs under "Correctness — flagged" instead. No exceptions. A change log with five fixed entries and zero Evidence subsections is a failed run — go back to Pass 4 and either gather the evidence or move them to flagged.

## What NOT to do

- Don't invent or speculate. Flag, never fabricate. This applies especially to dates, statistics, code identifiers, and personal facts.
- Don't add new sections or new examples. Clean, calibrate, correct, tighten. Restructure within the existing scope.
- Don't make Warren the cautionary tale outside learning-post mode.
- Don't add AI / Claude / ChatGPT references in the body of any document, except posts that are literally about those tools (the Claude RAG series, MCP server tutorial, etc.).
- Don't touch `tags`, `publishDate`, `slug`, `campaign`, `series`, `heroImage`, `heroAlt`, `locale`, `draft`, `relatedPosts` in frontmatter.
- Don't downgrade the technical claim to make a sentence read more humble. The voice softens; the expertise doesn't.
- Don't summarise back what Warren said as if it were a finding. The summary is for new information he can learn from.
