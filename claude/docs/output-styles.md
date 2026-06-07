# Output styles

An output style is a markdown file under `claude/output-styles/` that tunes Claude Code's voice for every response. It's prepended to the system prompt on every turn, so it's load-bearing: edit with care, keep it short.

`warren.md` is the one shipped with these dotfiles. It encodes Warren's voice. If you're someone else using this repo, make your own.

## How to make your own

```bash
cp claude/output-styles/warren.md claude/output-styles/<yourname>.md
```

Then:

1. **Change the `name:` field** in the frontmatter (e.g. `name: Alice`). This is the value Claude Code uses when you pick the style from `/config`.
2. **Update the `description:`** to a one-liner describing your voice.
3. **Rewrite the body** to describe YOUR voice, not Warren's. The body becomes the actual prompt Claude reads.
4. **Update `claude/settings.json`**: change `"outputStyle": "Warren"` to `"outputStyle": "<Yourname>"`.
5. **Restart Claude Code** (or run `/config` and re-select the style) to pick up the change.

Delete `warren.md` from your fork if you want a clean tree. Keeping it costs nothing; it just sits unused.

## What to put in an output style

Output styles are for **how Claude communicates**, not what it knows or what tools it uses. Good output-style content:

- **Tone and register.** Formal / informal, dry / warm, blunt / diplomatic. Be specific. "Direct" is vague; "no throat-clearing openers, no closing recaps" is actionable.
- **Voice quirks.** UK vs US English. Contractions vs formal forms. Sentence length preferences. Vocabulary you want or don't want.
- **Response shape.** When to use bullets vs prose. When to use headings. When a one-sentence answer beats a section. How long is too long.
- **Banned words / phrases.** Specific tokens you find irritating. Examples: "Great question!", "Let me check", "It's important to note", em-dashes.
- **Pushback policy.** When to defer vs when to argue. Whether to soften disagreement or surface it on the first turn. Whether "sure, I can do that" is allowed when you actually disagree.
- **Sycophancy controls.** What constitutes empty affirmation in your eyes. What a real assessment looks like.
- **Concrete examples.** Show, don't tell. "Bad: 'Great question! Let me dive into this...' Good: '<the answer>'." Examples beat abstract rules.

## What NOT to put in an output style

These belong elsewhere; putting them in the style wastes tokens and dilutes focus:

- **Tool-use rules, MCP server references, RAG/wiki lookup order.** Those go in `claude/CLAUDE.md` (global) or a project `CLAUDE.md`.
- **Facts about you** (your job, your projects, your preferences for specific libraries). Those go in Claude's memory system (`mcp__rag__log_action` for ephemera, the wiki for canonical facts).
- **Project conventions** (coding style, test patterns, framework choices). Per-project `CLAUDE.md`.
- **Long lists of banned words.** Keep the top 10 or so. Offload the canonical list to a separate file and reference it. Warren's style does this with `~/.wiki/personal/ai-writing-gotchas.md`.
- **Anything secret** (API keys, internal URLs, employer-confidential preferences). Output styles are committed to dotfiles.

## Frontmatter fields

```yaml
---
name: Yourname                    # Required. Matches the value in settings.json "outputStyle".
description: One line summary.    # Shown in Claude Code's style picker UI.
keep-coding-instructions: true    # Optional. If true, Claude keeps its built-in coding behaviour
                                  # alongside your voice tuning. If false, your file replaces it
                                  # entirely (usually not what you want).
---
```

## Iterating on a style

Output styles are write-once-then-forget for most people, but they're worth iterating on for a session or two when you first make one:

1. Make the file, point `settings.json` at it.
2. Open Claude Code and ask it to write something representative (a code review, a commit message, an explanation, whatever you do most).
3. If the output sounds wrong, note exactly what's wrong (sycophantic, too long, wrong English variant, hedging too much, etc.).
4. Add a specific instruction to your style addressing that. Be concrete. "Avoid hedging" is weak; "Don't say 'it seems' or 'might be' unless you genuinely don't know" is strong.
5. Restart Claude Code or `/config` re-select to pick up the change.
6. Repeat until the output reads like you wrote it.

You'll find a sweet spot somewhere between 50 and 200 lines. Much shorter and it has no effect. Much longer and you're paying for tokens you don't need and Claude starts ignoring the less-emphasised rules.

## Examples to learn from

- `claude/output-styles/warren.md` in this repo: opinionated, UK-tone, anti-sycophancy, anti-AI-tells. Long because Warren cares a lot about writing voice.
- Claude Code ships several built-in styles (default, learning, explanatory). Run `/config` to browse them. Reading the built-ins gives you a feel for the format and depth.

## Common mistakes

- **Writing the style as a description of yourself instead of an instruction to Claude.** "Warren is a senior engineer" is descriptive. "Write to a senior engineer's level: no hand-holding, no oversimplification" is an instruction. Use the second form.
- **Telling Claude what to do but not what NOT to do.** Bans are often more effective than prescriptions. "Don't open with 'Great question'" is more enforceable than "be direct".
- **Overlapping with CLAUDE.md.** If a rule already lives in `claude/CLAUDE.md`, don't repeat it in the style. Pick the right home for each rule.
- **Forgetting to update `settings.json`.** Renaming the file or changing `name:` without updating `"outputStyle"` leaves Claude on the previous style silently. Always change both.
