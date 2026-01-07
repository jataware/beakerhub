ARG base_img=python:3.13

FROM base AS node-base
USER root

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update -y && \
    apt install -y --no-install-recommends lsof rsync curl wget graphviz libgraphviz-dev && \
    apt install -y --no-install-recommends texlive-xetex texlive-fonts-recommended texlive-plain-generic xclip || true
    # Ignore error if packages from second line are not able to be installed

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system 'boto3>=1.26.0' kopf kubernetes jupyterhub pandoc tqdm dill

# RUN useradd -m ${notebook_user} && echo "${notebook_user} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
RUN mkdir -m 755 /var/run/beaker
RUN mkdir -p /var/run/jupyter/runtime
ENV BEAKER_RUN_PATH=/var/run/beaker
ENV JUPYTER_RUNTIME_DIR=/var/run/jupyter/runtime

# RUN mkdir -p /home/${notebook_user}/workdir
# WORKDIR /home/${notebook_user}/workdir
RUN mkdir -p /workdir
WORKDIR /workdir

CMD ["-m", "beaker_notebook.app.server_app", "--ip", "0.0.0.0", "--allow-root"]


########

FROM ${base_img} AS base

LABEL "beaker"="true"
LABEL "beaker.env"="beakerhub"

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt update -y && \
    apt install -y curl git vim-tiny unzip less net-tools
RUN ln -sf /usr/bin/vim.tiny /usr/bin/vim

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    pip install 'hatch<1.16' uv build 'virtualenv<21.0.0'

COPY --from=config bin/entry-point.sh /usr/local/bin/entry-point.sh

ENTRYPOINT ["entry-point.sh"]
