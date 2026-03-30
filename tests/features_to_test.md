# Features to test

## container-extras (done)
- [x] apt.sh: installs packages, verify mode
- [x] python.sh: installs python, creates symlinks, verify mode
- [x] git-delta.sh: installs delta, verify mode
- [x] all scripts: idempotent

## Containerfile.base (done)
- [x] builds clean from scratch
- [x] claude is on PATH and runnable

## Integration TODO
- [ ] yo build → yo run --entrypoint bash -c "python --version"
- [ ] volumes actually mount (write on host, read in container)
- [ ] env vars arrive inside container
- [ ] image tagged correctly in podman images
- [ ] claude --help exits 0 inside image
- [ ] --no-config changes build behavior
- [ ] worktree detection in real git worktree
