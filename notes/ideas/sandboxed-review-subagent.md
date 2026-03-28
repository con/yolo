# Sandboxed review subagent

A skill/hook that launches a yolo container (read-only) as a subagent:
1. Mount working tree read-only
2. Claude inside reviews the diff, runs tests, checks logs
3. Container exits with structured output
4. Calling Claude gets a summary: test failures, code concerns, log issues

Like a local CI loop / PR review that runs before you push, in a
sandbox where the reviewer can't modify your code.
