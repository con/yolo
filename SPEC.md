# YOLO Redesign Hackpad

Working design notes from brainstorming session 2026-03-28.
This is a living document — ideas, not commitments.
Locked decisions live in `HACK_DECISIONS.md`.

## Core problem

The current architecture has no extension points. Every new capability —
a tool in the image, a worktree strategy, a container runtime — requires
modifying the core. This is unsustainable.

The `--extras` pattern is the proof: every new tool is a PR to the
Dockerfile, a flag in `setup-yolo.sh`, a debate about what belongs in the
base image. The architecture forces everything through the center.

**The goal is an architecture where the core is small and stable, and
growth happens at the edges.** Adding datalad support, a new worktree
strategy, or singularity as a runtime should not require touching the core.

## What is yolo?

Two core components, plus an installer:

1. **Launcher** — assemble mounts/env/command, invoke the container runtime
2. **Environment builder** — resolve features, build a derived image
3. **Installer** (`setup-yolo.sh` successor) — deferred for now

These are decoupled. The launcher doesn't know how the image was built.
The builder doesn't know how the image will be run.

## User stories

**"I just want to run it"**
Scientist clones a repo, types `yolo`, it works. No build step, no config
editing, no container knowledge required.

**"I need datalad too"**
Scientist adds `datalad` to a list in project config. A pre-written install
script runs behind the scenes. They didn't need to know what that script does.

**"I do worktrees differently"**
Yarik has opinions about worktree layout. He drops a script into a known
location that overrides the default worktree behavior. No fork needed.

**"Here's a repo, it just works"**
A PI commits yolo config to a repo. Collaborators clone it, run `yolo`, and
the environment is ready — right features, right mounts, right setup.

---

## Features (environment builder)

Composable install units. Users compose by name, yolo resolves and runs them.

### Syntax (YAML config)

```yaml
features:
  - datalad          # finds install_datalad.sh in feature path → runs it
  - ffmpeg           # no script found → falls back to apt
  - apt:imagemagick  # explicit: apt-get install
  - uv:con-duct      # explicit: uv tool install
  - pip:numpy        # explicit: pip install
```

### Resolution for bare names

1. Search the feature path for `install_<name>.sh` → run it if found
2. No script? → `apt-get install -y <name>`

Prefixed names (`apt:`, `uv:`, `pip:`) skip the search, go straight to the
package manager script with args.

Curated scripts only need to exist where the install is non-trivial (datalad
needs extra `--with` flags, CUDA needs apt sources modified, playwright needs
both system deps and npm).

### Feature path (resolution order)

```
<con-yolo package>/features/ ← ships with yolo (builtins)
~/.config/yolo/features/     ← user local
.yolo/features/              ← project (committed)
.git/yolo/features/          ← project (local/untracked)
```

Later wins if names collide.

### Build mechanism

Static Dockerfiles, dynamic build context. No Dockerfile generation.

- `Dockerfile.base` — the base image (Claude Code + core tools)
- `Dockerfile.custom` — layers features on top of base

`Dockerfile.custom` is dumb — it copies in a build context and runs
a manifest script. yolo assembles the build context:

```
build/
  scripts/
    install_datalad.sh    ← resolved from feature path
    apt.sh                ← builtin package manager script
    uv.sh                 ← builtin package manager script
  run.sh                  ← generated manifest
```

`run.sh` is just:
```bash
bash /tmp/yolo-build/scripts/install_datalad.sh
bash /tmp/yolo-build/scripts/apt.sh imagemagick visidata
bash /tmp/yolo-build/scripts/uv.sh con-duct
```

Package manager scripts are simple. `apt.sh` is literally:
```bash
apt-get install -y "$@"
```

`apt-get update` happens once in the Dockerfile before running scripts,
not in each script.

### Build-time vs run-time

- **Primary: build-time.** Features baked into the derived image.
- **Secondary: run-time.** For things like `pip install -e .` that are
  inherently per-session. Configured separately (e.g. `startup` key).
- **Explicit rebuild.** No auto-detection of staleness. User runs
  `yolo --rebuild` when they change features.

### OPEN: Sharp edges

- What if a bare name matches a script AND is a valid apt package?
  (Script wins — is that always right?)
- Is the prefix syntax extensible enough? (`npm:`, `cargo:`, etc.)
- Error messages when an install fails — which script broke?

---

## Hooks / extensible launch behavior

Same resolution pattern as features, same override mechanism.
A hook is just a script in a known location that runs at a specific phase.

### Unified with features via phases

```
.yolo/
  build/              ← feature install scripts (build phase)
  launch/             ← runtime behavior scripts (launch phase)
  config.yaml         ← the thing users actually edit
```

No separate "hook framework." If a script with a known name exists,
it runs at the right phase. The phase is implied by location.

### Hook points (launch phase)

| Hook            | What it does by default        | Why someone might override        |
|-----------------|--------------------------------|-----------------------------------|
| `worktree`      | detect, prompt/bind/skip/error | custom worktree layout/naming     |
| `volumes`       | assemble the mount list        | SSH keys, conditional mounts      |
| `container-name`| `$PWD-$$` sanitized            | org naming conventions            |
| `pre-launch`    | nothing                        | env setup, credential injection   |
| `post-exit`     | nothing                        | cleanup, sync, notifications      |
| `entrypoint`    | `claude --dangerously-skip-permissions` | different agent, wrapper |

### OPEN: Hook contract

- Override vs wrap? Does a user hook replace the default or run around it?
- Data return: how does a hook communicate back (e.g. "add these mounts")?
- We want to stay on the simple side of: `exit code → stdout → JSON → plugin API`

---

## Launcher

The launcher speaks in **intent**, not container runtime flags.

### Vocabulary (YAML config keys)

```yaml
volumes:
  - ~/projects
  - ~/data::ro

nvidia: true
worktree: ask
```

NOT raw podman flags. Intent is portable across runtimes.

The launcher's job:
1. **Mounts** — default secure set + user additions from config
2. **Env vars** — default set + user additions
3. **Command** — claude with skip-permissions, or custom entrypoint
4. **Translate** — turn intent into `podman run` invocation

Raw passthrough (`--`) exists as an escape hatch, not the normal path.

---

## Config

See `HACK_DECISIONS.md` for locked decisions on format and locations.

### Layering (later overrides earlier)

1. `/etc/yolo/config.yaml` — system-wide (org defaults)
2. `~/.config/yolo/config.yaml` — user preferences
3. `.yolo/config.yaml` — project, committed (shareable)
4. `.git/yolo/config.yaml` — project, local (personal)
5. CLI args

### OPEN: Array merging vs replacement

With 4 config layers, does `volumes: [~/data]` in project config
replace or append to `volumes: [~/tools]` in user config?

---

## Context injection

yolo generates a context file bound into the container at launch,
telling Claude about its environment:

- "You're in a yolo container"
- "Mounted volumes: X, Y, Z"
- "You cannot: access SSH keys, write outside mounted volumes"
- "Installed features: datalad, ffmpeg"

Helps Claude work effectively AND respects boundaries.

---

## Security

### Posture

Secure by default. Flexible enough to weaken deliberately.

### Escape vector: config as attack surface

Claude has write access to `.yolo/config.yaml` (in the workspace).
Could modify config to mount sensitive directories on next launch.
Between-session escape, not within-session.

Mitigations under consideration:
- Mount `.yolo/` read-only inside container
- Diff-on-launch: show config changes, ask to confirm
- Exit warning if `.yolo/` was modified during session
- Trust prompt for committed config in unfamiliar repos
- Document honestly, don't pretend it's fully solved

---

## Still open

- Image naming/tagging strategy for derived images
- Singularity/apptainer runtime abstraction (#33)
- Registry story (GHCR for base image?) — deferred, build locally for now
- How extensions repo works (if at all)
- Installer redesign (setup-yolo.sh successor) — deferred
- Organize security-reports/ (generated by yolo session test run)
- `!replace` YAML tag for per-key merge vs replace semantics
- Default container-extras config (ships with package)
