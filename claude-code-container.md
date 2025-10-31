# Running Claude Code in a Container

This guide shows how to run claude-code in a Podman container while preserving your configuration and working directory access.

## Easy Setup (Recommended)

Clone the repository and run the setup script to build the container and optionally create a `YOLO` command:

```bash
git clone https://github.com/con/catenate.git
cd catenate
./ai/setup-yolo.sh
```

This will:
1. Build the container image if it doesn't exist
2. Optionally create a `YOLO` shell function
3. Configure everything for you

After setup, just run `YOLO` from any directory to start Claude Code in YOLO mode!

> **TODO**: Add curl-based one-liner setup once this PR is merged

## First-Time Login

On your first run, you'll need to authenticate:

1. Claude Code will display a URL like `https://claude.ai/oauth/authorize?...`
2. Copy the URL and paste it into a browser on your host machine
3. Complete the authentication in your browser
4. Copy the code from the browser and paste it back into the container terminal

Your credentials are stored in `~/.claude` on your host, so you only need to login once. Subsequent runs will use the stored credentials automatically.

## Manual Setup

If you prefer to run commands manually, first build the image from the `ai/images/` directory:

```bash
podman build --build-arg TZ=$(timedatectl show --property=Timezone --value) -t claude-code ai/images/
```

Then run:

```bash
podman run -it --rm \
  --userns=keep-id \
  -v ~/.claude:/claude:Z \
  -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e CLAUDE_CONFIG_DIR=/claude \
  -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
  claude-code \
  claude --dangerously-skip-permissions
```

⚠️ **Note**: This uses `--dangerously-skip-permissions` to bypass all permission prompts. This is safe in containerized environments where the container provides isolation from your host system.

## What's Included

The Dockerfile (based on [Anthropic's official setup](https://github.com/anthropics/claude-code/blob/07e13937b2d6e798ce1880b22ad6bd22115478e4/.devcontainer/Dockerfile)) includes:

- **Claude Code CLI**: Latest version
- **Development tools**: git, gh (GitHub CLI), jq, vim, nano, zsh
- **Git enhancements**: delta (better diffs), fzf (fuzzy finder)
- **Network tools**: iptables, ipset, dnsutils for container networking

## Command Breakdown

- `--userns=keep-id`: Maps your host user ID inside the container so files are owned correctly
- `-v ~/.claude:/claude:Z`: Bind mounts your Claude configuration directory with SELinux relabeling
- `-v ~/.gitconfig:/tmp/.gitconfig:ro,Z`: Mounts git config read-only for commits (push operations not supported)
- `-v "$(pwd):/workspace:Z"`: Bind mounts your current working directory into `/workspace`
- `-w /workspace`: Sets the working directory inside the container
- `-e CLAUDE_CONFIG_DIR=/claude`: Tells Claude Code where to find its configuration
- `-e GIT_CONFIG_GLOBAL=/tmp/.gitconfig`: Points git to the mounted config
- `claude --dangerously-skip-permissions`: Skips all permission prompts (safe in containers)
- `--rm`: Automatically removes the container when it exits
- `-it`: Interactive terminal

## Tips

1. **Persist configuration**: The `~/.claude` bind mount ensures your settings, API keys, and session history persist between container runs

2. **File ownership**: The `--userns=keep-id` flag ensures files created or modified inside the container will be owned by your host user, regardless of your UID

3. **Git operations**: Git config is mounted read-only, so Claude Code can read your identity and make commits. However, **SSH keys are not mounted**, so `git push` operations will fail. You'll need to push from your host after Claude Code commits your changes.

4. **Multiple directories**: Mount additional directories as needed:
   ```bash
   -v ~/projects:/projects:Z \
   -v ~/data:/data:Z
   ```
