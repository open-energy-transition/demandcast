# Dockerfile

We assume you have some familiarity with containers,
as there are a lot of materials out there to learn from.
For simplicity we give one example on how to build the container:
```bash
cd ETL/
docker build -t demandcast .
```
Below we explain the contents of the Dockerfile and the reasoning behind what we included.
The container ensures that all team members and deployment environments run with the same environment.

## Base Image

```dockerfile
FROM --platform=linux/amd64 python:3.12
```

The Dockerfile starts with the official Python 3.12 image for the `linux/amd64` platform.
This ensures consistent behavior across different operating systems.

## Google Cloud CLI Installation

```dockerfile
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    apt-get update -y && \
    apt-get install google-cloud-cli -y
```

This multi-step command installs the Google Cloud CLI, which is essential for the projects data pipeline:

1. **Add Google Cloud SDK repository**: Adds the official Google Cloud SDK package repository to the systems package sources
2. **Import GPG key**: Downloads and imports Googles GPG key to verify package authenticity
3. **Update package lists**: Refreshes the apt package index with the newly added repository
4. **Install Google Cloud CLI**: Installs the `google-cloud-cli` package

The Google Cloud CLI is a dependency because the project interacts with Google Cloud Storage and Google Cloup Platform is our deployment target.

## UV Package Manager Installation

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
```

This step installs [uv](https://docs.astral.sh/uv/), a Python package manager, by copying the pre-built binaries from the official distroless image (See their [docs](https://docs.astral.sh/uv/guides/integration/docker/#installing-uv) for more detail).

## Copying Code into Container

```dockerfile
ADD . /app
WORKDIR /app
```

1. **Copy project files**: Adds all project files from the build context to `/app` in the container

2. **Set working directory**: Changes the working directory to `/app` for subsequent commands

## Dependency Installation

```dockerfile
RUN uv sync --frozen
```

This command synchronizes the project dependencies using uv:

- **`sync`**: Installs dependencies and creates a virtual environment
- **`--frozen`**: Uses the exact versions specified in the lockfile without attempting to update them, ensuring:
  - Reproducible builds across different environments
  - Consistent dependency versions in development and production
  - Faster installation by skipping dependency resolution

This is particularly important for the DemandCast project, which has dependencies on:
- Geospatial libraries (pyogrio, geopandas)
- Machine learning frameworks (XGBoost)
- Data processing tools (pandas, numpy)
- Testing frameworks (pytest)

## Environment Activation

```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
```

This final step activates the virtual environment by prepending its binary directory to the system PATH. This means:

- All Python commands will use the virtual environments Python interpreter
- Installed packages are immediately available without explicit activation
- The container is ready to run the ETL pipeline, models, or any other project scripts

This approach is cleaner than traditional virtual environment activation in Docker, as it doesnt require sourcing activation scripts in each RUN command.
