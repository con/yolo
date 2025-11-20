# Running Claude Code in a Container

This guide shows how to run claude-code in a Podman container while preserving your configuration and working directory access.

## Easy Setup (Recommended)

Clone the repository and run the setup script to build the container and optionally create a `YOLO` command:

```bash
git clone https://github.com/con/yolo
cd yolo
./setup-yolo.sh
```

This will:
1. Build the container image if it doesn't exist
2. Optionally create a `YOLO` shell function
3. Configure everything for you

After setup, just run `yolo` from any directory to start Claude Code in YOLO mode!

By default, `yolo` preserves your original host paths to ensure session compatibility with native Claude Code. This means:
- Your `~/.claude` directory is mounted at its original path
- Your current directory is mounted at its original path (not `/workspace`)
- Sessions created in the container can be resumed in your native environment and vice versa

If you prefer the old behavior with anonymized paths (`/claude` and `/workspace`), use the `--anonymized-paths` flag:
```bash
yolo --anonymized-paths
```

> **TODO**: Add curl-based one-liner setup once this PR is merged

## First-Time Login

On your first run, you'll need to authenticate:

1. Claude Code will display a URL like `https://claude.ai/oauth/authorize?...`
2. Copy the URL and paste it into a browser on your host machine
3. Complete the authentication in your browser
4. Copy the code from the browser and paste it back into the container terminal

Your credentials are stored in `~/.claude` on your host, so you only need to login once. Subsequent runs will use the stored credentials automatically.

## Manual Setup

If you prefer to run commands manually, first build the image from the `images/` directory:

```bash
podman build --build-arg TZ=$(timedatectl show --property=Timezone --value) -t con-bomination-claude-code images/
```

Then run (with original host paths preserved by default):

```bash
podman run -it --rm \
  --userns=keep-id \
  -v "$HOME/.claude:$HOME/.claude:Z" \
  -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \
  -v "$(pwd):$(pwd):Z" \
  -w "$(pwd)" \
  -e CLAUDE_CONFIG_DIR="$HOME/.claude" \
  -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
  con-bomination-claude-code \
  claude --dangerously-skip-permissions
```

Or with anonymized paths (old behavior):

```bash
podman run -it --rm \
  --userns=keep-id \
  -v ~/.claude:/claude:Z \
  -v ~/.gitconfig:/tmp/.gitconfig:ro,Z \
  -v "$(pwd):/workspace:Z" \
  -w /workspace \
  -e CLAUDE_CONFIG_DIR=/claude \
  -e GIT_CONFIG_GLOBAL=/tmp/.gitconfig \
  con-bomination-claude-code \
  claude --dangerously-skip-permissions
```

⚠️ **Note**: This uses `--dangerously-skip-permissions` to bypass all permission prompts. This is safe in containerized environments where the container provides isolation from your host system.

## What's Included

The Dockerfile is based on [Anthropic's official setup](https://github.com/anthropics/claude-code/blob/07e13937b2d6e798ce1880b22ad6bd22115478e4/.devcontainer/Dockerfile) and includes Claude Code CLI plus common development tools. See the Dockerfile for the complete list.

## Command Breakdown

### Default Behavior (Preserved Host Paths)

- `--userns=keep-id`: Maps your host user ID inside the container so files are owned correctly
- `-v "$HOME/.claude:$HOME/.claude:Z"`: Bind mounts your Claude configuration directory at its original path with SELinux relabeling
- `-v ~/.gitconfig:/tmp/.gitconfig:ro,Z`: Mounts git config read-only for commits (push operations not supported)
- `-v "$(pwd):$(pwd):Z"`: Bind mounts your current working directory at its original path
- `-w "$(pwd)"`: Sets the working directory inside the container to match your host path
- `-e CLAUDE_CONFIG_DIR="$HOME/.claude"`: Tells Claude Code where to find its configuration (at original path)
- `-e GIT_CONFIG_GLOBAL=/tmp/.gitconfig`: Points git to the mounted config
- `claude --dangerously-skip-permissions`: Skips all permission prompts (safe in containers)
- `--rm`: Automatically removes the container when it exits
- `-it`: Interactive terminal

This default behavior ensures that session histories and project paths are compatible between containerized and native Claude Code environments.

### Anonymized Paths (Old Behavior with --anonymized-paths)

When using `--anonymized-paths`, paths are mapped to generic container locations:
- `-v ~/.claude:/claude:Z`: Mounts to `/claude` in container
- `-v "$(pwd):/workspace:Z"`: Mounts to `/workspace` in container
- `-w /workspace`: Working directory is `/workspace`
- `-e CLAUDE_CONFIG_DIR=/claude`: Config directory is `/claude`

## Tips

1. **Persist configuration**: The `~/.claude` bind mount ensures your settings, API keys, and session history persist between container runs

2. **Session compatibility**: By default, paths are preserved to match your host environment. This means:
   - Sessions created in the container can be resumed outside the container using `claude --continue` in your native environment
   - Each project maintains its own session history based on its actual path (e.g., `/home/user/project`)
   - You can seamlessly switch between containerized and native Claude Code for the same project

   **Note**: With `--anonymized-paths`, all projects appear to be in `/workspace`, which allows `claude --continue` to retain context across different projects that were also run with this flag. This can be useful for maintaining conversation context when working on related codebases.

3. **File ownership**: The `--userns=keep-id` flag ensures files created or modified inside the container will be owned by your host user, regardless of your UID

4. **Git operations**: Git config is mounted read-only, so Claude Code can read your identity and make commits. However, **SSH keys are not mounted**, so `git push` operations will fail. You'll need to push from your host after Claude Code commits your changes.

5. **Multiple directories**: Mount additional directories as needed:
   ```bash
   yolo -v ~/projects:~/projects -v ~/data:~/data -- "help with this code"
   ```
   Or with anonymized paths:
   ```bash
   yolo --anonymized-paths -v ~/projects:/projects -v ~/data:/data -- "help with this code"
   ```

## Security Considerations

YOLO mode runs Claude Code with `--dangerously-skip-permissions`, providing unrestricted command execution within the container. The container provides isolation through:

- **Filesystem boundaries**: Only `~/.claude`, `~/.gitconfig`, and your current working directory are accessible to Claude
- **Process isolation**: Rootless podman user namespace isolation (`--userns=keep-id`)
- **Limited host access**: SSH keys and other sensitive files are not mounted

**What is NOT restricted:**

- **Network access**: Claude can make arbitrary network connections from within the container (to package registries, APIs, external services, etc.)

**When to be cautious:**

- **Untrusted repositories**: Malicious code comments or documentation could exploit prompt injection to trick Claude into executing harmful commands or exfiltrating data
- Mounting directories with sensitive data (credentials, private keys, confidential files)
- Projects that access production systems or databases

**For higher security needs**, consider running untrusted code in a separate container without mounting sensitive directories, or wait for integration with Anthropic's modern sandbox runtime which provides network-level restrictions.
