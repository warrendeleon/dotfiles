Systematically diagnose a bug or failure. Never guess. Never try random fixes.

The user will describe the problem, or provide an error message/failing test. If not, ask what's failing.

## What done looks like

The full error and the command that triggered it are captured, the failure reproduces, and the root cause is stated as one sentence that explains every symptom ("X passes Y to Z, but Z expects W"). Write the fix only once that sentence is confirmed by logging, the source or the docs. Then the failing command passes, related tests still pass, and the original error is gone rather than masked.

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
