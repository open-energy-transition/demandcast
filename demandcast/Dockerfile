# DemandCast image: Python, the locked dependencies and the DemandCast code,
# run by an unprivileged user. Build with --build-arg INSTALL_GCLOUD=true to
# add the Google Cloud CLI.

FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv

FROM python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f

ARG INSTALL_GCLOUD=false

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3008
RUN if [ "${INSTALL_GCLOUD}" = "true" ]; then \
        apt-get update \
        && apt-get install --yes --no-install-recommends ca-certificates curl gnupg \
        && curl --fail --silent --show-error --location \
            https://packages.cloud.google.com/apt/doc/apt-key.gpg \
            | gpg --dearmor --output /usr/share/keyrings/cloud.google.gpg \
        && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
            > /etc/apt/sources.list.d/google-cloud-sdk.list \
        && apt-get update \
        && apt-get install --yes --no-install-recommends google-cloud-cli \
        && rm -rf /var/lib/apt/lists/*; \
    fi

COPY --from=uv /uv /uvx /bin/

RUN useradd --create-home --uid 1000 demandcast \
    && mkdir /app \
    && chown demandcast:demandcast /app
USER 1000:1000
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install the dependencies before copying the code, so that this layer is
# reused when only the code changes.
RUN --mount=type=cache,target=/home/demandcast/.cache/uv,uid=1000 \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=.python-version,target=.python-version \
    uv sync --locked --no-dev --no-install-project

COPY --chown=1000:1000 . .
RUN mkdir -p data

# Use the installed environment directly, and keep uv run from changing it.
ENV PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1
