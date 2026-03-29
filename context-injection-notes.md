# Should we tell the AI it's in a yolo container?

Yes. Strong yes. Here's why and what to include.

## Why context helps

An AI working blind inside a container will:

1. **Waste turns discovering its environment.** It'll run `which python`,
   check for tools, probe what's mounted — all things we already know at
   launch time.

2. **Hallucinate capabilities it doesn't have.** Without knowing its
   boundaries, it'll try to `ssh` somewhere, access credentials that
   aren't mounted, or install packages without knowing what's already
   available.

3. **Miss capabilities it does have.** If we installed datalad, delta,
   fzf, or Python 3.12 via container-extras, Claude won't know to use
   them unless told. The whole point of extras is to give the agent
   better tools — but only if it knows they're there.

4. **Misunderstand file boundaries.** It needs to know what's a bind
   mount (persistent, shared with host) vs container filesystem
   (ephemeral, dies on exit). Writing important output to `/tmp` inside
   the container is a silent data loss bug.

## What to include

### Environment awareness
- "You are running inside a yolo container (rootless Podman)"
- Container is ephemeral — filesystem outside of mounts is lost on exit
- No network restrictions (unless configured)
- Running as your host UID (rootless, userns=keep-id)

### Installed tools (from container-extras)
- List exactly what was installed: "Available tools: python 3.12,
  git-delta 0.18.2, fzf, gh, shellcheck, zsh, ..."
- This is generated at launch from the resolved config — always accurate

### Mount map
- Which directories are bind-mounted and where
- Which are read-only vs read-write
- "Your work directory is mounted at /workspace" (or wherever)
- "Changes outside mounted volumes are lost when the container exits"

### Boundaries (what you can't do)
- No SSH keys (unless explicitly mounted)
- No access to host services (Docker socket, DBus, etc.)
- Can't persist data outside mounted volumes
- `.yolo/` directory is read-only inside the container (if we do that)

### Operational guidance
- "Save all important output within mounted volumes"
- "You can install additional packages with apt, but they won't persist"
- "To add persistent tools, tell the user to add them to container-extras"

## How to deliver it

**CLAUDE.md in the container.** Claude Code already reads CLAUDE.md files.
Generate one at launch time and place it at the workspace root (or
`/etc/yolo/CLAUDE.md` to avoid clobbering a project's own CLAUDE.md).

Options:
1. **Workspace CLAUDE.md** — simple, but conflicts if the project has one
2. **`~/.claude/CLAUDE.md` inside the container** — user-level, no conflict
3. **Append to existing** — fragile, modifies user files
4. **`/etc/yolo/context.md` + symlink** — clean separation

Option 2 seems cleanest: the container's `~/.claude/CLAUDE.md` is
generated fresh each launch, contains the yolo context, and doesn't
touch the project's CLAUDE.md.

## What this looks like in practice

Generated at launch, something like:

```markdown
# Container Environment (yolo)

You are running inside a yolo container — an isolated, ephemeral
Podman container for safe autonomous coding.

## Installed tools
- Python 3.12 (system)
- git-delta 0.18.2
- apt packages: fzf, gh, less, man-db, shellcheck, zsh

## Mounted volumes
- /home/user/projects/myrepo → /workspace (read-write)
- /home/user/data → /data (read-only)

## Important
- The container filesystem is ephemeral. Only files in mounted
  volumes persist after exit.
- No SSH keys or host credentials are available.
- To add persistent tools, ask the user to add container-extras
  to .yolo/config.yaml and rebuild.
```

## Edge: should we tell it about security constraints?

Debatable. Telling Claude "you can't access SSH keys" is informational
and helps it avoid wasting turns. But explicitly listing security
boundaries could also be read as a challenge or a map of what to probe.

Pragmatic take: state what's available, not what's restricted. "Here are
your tools and mounts" naturally implies everything else is absent.
Don't enumerate attack surface.
