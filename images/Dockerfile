# Based on Anthropic's official Dockerfile: https://github.com/anthropics/claude-code/blob/07e13937b2d6e798ce1880b22ad6bd22115478e4/.devcontainer/Dockerfile
FROM node:22

ARG TZ
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Extra packages to install (space-separated list)
ARG EXTRA_PACKAGES=""

# Extras (set to "1" to enable)
ARG EXTRA_CUDA=""
ARG EXTRA_PLAYWRIGHT=""

# Install basic development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
  less \
  git \
  procps \
  sudo \
  fzf \
  zsh \
  man-db \
  unzip \
  gnupg2 \
  gh \
  iproute2 \
  dnsutils \
  jq \
  nano \
  vim \
  shellcheck \
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

# NVIDIA CUDA toolkit for building CUDA extensions
# Runtime GPU access (nvidia-smi, drivers) is handled by CDI at container runtime
# To use: run container with --device nvidia.com/gpu=all (yolo --nvidia)
RUN if [ "$EXTRA_CUDA" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends nvidia-cuda-toolkit \
      && apt-get clean && rm -rf /var/lib/apt/lists/*; \
    fi

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

# Install Claude
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

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

CMD ["claude"]
