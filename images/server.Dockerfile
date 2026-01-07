FROM base
USER root

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt update -y && \
    apt install -y iproute2 sqlite3 node-configurable-http-proxy

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir 'boto3>=1.26.0' kopf kubernetes

RUN useradd -m jupyter
RUN useradd -m user

RUN mkdir -m 755 /var/run/beaker
RUN mkdir -m 777 /var/run/beaker/checkpoints
RUN mkdir -p /workdir/user_files
RUN mkdir -p /var/run/jupyter/runtime
RUN chown user:user /workdir/user_files
ENV BEAKER_RUN_PATH=/var/run/beaker
ENV JUPYTER_RUNTIME_DIR=/var/run/jupyter/runtime

WORKDIR /pkg
COPY --from=src pyproject.toml /pkg/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

COPY --from=src --parents=true ./src/ ./README.md /pkg
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    ls -ltrah . && uv pip install --system --no-build-isolation .

ENV BEAKER_AGENT_USER=jupyter
ENV BEAKER_SUBKERNEL_USER=user
WORKDIR /workdir

COPY --from=beakerhub-ui /ui /ui

RUN rm -fr /beaker /pkg

CMD ["-m", "beakerhub.app", "--ip", "0.0.0.0", "--BeakerHub.beaker_static_path", "/ui"]
