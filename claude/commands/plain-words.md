---
description: Word and sentence pass for any text, long or short: lint hits read in their sentence, avoid-list words, stock constructions, em-dashes, idioms, undefined acronyms, British spelling, leftovers. For Jira comments, emails, PR text, wiki pages, blog drafts.
model: sonnet
effort: medium
---

Edit one text in place for words and sentences. Standard: `~/.wiki/personal/writing/ai-writing-gotchas.md` (every table, the punctuation rules, the judgement clause), `plain-sentence-construction.md` (the habits, above all the stock constructions) and the "Leftovers search" section of `revision-passes.md`. For a Jira comment also read `~/.wiki/news-uk/commercial-technology/jira-comment-conventions.md`.

Target: the file named, or the text in the conversation (write it to a scratchpad file first so the checks can run). Take a copy first (`cp -p`); a reader must be able to compare.

1. **Lint.** `python3 ~/Developer/dotfiles/claude/hooks/writing-lint.py <target>`. Exit 2 means a guide is missing or no longer parses: say so and scan by hand. Each hit is a pointer, not a finding.
2. **Read every hit in its sentence.**
   - Literal technical use ("framework" as a software framework, "dynamic" as dynamic dispatch): keep the word, record it under kept.
   - Filler or marketing colour: replace with the word that fits the sentence, not always the table's first column.
   - Load-bearing term: rewrite the sentence rather than swap the word.
   Never run the table as a substitution script.
3. **Beyond the lint.** Stock phrases and constructions (negative parallelism, reflex triples, "serves as" for "is", significance tails, stacked "-ing" clauses), idioms and engineer slang, acronyms undefined at first use, templated openers and closers, chat leftovers ("I hope this helps"), placeholders and tool artefacts.
4. **Punctuation.** Em-dashes near zero in prose, judged by density and function; use a colon, comma, parentheses or full stop where one serves as well, and vary them. `term — definition` rows stay. Never strip by count.
5. **British English.** behaviour, colour, organisation, optimise, recognise, licence, analyse, modelled, prioritise, favourite, defence. Leave quoted code, library names and upstream identifiers (`color` in CSS stays `color`).
6. **Never change** a number, identifier, version, quotation, code block, chart or data table. A doubt about one is reported, not edited.
7. **Check.** `python3 ~/Developer/dotfiles/claude/hooks/content-inventory.py check <copy> <target>` must exit 0. Then rerun the lint and read the hits left.
8. **Report** in under 100 words: hits read, edits made, words kept under the judgement clause with the reason (an empty list on a long text means the read was too fast), the inventory result.

Run `/tighten` after this, not before. Never post, send or publish the result.
