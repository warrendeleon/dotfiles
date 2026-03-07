Run a multi-pass audit on the specified files or the current changeset.

If the user specifies files, audit those. Otherwise, audit all modified files (`git diff --name-only`).

## Rules

1. **If a pass finds ANY bug, do another pass automatically.** Don't stop. Don't ask. Just keep going.
2. **The only valid stopping point is a completely clean pass that finds zero issues.**
3. **After a clean pass, keep going until you have 5 consecutive clean passes, each from a different angle.**
4. **Never declare confidence while bugs are still being found.** Finding bugs proves your previous confidence was wrong.
5. **Each pass must use a different review strategy.** Don't just re-read the same way each time.

## Pass strategies (use a different one each time)

1. **Line-by-line logic**: Read every line, verify correctness of each statement
2. **Data flow tracing**: Follow variables from input to output, check transformations
3. **Error path enumeration**: What happens when things fail? Missing error handling?
4. **Security/injection review**: Untrusted input, shell injection, prompt injection, XSS, SQL injection
5. **Concurrency analysis**: Race conditions, shared state, async ordering
6. **Boundary conditions**: Empty strings, NULL, zero, negative, MAX_INT, unicode, long strings
7. **Contract verification**: Do functions do what their name/docs say? Are return types correct?

## Process

1. Read all relevant source files thoroughly
2. Identify all bugs, edge cases, and security gaps
3. Fix all of them
4. Run tests, fix failures, re-run until 100% pass
5. Run all previous test suites for regression
6. Re-read all code using a different review strategy than previous passes
7. If step 6 found anything, go to step 2
8. Only stop after 5 consecutive clean passes with different strategies

## Output format

For each pass, report:
```
Pass N (strategy: [name])
- Found: X issues
- [List each issue with file:line and description]
- Status: CLEAN / ISSUES FOUND → continuing
```

Final summary:
```
Audit complete: 5 consecutive clean passes
Strategies used: [list all]
Total issues found and fixed: N
```
