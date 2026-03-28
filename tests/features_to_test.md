# Features to test

## container-extras
- [ ] extras-build to pytest not bash
- [ ] apt.sh: installs packages, idempotent
- [ ] python.sh: installs python, creates python/python3 symlinks, idempotent
- [ ] python.sh: works with version arg and without
- [ ] python.sh: symlinks point to correct version when specified

## Containerfile.base
- [ ] builds clean from scratch
- [ ] claude is on PATH and runnable

## Containerfile.extras
- [ ] builds with empty run.sh (vanilla)
- [ ] builds with apt + python extras
- [ ] idempotent rebuild produces working image
