# Install

This page sets up DemandCast on your computer: the code, its Python environment, the API keys of the data sources, and the folder where the data goes. It takes about 10 minutes.

!!! tip "Only need the forecasts?"
    The trained model and hourly forecasts for 184 countries and 135 subdivisions from 2000 to 2025 are on [Zenodo](https://doi.org/10.5281/zenodo.18374351). You do not need to install anything to use them.

## What you need

- **Git**, to download the code.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, a fast Python package manager. It installs the right Python version (3.12 or later) and all the dependencies for you.
- **Disk space.** The code is small. The data is not: weather grids and the electricity demand of many sources can take tens of gigabytes.

You can also use [Docker](../guides/docker.md) instead of uv. The Docker image has everything installed.

## 1. Get the code

```bash
git clone https://github.com/open-energy-transition/demandcast.git
cd demandcast/demandcast
```

The repository has a `demandcast/` folder inside it. **Run every command from this inner `demandcast/` folder**: the scripts import their modules from there.

## 2. Install the dependencies

```bash
uv sync
```

uv reads `pyproject.toml`, creates a virtual environment in `.venv/`, and installs the exact versions listed in `uv.lock`.

The LSTM model is optional and needs PyTorch, a large dependency. Install it only if you plan to use that model:

```bash
uv sync --extra lstm
```

Check that everything works by printing the help of a script:

```bash
uv run retrieve.py --help
```

!!! note "Not using uv?"
    You can install the dependencies of `pyproject.toml` with another tool, such as conda or pip. Then replace `uv run <script>.py` with `python <script>.py` in all the commands of this documentation.

To use Jupyter notebooks with the same environment:

```bash
uv run --with jupyter jupyter lab
```

## 3. Add your API keys

Some data sources require you to register and use a personal key. DemandCast reads the keys from a file named `.env` in the `demandcast/` folder. Create it and add only the keys you need, one per line, without quotes:

```bash
CDS_API_KEY=<your_key>
EMBER_API_KEY=<your_key>
ENTSOE_API_KEY=<your_key>
EIA_API_KEY=<your_key>
EPIAS_USERNAME=<your_username>
EPIAS_PASSWORD=<your_password>
ISONE_USERNAME=<your_username>
ISONE_PASSWORD=<your_password>
ZENODO_API_KEY=<your_key>
SANDBOX_ZENODO_API_KEY=<your_key>
```

Put any comment on its own line, starting with `#`: Docker's `--env-file` would read a comment after a value as part of the key.

| Key | Needed for | Where to get it |
|---|---|---|
| `CDS_API_KEY` | Gridded weather and temperature (not for past years with `reanalysis_source: arco`) | Register on the [Climate Data Store](https://cds.climate.copernicus.eu/) and accept the licences of the ERA5 and CMIP6 datasets |
| `EMBER_API_KEY` | Annual electricity demand per capita | [Ember API](https://api.ember-energy.org/v1/docs) (free) |
| `ENTSOE_API_KEY` | The `entsoe` data source | Register on the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) and request API access |
| `EIA_API_KEY` | The `eia` data source | [EIA Open Data](https://www.eia.gov/opendata/) (free) |
| `EPIAS_USERNAME`, `EPIAS_PASSWORD` | The `epias` data source | A free account on [EPİAŞ Transparency](https://seffaflik.epias.com.tr/) |
| `ISONE_USERNAME`, `ISONE_PASSWORD` | The `isone` data source | A free [ISO Express](https://www.iso-ne.com/isoexpress/) account |
| `ZENODO_API_KEY`, `SANDBOX_ZENODO_API_KEY` | [Publishing a release](../guides/publish.md) | Your Zenodo account settings |

A script that needs a missing key stops with an error that names the variable. Keys already set in your shell take priority over the `.env` file.

!!! warning
    Never commit `.env`: it holds your personal credentials. The repository's `.gitignore` already excludes it.

## 4. Choose where the data goes

Everything the scripts write (downloads, datasets, models, results and logs) goes in the **data folder**, `demandcast/data/` by default. To keep it somewhere else, such as on a larger disk, set the environment variable `DEMANDCAST_DATA_FOLDER` in your shell:

```bash
export DEMANDCAST_DATA_FOLDER=/path/to/large/disk/demandcast-data
```

or add it to `demandcast/.env`, next to your keys:

```
DEMANDCAST_DATA_FOLDER=/path/to/large/disk/demandcast-data
```

The scripts read `.env` before they look for the data folder, and a variable set in your shell wins over `.env`. Give an absolute path.

The [Data folder](../reference/data-folder.md) page describes everything inside it.

## Next step

Follow [Your first forecast](first-forecast.md) to retrieve data, train a model and forecast a year of hourly demand.
