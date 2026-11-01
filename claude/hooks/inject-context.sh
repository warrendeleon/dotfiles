#!/bin/bash
# UserPromptSubmit hook: inject a compact, standing reminder so the assistant
# consults the knowledge stores autonomously instead of waiting to be told.
#
# Whatever this script prints to stdout is added to the model's context for the
# turn. Keep it SHORT: it fires on every prompt, so a RAG dump here would be
# noise. This injects a routing reminder and a pointer, not data.

input=$(cat)

cat <<EOF
[Knowledge routing, standing reminder injected by hook]
Consult proactively, do not wait to be asked. Lookup order for anything substantive: wiki (~/.wiki) -> RAG (mcp__rag__search) -> codebase.
- Resuming or starting work: first search ~/.wiki/sessions/ and RAG for the prior summary, so you load context instead of guessing.
- Finishing substantial work: update the wiki page for that subject without asking. Search first and add to the existing page; a new page only when none covers it, linked from its index; never a duplicate page or fact. Session notes in ~/.wiki/sessions/ are auto-generated; never hand-write one.
- Knowledge goes in the wiki; memory files hold working rules and wiki triggers only.
EOF
