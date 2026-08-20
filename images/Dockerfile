# Based on Anthropic's official Dockerfile: https://github.com/anthropics/claude-code/blob/07e13937b2d6e798ce1880b22ad6bd22115478e4/.devcontainer/Dockerfile
#
# Base: Node 24 (current LTS) on Debian 13 "trixie".  The distribution is
# pinned explicitly rather than using the rolling `node:24` tag (still
# bookworm) so that the distro-conditional logic below (the Apptainer package
# flavour) is deterministic and the toolchain does not silently jump releases.
#
# Debian bookworm shipped git 2.39, which lacks `git worktree add --orphan`
# (added in git 2.42); trixie ships 2.47.  See con/yolo#39.
ARG BASE_IMAGE=node:24-trixie
FROM ${BASE_IMAGE}

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Extra packages to install (space-separated list)
ARG EXTRA_PACKAGES=""

# Extras (set to "1" to enable)
ARG EXTRA_PLAYWRIGHT=""

# Install basic development tools
# tini is included as a minimal init process to properly reap zombie processes
# when Claude spawns external tools (git, npm, etc.) that may fork children
RUN apt-get update && apt-get install -y --no-install-recommends \
  dnsutils \
  fzf \
  gh \
  git \
  gnupg2 \
  iproute2 \
  jq \
  less \
  man-db \
  mc \
  moreutils \
  nano \
  ncdu \
  parallel \
  procps \
  shellcheck \
  sudo \
  tini \
  tree \
  unzip \
  vim \
  zsh \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install extra packages if specified
RUN if [ -n "$EXTRA_PACKAGES" ]; then \
      apt-get update && apt-get install -y --no-install-recommends $EXTRA_PACKAGES \
      && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

# Install Playwright system dependencies if enabled (must be done as root)
RUN if [ "$EXTRA_PLAYWRIGHT" = "1" ]; then \
      npx playwright install-deps chromium; \
    fi

# Apptainer (rootless container/SIF runtime) — upstream Debian install instructions:
# https://apptainer.org/docs/admin/main/installation.html#install-debian-packages
ARG EXTRA_APPTAINER=""
ARG APPTAINER_VERSION=1.4.5
RUN if [ "$EXTRA_APPTAINER" = "1" ]; then \
      ARCH=$(dpkg --print-architecture) && \
      if [ "$ARCH" != "amd64" ]; then \
        echo "EXTRA_APPTAINER only supports amd64 (got $ARCH); upstream publishes amd64 .deb only" && exit 1; \
      fi && \
      . /etc/os-release && \
      if [ "$VERSION_CODENAME" = "trixie" ] || [ "$VERSION_CODENAME" = "forky" ] || [ "$VERSION_CODENAME" = "sid" ]; then \
        DEB="apptainer_${APPTAINER_VERSION}-trixie+_amd64.deb"; \
      else \
        DEB="apptainer_${APPTAINER_VERSION}_amd64.deb"; \
      fi && \
      wget -qO "/tmp/${DEB}" \
        "https://github.com/apptainer/apptainer/releases/download/v${APPTAINER_VERSION}/${DEB}" && \
      apt-get update && \
      apt-get install -y --no-install-recommends "/tmp/${DEB}" && \
      apt-get clean && rm -rf /var/lib/apt/lists/* && \
      rm "/tmp/${DEB}"; \
    fi

# No CUDA userspace is installed on purpose.  GPU access is a runtime concern:
# `yolo --nvidia` passes the host GPU through with CDI, which injects the host's
# driver libraries (libcuda.so.1, libnvidia-ml.so.1) and device nodes into the
# container.  Shipping a CUDA toolkit here would only add several GB and risk
# shadowing those injected libraries with a mismatched userspace — the failure
# reported in con/yolo#79.  Verify passthrough with tools/gpu-check.py.
# If you need nvcc to compile CUDA sources in-container, install it yourself:
# Debian's nvidia-cuda-toolkit lives in non-free, which this image does not
# enable, so that means either a local Dockerfile edit or an nvcc wheel via
# uv/pip.

# Ensure default node user has access to /usr/local/share
RUN mkdir -p /usr/local/share/npm-global && \
  chown -R node:node /usr/local/share

ARG USERNAME=node

# Persist bash history.
RUN SNIPPET="export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  && mkdir /commandhistory \
  && touch /commandhistory/.bash_history \
  && chown -R $USERNAME /commandhistory

# Set `DEVCONTAINER` environment variable to help with orientation
ENV DEVCONTAINER=true

# Create workspace and config directories and set permissions
RUN mkdir -p /workspace /home/node/.claude && \
  chown -R node:node /workspace /home/node/.claude

WORKDIR /workspace

ARG GIT_DELTA_VERSION=0.18.2
RUN ARCH=$(dpkg --print-architecture) && \
  wget "https://github.com/dandavison/delta/releases/download/${GIT_DELTA_VERSION}/git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  sudo dpkg -i "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb" && \
  rm "git-delta_${GIT_DELTA_VERSION}_${ARCH}.deb"

# Set up non-root user
USER node

# Re-declare ARGs needed after USER switch (ARG values don't persist)
ARG EXTRA_PLAYWRIGHT

# Install global packages
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin

# Set the default shell to zsh rather than sh
ENV SHELL=/bin/zsh

# Set the default editor and visual
ENV EDITOR=vim
ENV VISUAL=vim

# Default powerline10k theme
ARG ZSH_IN_DOCKER_VERSION=1.2.0
RUN sh -c "$(wget -O- https://github.com/deluan/zsh-in-docker/releases/download/v${ZSH_IN_DOCKER_VERSION}/zsh-in-docker.sh)" -- \
  -p git \
  -p fzf \
  -a "source /usr/share/doc/fzf/examples/key-bindings.zsh" \
  -a "source /usr/share/doc/fzf/examples/completion.zsh" \
  -a "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" \
  -x

# Install Playwright and Chromium browser if enabled
RUN if [ "$EXTRA_PLAYWRIGHT" = "1" ]; then \
      npm install -g playwright && \
      npx playwright install chromium; \
    fi

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && \
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Add uv to PATH for this build
ENV PATH="/home/node/.local/bin:$PATH"

# Install git-annex
RUN uv tool install git-annex && \
  uv cache clean

# Optional extras: datalad and jj
ARG EXTRA_DATALAD=""
ARG EXTRA_JJ=""
ARG JJ_VERSION=0.38.0

# Install DataLad with useful extensions
RUN if [ "$EXTRA_DATALAD" = "1" ]; then \
      uv tool install --with datalad-container --with datalad-next datalad && \
      uv cache clean; \
    fi

# Install Jujutsu (jj) from GitHub release (musl binary for portability)
RUN if [ "$EXTRA_JJ" = "1" ]; then \
      ARCH=$(uname -m) && \
      wget -qO /tmp/jj.tar.gz \
        "https://github.com/jj-vcs/jj/releases/download/v${JJ_VERSION}/jj-v${JJ_VERSION}-${ARCH}-unknown-linux-musl.tar.gz" && \
      mkdir -p ~/.local/bin && \
      tar -xzf /tmp/jj.tar.gz -C ~/.local/bin ./jj && \
      rm /tmp/jj.tar.gz && \
      mkdir -p ~/.zfunc && \
      ~/.local/bin/jj util completion zsh > ~/.zfunc/_jj && \
      echo 'fpath=(~/.zfunc $fpath)' >> ~/.zshrc; \
    fi

# Install Deno JS/TS runtime and formatter
ARG EXTRA_DENO=""
ARG DENO_VERSION=""

RUN if [ "$EXTRA_DENO" = "1" ]; then \
      if [ -n "$DENO_VERSION" ]; then \
        curl -fsSL https://deno.land/install.sh | sh -s -- --version "v$DENO_VERSION"; \
      else \
        curl -fsSL https://deno.land/install.sh | sh; \
      fi && \
      echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.zshrc && \
      echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc; \
    fi

ENV PATH="/home/node/.deno/bin:$PATH"

# Install Entire CLI via Go
ARG EXTRA_ENTIRE=""

RUN if [ "$EXTRA_ENTIRE" = "1" ]; then \
      ARCH=$(uname -m) && \
      case "$ARCH" in \
        x86_64) GOARCH=amd64 ;; \
        aarch64) GOARCH=arm64 ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
      esac && \
      GO_VERSION=1.24.2 && \
      wget -qO /tmp/go.tar.gz "https://go.dev/dl/go${GO_VERSION}.linux-${GOARCH}.tar.gz" && \
      mkdir -p /tmp/goroot && \
      tar -xzf /tmp/go.tar.gz -C /tmp/goroot --strip-components=1 && \
      GOROOT=/tmp/goroot GOPATH=/tmp/gopath PATH="/tmp/goroot/bin:$PATH" \
        go install github.com/entireio/cli/cmd/entire@v0.6.1 && \
      mkdir -p ~/.local/bin && \
      mv /tmp/gopath/bin/entire ~/.local/bin/entire && \
      chmod -R u+w /tmp/gopath && \
      rm -rf /tmp/go.tar.gz /tmp/goroot /tmp/gopath; \
    fi

# Install Claude
# Cache-bust: pass --build-arg CLAUDE_CACHEBUST=$(date +%s) to force a fresh install
ARG CLAUDE_CACHEBUST=
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Use tini as init process to properly reap zombie processes
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["claude"]
