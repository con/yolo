# Running Claude Code in a Container

This guide shows how to run claude-code in a Podman container with full permissions while preserving your configuration and working directory access.

## Quick Start

First, build the image from the `ai/images/` directory:

```bash
podman build --build-arg TZ=$(timedatectl show --property=Timezone --value) -t claude-code ai/images/
```

Then run:

```bash
podman run -it --rm \
  --privileged \
  --user $(id -u):$(id -g) \
  -v ~/.claude:/home/node/.claude:Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  -e HOME=/home/node \
  claude-code
```

> **Note**: The `:Z` flag handles SELinux relabeling. The `--user` flag ensures files created in mounted volumes are owned by you on the host.

## What's Included

The Dockerfile (based on [Anthropic's official setup](https://github.com/anthropics/claude-code/blob/main/.devcontainer/Dockerfile)) includes:

- **Claude Code CLI**: Latest version
- **Development tools**: git, gh (GitHub CLI), jq, vim, nano, zsh
- **Git enhancements**: delta (better diffs), fzf (fuzzy finder)
- **Network tools**: iptables, ipset, dnsutils
- **Firewall script**: Optional sandboxing for restricted network access

## Command Breakdown

- `--privileged`: Grants full permissions to the container (needed for some system operations)
- `--user $(id -u):$(id -g)`: Run as your host user to avoid permission issues
- `-v ~/.claude:/home/node/.claude:Z`: Bind mounts your Claude configuration directory with SELinux relabeling
- `-v "$(pwd):/workspace:Z"`: Bind mounts your current working directory into `/workspace`
- `-w /workspace`: Sets the working directory inside the container
- `-e HOME=/home/node`: Sets HOME so Claude Code finds its config
- `-e ANTHROPIC_API_KEY`: Passes your API key to the container
- `--rm`: Automatically removes the container when it exits
- `-it`: Interactive terminal

## Security Considerations

⚠️ **Important**: `--privileged` gives the container full access to your host system. Only use this when:
- Running on your local development machine
- You trust the container image
- You need system-level operations (device access, etc.)

For less privileged access, consider specific capabilities instead:

```bash
podman run -it --rm \
  --cap-add=SYS_PTRACE \
  --cap-add=NET_ADMIN \
  --user $(id -u):$(id -g) \
  -v ~/.claude:/home/node/.claude:Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e HOME=/home/node \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  claude-code
```

## Tips

1. **Persist configuration**: The `~/.claude` bind mount ensures your settings, API keys, and session history persist between container runs

2. **Git credentials**: If you need git operations, also mount your git config:
   ```bash
   -v ~/.gitconfig:/home/node/.gitconfig:Z \
   -v ~/.ssh:/home/node/.ssh:ro,Z
   ```

3. **Multiple directories**: Mount additional directories as needed:
   ```bash
   -v ~/projects:/projects:Z \
   -v ~/data:/data:Z
   ```

4. **File ownership**: By running with `--user $(id -u):$(id -g)`, files created or modified inside the container will be owned by your host user
