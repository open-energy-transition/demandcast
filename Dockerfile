FROM --platform=linux/amd64 python:3.12

# Install Google Cloud CLI and its required packages
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update -y && \
    apt-get install google-cloud-cli -y

# https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
# install uv by copying the binary from the official distroless Docker image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, using the frozen lockfile
WORKDIR /app
RUN uv sync --frozen

# https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
# activate the project virtual environment by placing its binary directory at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
