#!/bin/bash
# UserPromptSubmit hook: inject a compact, standing reminder so the assistant
# consults the knowledge stores autonomously instead of waiting to be told.
#
# Whatever this script prints to stdout is added to the model's context for the
# turn. Keep it SHORT: it fires on every prompt, so a RAG dump here would be
# noise. This injects a routing reminder and a pointer, not data.

input=$(cat)

# Best-effort: detect the domain from the working directory so the reminder
# names the right wiki area. HL work lives under ~/Developer/HL.
cwd=$(printf '%s' "$input" | grep -oE '"cwd"[[:space:]]*:[[:space:]]*"[^"]*"' | sed -E 's/.*"cwd"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')
case "$cwd" in
  */HL/*|*/hl-*) domain="hl" ;;
  *)            domain="personal" ;;
esac

cat <<EOF
[Knowledge routing, standing reminder injected by hook]
Consult proactively, do not wait to be asked. Lookup order for anything substantive: wiki (~/.wiki/wiki) -> RAG (mcp__rag__search) -> codebase.
- Resuming or starting work: first search ~/.wiki/wiki/${domain}/sessions/ and RAG for the prior summary, so you load context instead of guessing.
- Finishing substantial work: write or update a summary in ~/.wiki/wiki/${domain}/sessions/ and offer it to the user.
- Knowledge goes in the wiki; memory files hold behaviour and pointers only.
EOF
