Systematically diagnose a bug or failure. Never guess. Never try random fixes.

The user will describe the problem, or provide an error message/failing test. If not, ask what's failing.

## Process

### 1. Capture the error
- Get the full error output (stderr, stack trace, exit code)
- Note the exact command or action that triggered it
- Note when it started (did it work before? what changed?)

### 2. Read the error message
- Actually read it. The answer is often right there.
- Identify the file, line number, and function mentioned
- Classify: syntax error, type error, runtime error, network error, permission error, config error

### 3. Reproduce
- Can you trigger the same error consistently?
- What's the minimal reproduction case?
- Does it happen in all environments or just one?

### 4. Trace the data flow
- Start from the error location and work backwards
- What value was unexpected? Where did it come from?
- Follow the chain: input → transformation → output
- Check each step: is the data what you expect at every point?

### 5. Form a hypothesis
- Based on the trace, what's the most likely cause?
- State it clearly: "The error occurs because X passes Y to Z, but Z expects W"
- Don't fix yet. Verify the hypothesis first.

### 6. Verify the hypothesis
- Add logging, read the source, check the docs
- Confirm that your explanation matches all the symptoms
- If it doesn't match, go back to step 4. Don't force it.

### 7. Fix with understanding
- Only now write the fix
- The fix should directly address the root cause
- You should be able to explain WHY this fix works, not just that it works

### 8. Verify the fix
- Run the failing test/command again
- Run related tests to check for regressions
- Confirm the original error is gone, not just masked

## Red flags (you're guessing, not debugging)
- "Let me try changing this..." without knowing why
- Trying multiple fixes in quick succession
- The fix works but you can't explain why
- Reverting to a previous version instead of understanding the issue
- Adding try/catch or error suppression around the problem

## Output format
```
Error: [the actual error message]
Location: [file:line]
Root cause: [clear explanation of WHY it fails]
Fix: [what to change and WHY it fixes the root cause]
Verification: [what test/command proves it's fixed]
```
