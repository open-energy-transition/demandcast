# Dockerfile

DemandCast provides a Dockerfile to create a containerized environment with all dependencies pre-installed. Containers package the application and its dependencies into a single, portable unit that runs consistently across different systems.

## Prerequisites

Before using the Dockerfile, ensure you have Docker installed on your system:

- **Docker Desktop** (recommended for Windows and macOS): [Install Docker Desktop](https://docs.docker.com/get-docker/)
- **Docker Engine** (for Linux): [Install Docker Engine](https://docs.docker.com/engine/install/)

To verify Docker is installed and running:
```bash
docker --version
```

## Building the Container

To build the Docker image, navigate to the repository root and run:

```bash
cd demandcast
docker build -t demandcast -f demandcast/Dockerfile demandcast/
```

This command:
- `-t demandcast`: Tags the image with the name "demandcast"
- `-f demandcast/Dockerfile`: Specifies the Dockerfile location
- `demandcast/`: Sets the build context to the demandcast directory

The build process typically takes 5-10 minutes depending on your internet connection and system performance.

## Running the Container

Once built, you can run the container in different ways:

### Interactive Shell

To start an interactive shell session inside the container:

```bash
docker run -it --rm demandcast bash
```

This allows you to run commands interactively within the containerized environment:
- `-it`: Runs the container in interactive mode with a terminal
- `--rm`: Automatically removes the container when it exits
- `bash`: Starts a bash shell

### Running a Specific Script

To execute a specific script:

```bash
docker run --rm demandcast uv run retrieve.py
```

### Mounting Local Data

To access local files or save outputs to your host machine, mount a volume:

```bash
docker run -it --rm -v $(pwd)/data:/app/data demandcast bash
```

This mounts your local `data/` directory to `/app/data` inside the container, allowing the container to read/write files that persist after the container stops.

### Using Environment Variables

To pass API keys and other environment variables:

```bash
docker run --rm --env-file demandcast/.env demandcast uv run retrieve.py
```

Or pass individual variables:

```bash
docker run --rm -e CDS_API_KEY=your_key demandcast uv run retrieve.py
```

## Dockerfile Explained

Below we explain the contents of the Dockerfile and the reasoning behind what we included. The container ensures that all team members and deployment environments run with the same dependencies and configuration.

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

The Google Cloud CLI is a dependency because the project interacts with Google Cloud Storage and Google Cloud Platform is our deployment target.

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

The `--frozen` flag is particularly important for the DemandCast project, which has complex dependencies on:
- Geospatial libraries (pyogrio, geopandas)
- Machine learning frameworks (XGBoost)
- Data processing tools (pandas, polars, numpy)
- Testing frameworks (pytest)
- Weather data APIs (cdsapi)

## Environment Activation

```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
```

This final step activates the virtual environment by prepending its binary directory to the system PATH. This means:

- All Python commands will use the virtual environment's Python interpreter
- Installed packages are immediately available without explicit activation
- The container is ready to run retrieval scripts, ML training, forecasting, or any other project scripts

This approach is cleaner than traditional virtual environment activation in Docker, as it doesn't require sourcing activation scripts in each RUN command.

## Best Practices

When working with the Docker container:

1. **Keep the image updated**: Rebuild the image after updating dependencies in `pyproject.toml` or `uv.lock`
2. **Use volume mounts**: Mount directories to persist data and logs between container runs
3. **Manage secrets securely**: Never include API keys in the Dockerfile; always pass them via environment variables or mounted `.env` files
4. **Resource limits**: For large-scale data processing, consider setting memory and CPU limits using `--memory` and `--cpus` flags
5. **Cleanup**: Remove unused containers and images periodically with `docker system prune`

## Troubleshooting

**Build fails with network errors**: Check your internet connection and retry. The build process downloads packages from external repositories.

**Permission errors when accessing mounted volumes**: On Linux, you may need to adjust file permissions or run the container with appropriate user mapping using `--user $(id -u):$(id -g)`.

**Container runs out of memory**: Increase Docker's memory allocation in Docker Desktop settings or use the `--memory` flag to allocate more resources.
