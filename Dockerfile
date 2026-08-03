# Agent image for pic's oci backend.
#
# This is the image pic LAUNCHES: it hosts the pi coding agent (npm)
# plus the tools from the example guix manifest (guix/manifest.scm):
# python, git, openssh, gnupg, ca-certificates.  pic itself (the
# launcher) stays on the host and is NOT part of this image.
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
    && rm -rf /var/lib/apt/lists/*

# plain `docker run IMAGE` starts pi; pic always overrides with its own
# command line
CMD ["pi"]
