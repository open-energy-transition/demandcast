# Docker

DemandCast provides a Docker image with Python, the locked dependencies and the DemandCast code, so that the scripts run the same way on every system. The image is published to the GitHub Container Registry for every change on `main` and every release, and you can also build it yourself.

## Prerequisites

Install Docker:

- **Docker Desktop** (recommended for Windows and macOS): [Install Docker Desktop](https://docs.docker.com/get-docker/)
- **Docker Engine** (for Linux): [Install Docker Engine](https://docs.docker.com/engine/install/)

Check that Docker is installed and running:

```bash
docker --version
```

## Using the published image

Pull the image:

```bash
docker pull ghcr.io/open-energy-transition/demandcast-demandcast:latest
```

The available tags are `latest` (the current `main`), the release versions (for example `1.0.0`, `1.0` and `1`) and `sha-<commit>` for each commit on `main`.

Each published image is signed with [Sigstore](https://www.sigstore.dev/) and comes with a provenance attestation and a software bill of materials (SBOM). You can verify where an image was built with the [GitHub CLI](https://cli.github.com/):

```bash
gh attestation verify oci://ghcr.io/open-energy-transition/demandcast-demandcast:latest --owner open-energy-transition
```

## Building the image

From the root of the repository, run:

```bash
docker build -t demandcast demandcast/
```

The image does not include the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), which DemandCast does not need. To add it, run:

```bash
docker build -t demandcast --build-arg INSTALL_GCLOUD=true demandcast/
```

## Running the container

The examples below use the image built locally (`demandcast`); replace it with `ghcr.io/open-energy-transition/demandcast-demandcast:latest` to use the published image.

### Interactive shell

```bash
docker run -it --rm demandcast bash
```

- `-it`: runs the container interactively with a terminal
- `--rm`: removes the container when it exits

### Running a script

```bash
docker run --rm demandcast uv run retrieve.py
```

### Mounting local data

To keep the data after the container stops, mount a local folder on `/app/data`:

```bash
docker run -it --rm -v "$(pwd)/data:/app/data" demandcast bash
```

The container runs as an unprivileged user with ID 1000. On Linux, if your user ID is different (check with `id -u`), make the folder writable for the container:

```bash
chmod a+rwx data
```

### Using environment variables

Pass API keys as environment variables, from a file or one by one:

```bash
docker run --rm --env-file demandcast/.env demandcast uv run retrieve.py
docker run --rm -e CDS_API_KEY=your_key demandcast uv run retrieve.py
```

To upload data to Google Cloud Storage, mount a service account key and point `GOOGLE_APPLICATION_CREDENTIALS` to it:

```bash
docker run --rm -v "$HOME/key.json:/secrets/key.json:ro" -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/key.json demandcast uv run upload.py
```

## What the image contains

The [Dockerfile](https://github.com/open-energy-transition/demandcast/blob/main/demandcast/Dockerfile):

- starts from the official `python:3.12-slim` image, and copies [uv](https://docs.astral.sh/uv/) from its official image, both pinned to an exact digest (Dependabot proposes updates);
- installs the dependencies from `uv.lock` (`uv sync --locked --no-dev`) into `/app/.venv`, without development tools such as pytest;
- copies the DemandCast code to `/app`, without the tests and the `archive/` folder;
- runs as the unprivileged user `demandcast` (ID 1000);
- puts the virtual environment on the `PATH`, so `python` and `uv run` use it directly, without changing it.

## Best practices

1. **Keep the image updated**: pull the latest image, or rebuild it after changing `pyproject.toml` or `uv.lock`.
2. **Use volume mounts**: mount folders to keep data and logs after the container stops.
3. **Manage secrets securely**: never put API keys in the image; pass them as environment variables or mounted files.
4. **Resource limits**: for large-scale data processing, consider limiting memory and CPU with `--memory` and `--cpus`.
5. **Cleanup**: remove unused containers and images with `docker system prune`.

## Troubleshooting

**Build fails with network errors**: check your internet connection and retry. The build downloads the base images and the Python packages.

**Permission errors when writing to mounted folders**: make the folder writable for the container's user (ID 1000), see [Mounting local data](#mounting-local-data).

**Container runs out of memory**: increase Docker's memory in the Docker Desktop settings, or use the `--memory` flag.
