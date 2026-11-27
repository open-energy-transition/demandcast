# Run DemandCast with Docker

DemandCast publishes a Docker image with Python, the locked dependencies and the code, so the scripts run the same way on every system. Use it to avoid installing Python and uv, or to run DemandCast on a server.

An **image** is a packaged file system with everything a program needs. A **container** is one running copy of an image. Files written inside a container disappear when it is removed, unless you **mount** a folder of your computer into it.

## Install Docker

Install [Docker Desktop](https://docs.docker.com/get-docker/) (Windows and macOS) or [Docker Engine](https://docs.docker.com/engine/install/) (Linux), and check that it runs with `docker --version`.

## Get the image

### Pull the published image

The image is published to the GitHub Container Registry as `ghcr.io/open-energy-transition/demandcast-demandcast`, with these tags:

| Tag | Which image |
|---|---|
| `latest`, `main` | The latest commit of `main` |
| `2.1.0` (a release version) | The release `v2.1.0` |
| `2.1`, `2` | The latest release of that minor or major version |
| `sha-<commit>` | One commit, by the first seven characters of its hash |

```bash
docker pull ghcr.io/open-energy-transition/demandcast-demandcast:2.1.0
```

Prefer a release tag over `latest`, so your results come from a known version of the code.

### Build the image yourself

Build your own image to use code you changed, or the [LSTM model](#use-the-lstm-model). From the `demandcast/` folder:

```bash
docker build -t demandcast .
```

The rest of this page uses this name, `demandcast`; for the published image, write `ghcr.io/open-energy-transition/demandcast-demandcast:<tag>` instead. Rebuild after you change the code, `pyproject.toml` or `uv.lock`.

The image does not include the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), since DemandCast reaches Cloud Storage through its Python library. To add it, for example to log in from inside a container, build with `--build-arg INSTALL_GCLOUD=true`.

## Run a script

The working folder of the container is `/app`, which holds the code:

```bash
docker run --rm demandcast uv run retrieve.py --help   # --rm removes the container at the end
docker run -it --rm demandcast bash                     # a shell inside the container
```

`-it` connects your terminal to the container. Without a command, the image runs `python3`.

To use your own settings file, mount it read-only (`:ro`) and give its path inside the container:

```bash
docker run --rm \
  -v "$(pwd)/config/my_retrieval.yaml:/app/config/my_retrieval.yaml:ro" \
  demandcast uv run retrieve.py --config config/my_retrieval.yaml
```

## Keep the data

The [data folder](../concepts/glossary.md#data-folder) is `/app/data` inside the container, and is lost with the container unless you mount a folder on it. From the `demandcast/` folder, this uses the same data folder as a local installation:

```bash
docker run -it --rm -v "$(pwd)/data:/app/data" demandcast bash
```

To mount it on another path, set `DEMANDCAST_DATA_FOLDER` to that path with `-e`:

```bash
docker run --rm \
  -v /path/to/large/disk/demandcast-data:/data \
  -e DEMANDCAST_DATA_FOLDER=/data \
  demandcast uv run retrieve.py
```

The electricity demand files that you [download by hand](retrieve.md#files-downloaded-by-hand) are in the data folder too, so the container sees them only through this mount. On Windows PowerShell, write `${PWD}` instead of `$(pwd)`.

!!! note "File permissions on Linux"
    The container runs as an unprivileged user with ID 1000, which owns the files it writes. If your user ID differs (check with `id -u`), make the folder writable first: `chmod a+rwx data`.

## Pass your API keys

Pass the keys as environment variables, from a file or one by one:

```bash
docker run --rm --env-file .env -v "$(pwd)/data:/app/data" demandcast uv run retrieve.py
docker run --rm -e CDS_API_KEY=<your_key> -v "$(pwd)/data:/app/data" demandcast uv run retrieve.py
```

The `.env` file is left out of the image when it is built. Never add keys to an image.

!!! warning "Docker reads `.env` more strictly than DemandCast"
    `--env-file` takes each line literally, with its quotes and end-of-line comments: `CDS_API_KEY=abc123   # Copernicus` gives the key `abc123   # Copernicus`, which the data source rejects. Write each key alone on its line, without quotes, and comments on their own lines.

Do not set `DEMANDCAST_DATA_FOLDER` to a path of your computer in a file passed with `--env-file`: that path does not exist in the container. Set it with `-e`, as above.

## Copy the data folder to or from a bucket

[`sync.py`](sync.md) needs Google credentials. Mount a credentials file read-only, and point `GOOGLE_APPLICATION_CREDENTIALS` to it. With a service account key:

```bash
docker run --rm \
  -v "$HOME/key.json:/secrets/key.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/key.json \
  -v "$(pwd)/data:/app/data" \
  demandcast uv run sync.py
```

With your own login, after `gcloud auth application-default login` on your computer, mount `$HOME/.config/gcloud/application_default_credentials.json` the same way (on Windows, `%APPDATA%\gcloud\application_default_credentials.json`):

```bash
docker run --rm \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/secrets/adc.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/adc.json \
  -v "$(pwd)/data:/app/data" \
  demandcast uv run sync.py
```

## Use the LSTM model

The image has no optional `lstm` extra, so it cannot train or run the LSTM model. To add it, add `--extra lstm` to the `uv sync` command of `demandcast/Dockerfile`, and [build the image](#build-the-image-yourself):

```dockerfile
uv sync --locked --no-dev --no-install-project --extra lstm
```

The image then installs the CPU-only build of PyTorch, from the index set in `pyproject.toml`.

## What the image contains

The [Dockerfile](https://github.com/open-energy-transition/demandcast/blob/main/demandcast/Dockerfile):

- starts from `python:3.12-slim` and copies [uv](https://docs.astral.sh/uv/) from its official image, both pinned to an exact digest (Dependabot proposes updates monthly);
- removes `pip`, since uv installs and runs the environment;
- upgrades the Debian packages, for the security fixes released since the base image was built;
- installs `libexpat1`, the XML parser that the GDAL library of rasterio loads to read rasters;
- installs the dependencies from `uv.lock` (`uv sync --locked --no-dev`) into `/app/.venv`, without development tools such as pytest;
- copies the code to `/app`, with the configuration, shapes, data source files and the files downloaded by hand that come with the code;
- creates an empty data folder, `/app/data`;
- runs as the unprivileged user `demandcast` (ID 1000);
- puts the virtual environment on the `PATH`, and sets `UV_NO_SYNC=1` so `uv run` never changes it.

`demandcast/.dockerignore` keeps out the tests, the contents of `data/`, Parquet files, `.env`, `.venv` and caches.

The image has no git repository, so the [manifests](../reference/data-folder.md#manifests) of files made in a container record no commit (`commit` is `null`), only the checksum of `uv.lock`.

## How the image is published

The workflow `.github/workflows/docker-publish.yml` runs on each push to `main` and each version tag (`v*`):

1. On a version tag, it checks that `demandcast/pyproject.toml` and `CITATION.cff` have the version of the tag, and stops otherwise.
2. It builds the image without cache, so a cache written by a pull request never ends up in a published image.
3. It scans the image. An image with a fixable vulnerability of high or critical severity is not published.
4. It pushes the image with its tags, a software bill of materials (SBOM, the list of its packages) and an attestation of its provenance (where and how it was built).
5. It signs the image with [cosign](https://docs.sigstore.dev/cosign/), without a key, using the identity of the workflow.

The CI workflow builds the image on pull requests, and checks that it runs as user 1000, that `retrieve.py --help` works, and that the files downloaded by hand that come with the code are in it.

To check the signature and the provenance of an image:

```bash
cosign verify ghcr.io/open-energy-transition/demandcast-demandcast:2.1.0 \
  --certificate-identity-regexp '^https://github.com/open-energy-transition/demandcast/\.github/workflows/docker-publish\.yml@' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/open-energy-transition/demandcast-demandcast:2.1.0 \
  --repo open-energy-transition/demandcast
```

## Good practice

- **Pin a version**: use a release tag rather than `latest`.
- **Mount the data folder**, so data and logs survive the container.
- **Keep secrets out of the image**: pass keys with `--env-file` or `-e`, and credential files with a read-only mount.
- **Limit resources** for large runs, with `--memory` and `--cpus`.
- **Clean up** unused containers and images with `docker system prune`.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| The build fails with network errors | The build downloads the base images and Python packages. Check your connection and try again. |
| `Permission denied` when writing to the mounted folder | User 1000 cannot write there. See [Keep the data](#keep-the-data). |
| The data is gone after the container stops | Mount the data folder with `-v`. |
| An API key is rejected in Docker but works locally | Your `.env` has quotes or end-of-line comments. See [Pass your API keys](#pass-your-api-keys). |
| `No module named 'torch'` | See [Use the LSTM model](#use-the-lstm-model). |
| The container runs out of memory | Give Docker more memory in Docker Desktop, or raise `--memory`. |
| `sync.py` fails with a credentials error | See [Copy the data folder to or from a bucket](#copy-the-data-folder-to-or-from-a-bucket). |
