# Agent image for pic's oci backend.
#
# This is the image pic LAUNCHES: it hosts the pi coding agent (npm)
# plus the tools it needs (mirrors guix/manifest.scm): python, git,
# openssh, gnupg, ca-certificates, the tools pi would otherwise
# auto-download on first use (fd, ripgrep), and mise for one-shot
# dev tools (guix has no mise package, so it is image-only).  pic
# itself (the launcher) stays on the host and is NOT part of this
# image.
#
# pic starts it with `run IMAGE pi INNER...`, so the command is always
# passed explicitly.

FROM node:24-bookworm-slim

# Pin with --build-arg PI_VERSION=0.83.0; default: latest from npm.
ARG PI_VERSION=latest
RUN npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@${PI_VERSION}" \
    && npm cache clean --force

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        git \
        openssh-client \
        gnupg \
        ca-certificates \
        curl \
        fd-find \
        ripgrep \
    && ln -s /usr/bin/fdfind /usr/bin/fd \
    && rm -rf /var/lib/apt/lists/*

# mise: one-shot dev tools inside the container (e.g. mise use node@24)
RUN curl -fsSL https://mise.jdx.dev/install.sh \
    | MISE_INSTALL_PATH=/usr/local/bin/mise sh

# plain `docker run IMAGE` starts pi; pic always overrides with its own
# command line
CMD ["pi"]
