FROM base
USER root

# Add node/npm to apt
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash -

# Update apt and install npm
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt update -y && \
    apt install -y nodejs

COPY --from=src ./ /build

WORKDIR /build
RUN npm i && npm run ui:build && cp -r /build/ui/dist /ui
