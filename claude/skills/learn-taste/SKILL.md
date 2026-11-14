---
name: learn-taste
description: Turn a session's design corrections into rules, with their why, scoped to one brand and one medium, in the wiki (`~/.wiki`), never in the project folder. Use when the user corrects a design choice (spacing, type size, colour, layout, chart, motion, copy on a visual), edits your design by hand, or picks one variant over another.
---

# Learning Taste

Every correction a user makes is taste the agent didn't have. If it isn't written down, the next session makes the same mistake and the user corrects it again. This skill finds those corrections, turns each one into a rule with its reason, and writes it where the next agent will read it.

It does ONE thing: write rules. It never changes component code, and it never adds a rule the user didn't express.

## Hard Rules

1. **Only the user's taste.** Every rule traces back to something the user said, edited, or confirmed. Never add a rule because it seems like good practice. That's your taste, and your taste is what the user was correcting.
2. **Never invent a why.** If the user gave no reason, propose one marked *inferred* and get it confirmed before writing. A wrong why is worse than none: the next agent extends the reasoning to cases it doesn't fit.
3. **Propose, then stop.** Present every candidate and write only what the user approves. A wrong rule repeats in every future session, exactly like the mistake would have.
4. **Rules live in the wiki, never in the project folder.** Every rule is written to the wiki page for its brand and medium. This skill never creates or edits a `DESIGN.md`, a lint rule, a test, a `CLAUDE.md` or any other file in a repository or working folder. If a violation could be found by matching code (a banned value, a raw hex instead of a token), say so in the report as a check the user could ask for; build one only when the user asks for it in words.
5. **Every rule has one scope: a brand and a medium.** Brands are separate worlds: warrendeleon.com, News UK, and any other client or project each keep their own rules. So are media: a web page, a dashboard, a slide deck, an A4 document. A rule learnt on a deck is a deck rule; a rule learnt on warrendeleon.com is a warrendeleon.com rule. Never write a rule to another brand or medium, and never apply one there, unless the user said in words that it holds there too.
6. **Write for an agent that wasn't here.** No "like we discussed" or "the card from earlier". Name the class of component, the value, the token, the file.

## Workflow

### Phase 1: Collect corrections

Read the current conversation from the first turn. If the user names earlier sessions and you can read their transcripts (Claude Code stores them as JSONL under `~/.claude/projects/<project>/`), read those too.

Explicit corrections are the minority. Look for all five signals:

| Signal | Example | What it tells you |
| --- | --- | --- |
| Explicit correction | "No, semi-transparent shadow, not a border" | The rule, often with the why |
| Silent edit | User changed `duration: 400` to `200` in a file you wrote | Your default was wrong and their value is the rule. Find these through notices that a file changed outside your edits, or by diffing a file against what you last wrote |
| Repeated nudge | "Smaller." → "Still too big." → "Ok" | Your default was off by the total distance. Record where they landed, not the steps |
| Revert or rejection | "Undo that", picking variant B over A, deleting something you added | What not to do. The why is usually missing, so it goes to Phase 3's questions |
| Confirmed non-obvious choice | "Yes, keep the icon outside the button" | A choice a fresh agent might not repeat. Record it only if a fresh agent would plausibly do otherwise |

For each one, capture the user's exact words (or the diff), what you had done, what they wanted instead, any reason they gave, and its scope: the brand the work belongs to and the medium it was made in.

Skip what isn't taste: functional bugs, content specific to one screen ("the headline should say Pricing"), and corrections to your understanding of the task.

**Completion criterion:** every turn has been read, and every correction is listed with its source quote or diff.

### Phase 2: Filter

Walk every correction through this tree:

```
Would a fresh agent building a DIFFERENT component, page or slide for this brand and medium make the same mistake?
├── No (a one-off: this campaign's color, this page's layout) → Skipped
└── Yes
    ├── Does an existing rule cover it? Check the wiki page for this brand and medium.
    │   ├── Yes, and it says the same thing → The rule failed. Rewrite it stricter
    │   │   (a number, a token, "never") instead of adding a duplicate.
    │   ├── Yes, and it contradicts → Conflict. Show both; the user picks.
    │   └── No → continue
    ├── Can a violation be found by matching code? → Note it as a possible check; it is still written as a rule.
    │   Keep a one-line rule too, so the why is recorded somewhere.
    └── Did the user say it applies beyond this brand or this medium? → Record the wider scope in their words.
        Otherwise it stays in the brand and medium it came from. Never widen a scope on your own judgment:
        put "also for decks?" or "also for News UK?" in the questions if it looks likely.
```

**Completion criterion:** every Phase 1 correction ends as Skipped, Rewrite, Conflict, or a rule to generalize.

### Phase 3: Generalize and find the why

Pick the narrowest level that would have prevented the mistake on the next, different component:

| Level | Example | Verdict |
| --- | --- | --- |
| Instance | "The pricing card gets a shadow, not a border" | Too narrow: it only protects this card |
| Class | "Raised surfaces (cards, popovers, menus) separate from the background with `shadow-raised`, never a solid border" | Write this |
| Universal | "Never use borders" | Too broad: breaks inputs, dividers, tables |

If the same correction came up on two or more different components, that's evidence for the class level. If two levels both seem right, ask.

Write the rule strictly: values and token names from this codebase, "always" or "never", no "prefer" or "try to". Use softer wording only when the user framed it as a preference.

Then the why. Use the user's reason, in their words, when they gave one. Otherwise write your best candidate, mark it *inferred*, and put it in the questions for the user.

**Self-test before proposing:** read only the rule and its why, then picture the original task. Would an agent that knows nothing else produce what the user wanted? If it could still produce the wrong version, the rule is too vague. Add the value, the token, or the exception.

**Completion criterion:** every kept rule has a level and a why marked as the user's or *inferred*.

### Phase 4: Decide where it goes

Always the wiki. One page per brand and medium; a rule is written to its own page and nowhere else.

1. Search the wiki for the page that already covers this brand and medium and add to it. Known pages: warrendeleon.com on the web is `~/.wiki/personal/website/design.md`; slide decks are `~/.wiki/personal/writing/slide-decks.md`, under a heading for the brand when the rule is one brand's.
2. If none covers it, create one in that brand's part of the wiki (News UK work under `~/.wiki/news-uk/`, personal work under `~/.wiki/personal/`), named for the brand and the medium, and link it from that area's index. Never a second page for the same brand and medium.
3. A rule the user said holds for every brand and every medium goes to the page they name for global rules; ask if they have not named one.

Inside the page, put the rule under the matching section: Surfaces · Color · Typography · Spacing & layout · Charts · Motion · Interaction · Copy. Create the section if it is missing.

Entry format:

```md
## Surfaces

- **Raised surfaces (cards, popovers, menus) use `shadow-raised`, never a solid border.**
  Why: a solid border makes a raised surface look flat and heavy; a semi-transparent shadow separates it from the background and adapts to both themes.
  <!-- 2026-11-12: "no, semi-transparent shadow, not a border" -->
```

The comment holds the date and the user's words. When a later correction conflicts, it shows which rule is newer and what the user actually said.

### Phase 5: Report and stop

Present the report below, then stop.

### Phase 6: Write on approval

Write only the approved items, to the wiki page only. Show the resulting diff of that page. Touch nothing in the project folder.

## Required Output Format

### Rules to add

| # | You said | Rule | Why | Scope | Where |
| --- | --- | --- | --- | --- | --- |
| 1 | "no, semi-transparent shadow, not a border" | Raised surfaces use `shadow-raised`, never a solid border | Solid borders look flat and heavy; shadows adapt to both themes | warrendeleon.com · web | wiki: `personal/website/design.md` › Surfaces |
| 2 | Changed `duration: 400` → `200` in `Dropdown.tsx` | Dropdowns open in 200ms | *inferred:* 400ms felt sluggish on a surface opened many times a day | warrendeleon.com · web | wiki: `personal/website/design.md` › Motion |

### Needs your answer

Each *inferred* why, each ambiguous generalization level, and each question about whether a rule holds for another brand or medium. One line each, with your recommendation.

### Conflicts

The existing rule, the new correction, and which one you'd keep.

### Could be a check

Each rule a lint rule or test could enforce, in one line. Nothing is built unless the user asks.

### Skipped

One line per skipped correction and why, so the user can override.

Close with: "Say `write all` or `write 1, 3`, and answer the questions above."

If the session had no taste corrections, say so in one line. That's a good result, not a failure.

## Invocation Variants

| Invocation | Behavior |
| --- | --- |
| `/learn-taste` | Current session, full workflow, stop at the report |
| `/learn-taste <sessions>` | Also read the named or most recent N session transcripts |
| `write all` / `write 1, 3` | Write the approved items from the last report |
| `/learn-taste prune` | Read the wiki page for the brand and medium and propose merges for duplicates, fixes for contradictions, and stricter wording for vague rules. Same propose-then-stop rule |
