# Claude Code Sandbox vs. YOLO: A Comparison

Both solve the same fundamental problem — **how to let Claude Code run autonomously without it doing something dangerous** — but they take very different architectural approaches.

## Core Philosophy

| | Claude Code Sandbox | YOLO |
|---|---|---|
| **Approach** | Fine-grained OS-level policy enforcement | Coarse-grained container isolation |
| **Metaphor** | "You can run freely, but these specific walls are enforced by the kernel" | "You're in a separate room; do whatever you want in there" |
| **Permission model** | Whitelist domains + filesystem paths, deny everything else | Mount only what's needed, auto-approve everything inside |
| **Technology** | macOS Seatbelt / Linux Bubblewrap + network proxy | Podman rootless containers + user namespaces |

## What Each Restricts

| Resource | Claude Code Sandbox | YOLO |
|---|---|---|
| **Filesystem write** | CWD only (configurable allowlist) | Only mounted volumes (CWD, `~/.claude`, `.gitconfig`) |
| **Filesystem read** | Whole machine minus denylist | Only mounted volumes |
| **Network** | Proxy-based domain allowlist | **Unrestricted** (intentional) |
| **SSH keys** | Accessible (unless denied) | **Not mounted** (no git push) |
| **Subprocess isolation** | All children inherit sandbox | All children are in the container |
| **Credentials** | Configurable deny (e.g., `~/.aws/credentials`) | Only OAuth token passed via env var |

## Key Trade-offs

### Claude Code Sandbox strengths

- **Network filtering** — the biggest differentiator. YOLO has no network restrictions, meaning a prompt injection attack could exfiltrate data. The sandbox's domain-level proxy blocks this.
- **No setup overhead** — no container build step, no image maintenance. Just `bubblewrap` + `socat` on Linux.
- **Full host read access by default** — Claude can read your whole machine (minus denylists), which is useful for cross-project work.
- **Granular configurability** — per-path, per-domain rules in `settings.json`.
- **Open-source runtime** — `@anthropic-ai/sandbox-runtime` is reusable in other agent projects.

### YOLO strengths

- **Stronger filesystem isolation** — sandbox allows reading the whole machine by default; YOLO only exposes what you mount. A read-based side-channel attack is harder.
- **Reproducible environment** — the Dockerfile gives you a known, consistent toolchain (git, gh, shellcheck, uv, etc.). No "works on my machine" issues.
- **Customizable environments** — NVIDIA GPU support, Playwright, DataLad, jj via `--extras`. The sandbox doesn't manage your tool environment.
- **Session portability** — preserved paths mean sessions work identically in and out of the container.
- **Config layering** — user-wide + per-project config with array merging for volumes/args.
- **No SSH key exposure** — a deliberate security boundary that forces push operations to happen on the host.

## Where YOLO Has a Gap

The **network** is the elephant in the room. YOLO's container has unrestricted network access. This means:

- A prompt injection in a code comment could instruct Claude to `curl` data to an attacker's server
- Malicious dependencies could phone home
- There's no domain allowlisting

The sandbox's proxy-based network filtering directly addresses this threat model.

## Where Claude Code Sandbox Has a Gap

- **No environment management** — you're running on your host. If Claude needs `playwright` or `cuda`, it's installing on your machine.
- **Read access is broad by default** — `~/.ssh`, `~/.gnupg`, env files, etc. are readable unless you explicitly deny them. YOLO's mount-only approach is deny-by-default for the filesystem.
- **Platform limitations** — no native Windows support, weaker in nested Docker environments on Linux.

## Could They Be Combined?

Yes, and it would be the strongest posture:

1. **YOLO for environment isolation** — reproducible toolchain, mount-only filesystem, no SSH keys
2. **Claude Code sandbox inside the container** — add network filtering and filesystem write restrictions within the already-restricted container

This would give you defense-in-depth: container boundaries for the coarse isolation + sandbox policies for fine-grained network and filesystem control inside.

## Summary

If your primary threat model is **"Claude modifies the wrong files or installs something I don't want"**, both approaches work well.

If your threat model includes **"data exfiltration via network"**, the Claude Code sandbox is strictly better today — YOLO would need network restrictions (e.g., podman `--network=none` plus an allowlist proxy, or just enabling sandbox mode inside the container).

If your concern is **reproducible, portable environments with known toolchains**, YOLO provides something the sandbox doesn't attempt.

They're complementary rather than competing.
