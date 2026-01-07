FROM base

# Python notebook env
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system ipykernel numpy pandas matplotlib seaborn plotly tqdm dill

# R notebook env
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt update -y && \
    apt install -y --no-install-recommends r-base-core r-cran-irkernel

# Julia notebook env
ENV JULIA_PATH=/usr/local/julia
COPY --from=julia:latest $JULIA_PATH $JULIA_PATH
ENV PATH="$JULIA_PATH/bin:$PATH"
RUN julia -e ' \
    packages = [ "IJulia" ]; \
    using Pkg; \
    Pkg.add(packages);'
RUN rm -rf /usr/local/julia/share/doc \
        /usr/local/julia/share/man \
        /usr/local/julia/depot/logs \
        /usr/local/julia/depot/registries \
        /root/.julia/logs \
        /root/.julia/registries
RUN julia -e 'using Pkg; Pkg.gc()'

RUN uv pip install --system beaker-notebook
RUN --mount=type=bind,from=beaker-hub-src,target=/beakerhub uv pip install --system /beakerhub
