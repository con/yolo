# Issue #51: EACCES crash when running multiple yolo instances

## Problem
Running two yolo containers simultaneously causes the first one to crash with:
```
EACCES: permission denied, open '/home/austin/.claude/.claude.json'
```

## Root Cause
All volume mounts in yolo used `:Z` (uppercase) SELinux label, which means
"private unshared label". When a second container mounts the same `~/.claude`
directory with `:Z`, the container runtime relabels the files for container #2,
revoking access from container #1. Container #1 then gets EACCES.

This explains why two native Claude Code sessions work fine (no SELinux
relabeling) but two yolo containers don't.

## Fix Applied
Changed `CLAUDE_MOUNT` lines (417 and 423 in bin/yolo) from `:Z` to `:z`
(lowercase = shared label, allows multiple containers to access simultaneously).

Only the `~/.claude` mount was changed. Other mounts (workspace, worktree) still
use `:Z` since those are typically not shared between concurrent containers.

## Status
- Fix applied, needs testing: run two yolo sessions simultaneously and confirm
  the first no longer crashes.
- If it works, commit and reference issue #51.
