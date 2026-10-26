---
description: Shorten a text without losing content, context or meaning. Takes an inventory, cuts prose, checks the inventory, reads original against edit, reports words before and after. For Jira comments, emails, PR text, wiki pages, any prose before it goes out.
model: opus
effort: high
---

Tighten one text in place so it is shorter and loses nothing. Standard: guide 7, "Tighten without losing content" (`~/.wiki/personal/writing/revision-passes.md`).

Target: the file named, or the text in the conversation (write it to a scratchpad file first so the checks can run). Run it last, after any structure or word edit. The `edit-doc` workflow runs this skill as its tighten stage, with the backup and inventory it already took: it skips steps 1 and 2 and uses those.

1. **Back up.** `d=$(mktemp -d "$HOME"/.claude/edit-doc/<name>.XXXXXX) && cp -p <target> "$d"/original<ext> && cmp <target> "$d"/original<ext>`, then `wc -w` on the target. If a command fails, edit nothing.
2. **Inventory.** List every claim, number, name, identifier, date, link, example, step, caveat, qualifier, condition ("only when"), reason ("because") and decision, one numbered line each with a short quote. Context is content: the reason a step exists and the condition a claim holds under are items. Write it to `$d/inventory.md`.
3. **Cut prose.** Say each item once, in the fewest exact words.
   - Shorten wordy phrasing, cut framing that announces what comes next, cut restatements and closing recaps.
   - Merge passages that cover the same ground, keeping the fuller detail.
   - Where two sections state the same item, keep it once in the section the text's structure gives it and cut the other. Phrase-level trims alone fall short: whole sentences and paragraphs that another place already carries are where most of the words are.
   - Cut an example only when nothing in it is missing from another.
   - Add nothing: no new fact, example or section.
   - Keep the sentences plain and connected. A shorter text comes from saying each thing once, never from a telegraphic style or from dropping the words that join a thought.
   - Leave numbers, identifiers, versions, commands, quotations and link targets byte for byte. Never shorten, cut, merge or turn into prose a code block, chart, data table, log, console output or data excerpt.
   - You decide every cut; refer none to the author. When a cut would lose an item, the item stays. There is no target length, and a text already as short as its content allows is a valid result.
4. **Gate.** Three checks, the same ones the `edit-doc` workflow runs; each at most three times, stopping on exit 2 (it cannot run: say so) and when a run reports the same missing set as the one before.
   - `python3 ~/Developer/dotfiles/claude/hooks/content-inventory.py check "$d"/original<ext> <target>` must exit 0; restore what it reports missing.
   - `python3 ~/Developer/dotfiles/claude/hooks/inbound-quotes.py check "$d"/original<ext> <target> --in <the target's folder>` must exit 0: another file quotes each span it reports, and that file is not edited here, so the span goes back word for word.
   - `python3 ~/Developer/dotfiles/claude/hooks/writing-lint.py <target>`: read each hit in its sentence. A leftover (a placeholder, a chat reply, a tool artefact, a truncated ending) is fixed; a listed word was there before the cut and is not this skill's job, unless the cut made it.
   Then `wc -w`: the text must not exceed the original plus 2%. If it does, make one more cut over the whole prose, then count again.
5. **Read original against edit.** Open both and list every claim, qualifier, condition, reason, example or piece of context that is gone or weakened ("may" turned into "will", a lost "only when", a lost "because", two paragraphs run together). Put each back in its shortest exact form. The script cannot see these; this read is the check.
6. **Report** in under 100 words: words before and after with the % change, the inventory result ("43 of 43 kept"), items restored, the backup path.

Never post, send or publish the result; that stays the author's call.
