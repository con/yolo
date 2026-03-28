1. --global-claude doesnt seem like the right name to me (--anonymized-paths)
2. bin/yolo:16 - argument parsing bug: `[ "${arg:0:2}" = "--" ]` matches any long option (--rm, --env, etc.) not just the separator `--`. Should be exact match: `[ "$arg" = "--" ]`
3. README.md - manual examples use `~/.claude:~/.claude:Z` but bash only expands first tilde, not the one after colon. Should use `$HOME/.claude:$HOME/.claude:Z` or fully expanded paths

TODOs later (not part of this PR/review)
1. add shellcheck to CI (lets do in separate PR/branch)
1. add some sanity tests (hard to do without user to authenticate though)

