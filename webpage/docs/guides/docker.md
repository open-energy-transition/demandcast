# Run DemandCast with Docker

DemandCast publishes a Docker image with Python, the locked dependencies and the code, so that the scripts run the same way on every system. Use it if you prefer not to install Python and uv, or to run DemandCast on a server.

An **image** is a packaged file system with everything a program needs. A **container** is one running copy of an image. Files written inside a container disappear when it is removed, unless you **mount** a folder of your computer into it.

## Install Docker

- **Windows and macOS**: [Docker Desktop](https://docs.docker.com/get-docker/).
- **Linux**: [Docker Engine](https://docs.docker.com/engine/install/).

Check that Docker is installed and running:

```bash
docker --version
```

## Get the image

### Pull the published image

Each push to `main` and each release publishes the image to the GitHub Container Registry as `ghcr.io/open-energy-transition/demandcast-demandcast`, with these tags:

| Tag | Which image |
|---|---|
| `latest`, `main` | The latest commit of `main` |
| `2.1.0` (the version of a release) | The release `v2.1.0` |
| `2.1`, `2` | The latest release of that minor or major version |
| `sha-<commit>` | One commit, by the first seven characters of its hash |

Pull the image of a release:

```bash
docker pull ghcr.io/open-energy-transition/demandcast-demandcast:2.1.0
```

Prefer a release tag over `latest`: your results then come from a known version of the code.

### Build the image yourself

Build your own image to use code you changed, or the [LSTM model](#use-the-lstm-model). From the `demandcast/` folder, run:

```bash
docker build -t demandcast .
```

This names the image `demandcast`. The rest of this page uses that name. To use the published image instead, replace `demandcast` with `ghcr.io/open-energy-transition/demandcast-demandcast:<tag>`.

The image does not include the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install): DemandCast reaches Cloud Storage through its Python library. To add the CLI, for example to log in from inside a container, build with:

```bash
docker build -t demandcast --build-arg INSTALL_GCLOUD=true .
```

Rebuild the image after you change the code, `pyproject.toml` or `uv.lock`.

## Run a script

The working folder of the container is `/app`, which holds the code. Run a script as you would on your computer:

```bash
docker run --rm demandcast uv run retrieve.py --help
```

`--rm` removes the container when the script ends. The image has no default script: without a command, it runs `python3`.

To open a shell inside the container and run several commands:

```bash
docker run -it --rm demandcast bash
```

`-it` connects your terminal to the container.

To pass a settings file of your own, mount it and give its path inside the container:

```bash
docker run --rm \
  -v "$(pwd)/config/my_retrieval.yaml:/app/config/my_retrieval.yaml:ro" \
  demandcast uv run retrieve.py --config config/my_retrieval.yaml
```

`:ro` mounts the file read-only.

## Keep the data

Everything the scripts write goes in the [data folder](../concepts/glossary.md#data-folder), `/app/data` inside the container. Without a mount, it is lost when the container is removed.

Mount a folder of your computer on `/app/data`. From the `demandcast/` folder, this uses the same data folder as a local installation:

```bash
docker run -it --rm -v "$(pwd)/data:/app/data" demandcast bash
```

To use another path inside the container, set `DEMANDCAST_DATA_FOLDER` to it:

```bash
docker run --rm \
  -v /path/to/large/disk/demandcast-data:/data \
  -e DEMANDCAST_DATA_FOLDER=/data \
  demandcast uv run retrieve.py
```

The files of the electricity demand that you [download by hand](retrieve.md) also go in the data folder, so the container sees them only through this mount.

!!! note "File permissions on Linux"
    The container runs as an unprivileged user with ID 1000, and the files it writes belong to that ID. If your user ID is different (check with `id -u`), make the folder writable for the container first:

    ```bash
    chmod a+rwx data
    ```

On Windows PowerShell, write `${PWD}` instead of `$(pwd)`.

## Pass your API keys

Pass the keys of the data sources as environment variables, from a file or one by one:

```bash
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" demandcast uv run retrieve.py
docker run --rm -e CDS_API_KEY=<your_key> -v "$(pwd)/data:/app/data" demandcast uv run retrieve.py
```

The image never contains your `.env` file: it is left out when the image is built. Never add keys to the image; pass them when you run it.

!!! warning "Docker reads `.env` more strictly than DemandCast"
    `--env-file` takes each line literally. It does not remove quotes or comments at the end of a line. A line such as `CDS_API_KEY=abc123   # Copernicus` gives the key `abc123   # Copernicus`, which the data source rejects. For Docker, write each key alone on its line, without quotes or trailing comments, and comments on their own lines.

Do not set `DEMANDCAST_DATA_FOLDER` to a path of your computer in a file passed with `--env-file`: inside the container, that path does not exist. Set it with `-e` to the path of the mount, as above.

## Copy the data folder to or from a bucket

[`sync.py`](sync.md) needs Google credentials. The image has no `gcloud` login, so pass the credentials as a file, and point `GOOGLE_APPLICATION_CREDENTIALS` to it.

With a service account key:

```bash
docker run --rm \
  -v "$HOME/key.json:/secrets/key.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/key.json \
  -v "$(pwd)/data:/app/data" \
  demandcast uv run sync.py
```

With your own login, after `gcloud auth application-default login` on your computer:

```bash
docker run --rm \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/secrets/adc.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/adc.json \
  -v "$(pwd)/data:/app/data" \
  demandcast uv run sync.py
```

On Windows, the login file is in `%APPDATA%\gcloud\application_default_credentials.json`.

## Use the LSTM model

The image has the dependencies without the optional `lstm` extra, so it cannot train or run the LSTM model. To add it:

1. In `demandcast/Dockerfile`, add `--extra lstm` to the `uv sync` command:

    ```dockerfile
    uv sync --locked --no-dev --no-install-project --extra lstm
    ```

2. [Build the image](#build-the-image-yourself).

The image installs the CPU-only build of PyTorch, from the index set in `pyproject.toml`.

## What the image contains

The [Dockerfile](https://github.com/open-energy-transition/demandcast/blob/main/demandcast/Dockerfile):

- starts from the official `python:3.12-slim` image, and copies [uv](https://docs.astral.sh/uv/) from its official image. Both are pinned to an exact digest, and Dependabot proposes their updates every month;
- removes `pip` from the base image, since uv installs and runs the environment;
- upgrades the Debian packages of the base image, so that it has the security fixes released since the base image was built;
- installs `libexpat1`, the XML parser that the GDAL library of rasterio loads to read rasters;
- installs the dependencies from `uv.lock` (`uv sync --locked --no-dev`) into `/app/.venv`, without development tools such as pytest;
- copies the code to `/app`, including the configuration, the shapes, the data source files and the files downloaded by hand that come with the code;
- creates an empty data folder, `/app/data`;
- runs as the unprivileged user `demandcast` (ID 1000);
- puts the virtual environment on the `PATH`, so `python` and `uv run` use it directly. `uv run` never changes the installed environment (`UV_NO_SYNC=1`).

`demandcast/.dockerignore` keeps these out of the image: the tests, the contents of `data/`, Parquet files, `.env`, `.venv`, and caches.

The image has no git repository. The [manifests](../concepts/glossary.md#manifest) of the files made in a container therefore record no commit (`commit` is `null`). They still record the checksum of `uv.lock`.

## How the image is published

The GitHub workflow `.github/workflows/docker-publish.yml` publishes the image on each push to `main` and each version tag (`v*`):

1. On a version tag, it checks that `demandcast/pyproject.toml` and `CITATION.cff` have the version of the tag, and stops otherwise.
2. It builds the image without any cache, so that a cache written by a pull request never ends up in a published image.
3. It scans the image for vulnerabilities. An image with a vulnerability of high or critical severity that has a fix is not published.
4. It pushes the image with its tags, a software bill of materials (SBOM, the list of the packages it contains) and an attestation of its provenance (where and how it was built).
5. It signs the image with [cosign](https://docs.sigstore.dev/cosign/), without a key, using the identity of the workflow.

Pull requests build the image in the CI workflow. CI checks that it runs as user 1000, that `retrieve.py --help` works, and that the files downloaded by hand that come with the code are in it.

To check the signature of an image:

```bash
cosign verify ghcr.io/open-energy-transition/demandcast-demandcast:2.1.0 \
  --certificate-identity-regexp '^https://github.com/open-energy-transition/demandcast/\.github/workflows/docker-publish\.yml@' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

To check its provenance with the GitHub CLI:

```bash
gh attestation verify oci://ghcr.io/open-energy-transition/demandcast-demandcast:2.1.0 \
  --repo open-energy-transition/demandcast
```

## Good practice

1. **Pin a version**: use a release tag, such as `2.1.0`, rather than `latest`.
2. **Mount the data folder**, so that data and logs survive the container.
3. **Keep secrets out of the image**: pass keys with `--env-file` or `-e`, and credential files with a read-only mount.
4. **Limit resources** for large runs, with `--memory` and `--cpus`.
5. **Clean up** unused containers and images with `docker system prune`.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| The build fails with network errors | The build downloads the base images and the Python packages. Check your connection and try again. |
| `Permission denied` when writing to the mounted folder | The container's user (ID 1000) cannot write there. See [Keep the data](#keep-the-data). |
| The data is gone after the container stops | The data folder was not mounted. Mount it with `-v`. |
| An API key is rejected in Docker but works locally | Your `.env` has quotes or comments at the end of the line. See [Pass your API keys](#pass-your-api-keys). |
| `No module named 'torch'` | The image has no LSTM dependencies. See [Use the LSTM model](#use-the-lstm-model). |
| The container runs out of memory | Give Docker more memory in the Docker Desktop settings, or raise `--memory`. |
| `sync.py` fails with a credentials error | Mount a credentials file and set `GOOGLE_APPLICATION_CREDENTIALS`. See [Copy the data folder to or from a bucket](#copy-the-data-folder-to-or-from-a-bucket). |
