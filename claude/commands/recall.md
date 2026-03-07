Search past conversation transcripts to find previous discussions, decisions, or context.

When the user says "we talked about X", "remember when we did Y", "I mentioned Z before", or similar, find the relevant conversation.

## Process

### 1. Semantic search first (RAG)

Use the RAG MCP tools to search indexed conversations:

```
mcp__rag__search(query="<search terms>", scope="conversations")
```

If results are relevant, summarise what was found and stop. If no results or insufficient, continue to step 2.

### 2. Broader RAG search

Widen the search to all collections:

```
mcp__rag__search(query="<search terms>")
```

Check code and docs too: the context might be in a commit message, planning doc, or code comment.

### 3. Grep fallback

If RAG returns nothing useful (index might be incomplete), fall back to direct grep:

```bash
# Search all conversations for a topic
grep -ril "search term" ~/.claude/projects/ --include="*.jsonl" | head -20

# Get context around matches
grep -i "search term" ~/.claude/projects/**/*.jsonl | head -50
```

For matches, extract relevant context:
```bash
grep -i -B 2 -A 5 "search term" <matched_file>
```

### 4. Summarise

Report what was found: when it was discussed, what was decided, and any relevant context. Include the session ID or file path for reference.

## Tips
- Search broadly first, then narrow down. The user might not remember exact wording.
- Try multiple search terms if the first doesn't find results.
- RAG results include a relevance percentage: anything above 60% is usually a good match.
- If RAG is unavailable (server not running), grep still works fine.

## When to use proactively
- User says "we discussed", "we talked about", "remember when", "as I mentioned", "like before", "last time"
- User references a past decision without explaining it
- User expects you to know something from a previous session
