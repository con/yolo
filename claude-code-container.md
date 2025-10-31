# Running Claude Code in a Container

This guide shows how to run claude-code in a container (Docker or Podman) with full permissions while preserving your configuration and working directory access.

## Quick Start

First, build the image from the `ai/images/` directory:

```bash
# Docker
docker build -t claude-code ai/images/

# Podman
podman build -t claude-code ai/images/
```

Then run:

```bash
# Docker
docker run -it --rm \
  --privileged \
  -v ~/.claude:/home/node/.claude \
  -v "$(pwd):/workspace" \
  -w /workspace \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  claude-code

# Podman
podman run -it --rm \
  --privileged \
  -v ~/.claude:/home/node/.claude:Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  claude-code
```

> **Note**: Podman uses `:Z` flag for SELinux relabeling on systems that enforce SELinux.

## What's Included

The Dockerfile (based on [Anthropic's official setup](https://github.com/anthropics/claude-code/blob/main/.devcontainer/Dockerfile)) includes:

- **Claude Code CLI**: Latest version
- **Development tools**: git, gh (GitHub CLI), jq, vim, nano, zsh
- **Git enhancements**: delta (better diffs), fzf (fuzzy finder)
- **Network tools**: iptables, ipset, dnsutils
- **Firewall script**: Optional sandboxing for restricted network access

## Command Breakdown

- `--privileged`: Grants full permissions to the container (needed for some system operations)
- `-v ~/.claude:/home/node/.claude`: Bind mounts your Claude configuration directory
- `-v "$(pwd):/workspace"`: Bind mounts your current working directory into `/workspace`
- `-w /workspace`: Sets the working directory inside the container
- `-e ANTHROPIC_API_KEY`: Passes your API key to the container
- `--rm`: Automatically removes the container when it exits
- `-it`: Interactive terminal

## Security Considerations

⚠️ **Important**: `--privileged` gives the container full access to your host system. Only use this when:
- Running on your local development machine
- You trust the container image
- You need system-level operations (Docker-in-Docker, device access, etc.)

For less privileged access, consider specific capabilities instead:

```bash
# Docker
docker run -it --rm \
  --cap-add=SYS_PTRACE \
  --cap-add=NET_ADMIN \
  -v ~/.claude:/home/node/.claude \
  -v "$(pwd):/workspace" \
  -w /workspace \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  claude-code

# Podman
podman run -it --rm \
  --cap-add=SYS_PTRACE \
  --cap-add=NET_ADMIN \
  -v ~/.claude:/home/node/.claude:Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
  claude-code
```

## Alternative: Compose

Create a `docker-compose.yml` or `podman-compose.yml`:

```yaml
version: '3.8'
services:
  claude-code:
    build: ./ai/images
    privileged: true
    volumes:
      - ~/.claude:/home/node/.claude
      - .:/workspace
    working_dir: /workspace
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    stdin_open: true
    tty: true
```

Run with:
```bash
# Docker
docker-compose run --rm claude-code

# Podman
podman-compose run --rm claude-code
```

## Tips

1. **Persist configuration**: The `~/.claude` bind mount ensures your settings, API keys, and session history persist between container runs

2. **Git credentials**: If you need git operations, also mount your git config:
   ```bash
   -v ~/.gitconfig:/home/node/.gitconfig \
   -v ~/.ssh:/home/node/.ssh:ro
   ```

3. **Multiple directories**: Mount additional directories as needed:
   ```bash
   -v ~/projects:/projects \
   -v ~/data:/data
   ```

4. **Running as your user**: The image runs as the `node` user (UID 1000) by default. If you need different permissions, you can override:
   ```bash
   --user $(id -u):$(id -g)
   ```
