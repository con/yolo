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
  --userns=keep-id \
  -v ~/.claude:/home/node/.claude:Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e HOME=/home/node \
  claude-code
```

## First-Time Login

On your first run, you'll need to authenticate:

1. Claude Code will display a URL like `https://claude.ai/oauth/authorize?...`
2. Copy the URL and paste it into a browser on your host machine
3. Complete the authentication in your browser
4. Copy the code from the browser and paste it back into the container terminal

Your credentials are stored in `~/.claude` on your host, so you only need to login once. Subsequent runs will use the stored credentials automatically.

## What's Included

The Dockerfile (based on [Anthropic's official setup](https://github.com/anthropics/claude-code/blob/main/.devcontainer/Dockerfile)) includes:

- **Claude Code CLI**: Latest version
- **Development tools**: git, gh (GitHub CLI), jq, vim, nano, zsh
- **Git enhancements**: delta (better diffs), fzf (fuzzy finder)
- **Network tools**: iptables, ipset, dnsutils
- **Firewall script**: Optional sandboxing for restricted network access

## Command Breakdown

- `--userns=keep-id`: Maps your host user ID inside the container so files are owned correctly
- `-v ~/.claude:/home/node/.claude:Z`: Bind mounts your Claude configuration directory with SELinux relabeling
- `-v "$(pwd):/workspace:Z"`: Bind mounts your current working directory into `/workspace`
- `-w /workspace`: Sets the working directory inside the container
- `-e HOME=/home/node`: Sets HOME so Claude Code finds its config
- `--rm`: Automatically removes the container when it exits
- `-it`: Interactive terminal

## Tips

1. **Persist configuration**: The `~/.claude` bind mount ensures your settings, API keys, and session history persist between container runs

2. **File ownership**: The `--userns=keep-id` flag ensures files created or modified inside the container will be owned by your host user, regardless of your UID

3. **Git credentials**: If you need git operations, also mount your git config:
   ```bash
   -v ~/.gitconfig:/home/node/.gitconfig:Z \
   -v ~/.ssh:/home/node/.ssh:ro,Z
   ```

4. **Multiple directories**: Mount additional directories as needed:
   ```bash
   -v ~/projects:/projects:Z \
   -v ~/data:/data:Z
   ```
