https://github.com/con/yolo/issues/47

# Config and Arbitrary Development Environments

This isn't a firm proposal — just consolidating the discussions we've had across several issues and PRs, along with some of my thinking on where this could go. Opening this to get everyone's input in one place and encourage more!

**Next steps:**
1. Discuss here — poke holes, raise concerns, add ideas
2. Generally agree on the shape of the approach
3. Write a design document (PR) for sharper, per-line discussion

## Context

yolo needs to create arbitrary, persistent development environments for each project.
Today, every time someone needs a tool in the image, we hit the same debate: add it to the Dockerfile? Make it an `--extras` flag? A separate image?

This has come up repeatedly:
- PR #28: playwright added ~600MB, prompting "should be a separate image"
- PR #31: `--packages`/`--extras` added to setup-yolo.sh, with discussion of multiple images and runtime image selection
- PR #43: `--image` with derived Dockerfiles rejected for combinatorial explosion, landed as `--extras=datalad,jj`
- #39: newer git needed — another "what goes in the base image" question
- #33: singularity/apptainer — different container runtime entirely

The `--extras` pattern was a good stopgap, but we can't encode install instructions for every tool every user might want. Meanwhile, yolo is fully capable of constructing environments ephemerally, but ephemeral environments aren't ideal for development — they need to be reconstructed every time.

### Target audience

Our primary users are scientists, not software engineers.
Most will never write a Dockerfile and shouldn't have to.
Whatever we design, the common case needs to be as simple as adding a package name to a config file.

## Discussion: How should environment customization work?

Some directions that have come up in prior discussions, consolidated here.

### Pre-built base images

Publish a base image to a registry so yolo works out of the box with no build step.
What goes in the base? Just the minimum, or opinionated with group tools like datalad?

### Config-driven packages

Let users list packages in config files (apt, pip, etc.) without writing a Dockerfile:

```
# in .git/yolo/config or ~/.config/yolo/config
YOLO_APT_PACKAGES=(ffmpeg imagemagick)
YOLO_PIP_PACKAGES=(datalad)
```

This could be the primary customization path for most users — a scientist who needs `ffmpeg` just adds it to their project config.

### Custom Dockerfiles for power users

For anything that needs custom install steps, users could provide their own Dockerfile (using our base as `FROM` or not).
This would live outside our repo.

### yolo as the single entrypoint

Currently `setup-yolo.sh` handles building and `yolo` handles running.
Should yolo handle both — pulling/building images as needed? With a base image in a registry, this would mean yolo works immediately after install.

### Config precedence

Build-time config (image name, packages, Dockerfile path, registry) could follow the same precedence as existing runtime config:

**CLI args > project config > user-wide config > defaults**

### Build behavior

Build on first run if image doesn't exist.
`--rebuild` to force.
Auto-detection of config changes could come later.

## Alternative approaches

### Two layers only: base image + custom Dockerfile

This is what Gitpod and Codespaces do — provide a base image, let users write a Dockerfile for customization. Simpler to implement and reason about. However, the gap between "use the base" and "write a Dockerfile" is too wide for our audience. A scientist who just needs `ffmpeg` shouldn't have to learn Docker to get it.
We're leaning away from this toward a config-driven middle path because that's where most of our potential users would actually be comfortable.

### Other prior art

- **devcontainer features** — composable install scripts with metadata. Well-specified but heavyweight; requires authoring feature scripts with a specific structure.
- **Nix / devenv** — declarative, reproducible. Elegant but steep learning curve.
- **Docker official image variants** — tag-based (`python:3.12-slim`). No composition, just pick one.

## Open questions

- **CLI rewrite?** Bash is hitting its limits for config parsing, registry logic, and the complexity ahead. Python? How much rewrite vs. incremental?
- **Registry?** GHCR, Docker Hub, Quay, multiple?
- **Base image contents?** Minimal vs. opinionated?
- **Alternative runtimes** (#33) — Singularity/Apptainer is a related concern; good architecture now would make it easier later.

## Related

- #42 — Extract a SPEC.md
- #33 — Singularity/Apptainer support
- #39 — Need newer git in the environment
- #46 — HOME mismatch between host and container
- PR #28, #31, #43 — Prior discussions on image customization

## Comments

### just-meng (2026-03-12T17:17:31Z)

I totally agree with the your point of providing something more flexible than `--extras` and much simpler than a Dockerfile. On the technical level, I have nothing to contribute, but happy to report "user experiences" once there is a concrete design/solution.

### yarikoptic (2026-03-13T01:01:15Z)

on a tangential topic -- I discovered that there is a built in feature for isolation in 'claude code' , https://code.claude.com/docs/en/sandboxing , so I am yet to review/compare the two . Might even just switch away from yolo at some point

### asmacdo (2026-03-13T08:36:27Z)

@yarikoptic that discussion: https://github.com/con/yolo/issues/49
