# AGENTS.md

Instructions for AI coding agents working on DemandCast. Human contributors should read [CONTRIBUTING.md](CONTRIBUTING.md).

## Project

DemandCast retrieves hourly electricity demand, weather and socio-economic data from public sources, and trains machine learning models (XGBoost, and an optional LSTM) to forecast hourly electricity demand for countries and subdivisions. It is a Python 3.12+ project managed with [uv](https://docs.astral.sh/uv/).

## Pipeline

Each step is a script in `demandcast/`, configured by `config/<script>_config.yaml` (pass another file with `--config`):

1. `retrieve.py` downloads demand, weather and socio-economic data into `data/<variable>/`.
2. `assemble.py` merges the retrieved data into one dataset for training or forecasting, in `data/assembled/`. Its inputs are the rows of `DATASETS`: a new input is a new row, with its folder, columns and scenarios.
3. `train.py` trains a model; `validate.py` evaluates it on each entity's most recent year, and `cross_validate.py` on entities left out of training.
4. `forecast.py` predicts hourly demand in MW with a trained model.
5. `plot.py`, `check.py` and `upload.py` draw figures, check data availability and the data sources over the network, and upload data to Google Cloud Storage and Zenodo.

Paths come from `utils/paths.py`; use its functions instead of hard-coding paths. The inputs that come with the code (configuration, shapes, data source YAMLs, flag reviews) stay in the code folder, and everything the scripts write goes under the data folder: `data/`, or the folder named by `DEMANDCAST_DATA_FOLDER`. Each dataset has its own folder there, with its stages (`raw/`, `processed/`, ...), next to `assembled/`, `models/<algorithm>/`, `results/` (validation, cross-validation, forecasts, figures, check reports) and `logs/`.

Dependencies go one way: the scripts use `retrievals/`, `cleaning/`, `checks/`, `figures/` and `ml_models/`, which use `utils/`; `utils/` imports none of them (`tests/utils/test_dependencies.py` checks it).

The scenarios (SSP, IAMC and CMIP6), the climate models and the years of each projection and gridded dataset are listed once, in `utils/catalogue.py`; use it instead of writing them again.

## Layout

- `demandcast/`: the Python project. Run all Python commands from this folder, because modules are imported as top-level packages (`import utils.config`, not `import demandcast.utils.config`).
  - `retrievals/`: data retrieval. Each electricity demand source is a module plus a YAML file in `retrievals/electricity_demand_data_sources/`. The indicators (population, GDP PPP per capita, annual electricity demand per capita) save their years and scenarios with `retrievals/indicators.py`, and the gridded data extracts each country and subdivision with `retrievals/gridded.py`.
  - `ml_models/`: the models. `registry.py` lists them and defines the interface of their modules (`ModelModule`), `data.py` holds the settings of `config/ml_config.yaml` and prepares the data (target conversions, splits), `files.py` finds the latest model and assembled data and saves the results, and `evaluation.py` computes the errors (the MAPE of each entity and set, and the cross-validation).
  - `utils/`: shared helpers; CI requires at least 95% test coverage. The countries and subdivisions are in `codes.py` (ISO codes, names, continents), `data_sources.py` (the YAML registry of the data sources), `time_zones.py` and `availability.py` (the codes of interest and their data).
  - `benchmark/`: the configuration files of the data of the benchmark of the models and `run.py`, which retrieves and assembles it.
  - `tests/`: the pytest suite, in folders that mirror the code: the tests of `utils/fetcher.py` are in `tests/utils/test_fetcher.py`, and those of the scripts are at the top of `tests/`.
- `webpage/`: the MkDocs documentation site, a separate uv project.

## Commands

```bash
cd demandcast
uv sync --extra lstm                         # install all dependencies
uv run --extra lstm pytest                   # run the tests
uv run --extra lstm mypy                     # check the types
cd ..
uvx pre-commit run --all-files               # lint, format and check everything
cd webpage && uv run mkdocs build --strict   # build the documentation, if you changed it
```

Run the tests and the pre-commit hooks before you finish: CI runs both.

## Conventions

- Ruff formatting and linting, with lines of at most 79 characters (72 for docstrings and comments), NumPy-style docstrings and type hints, checked by mypy. Import pandas, NumPy and Matplotlib as `pd`, `np` and `plt`.
- Each script validates its YAML settings with a pydantic `ConfigModel`. Document new options in the YAML file and in `webpage/docs/`.
- Data source modules return a `pandas.Series` of demand in MW with a time-zone-aware index; stored timestamps are in UTC.
- Tests must not use the network: mock downloads (the `fake_downloads` fixture serves synthetic files to the functions of `utils.fetcher`) and write files to `tmp_path`. Mark the rare tests that need real downloaded data with `@pytest.mark.network`.
- The code must also work on Windows: build paths with `os.path.join` or `pathlib`, also in tests.
- Change dependencies in `pyproject.toml` and run `uv lock`; never edit `uv.lock` by hand.
- `README.md` is short and links to the documentation site, whose home page, `webpage/docs/index.md`, has the full text; `webpage/docs/architecture.md` describes the scripts, the folders and the dependency rule: update it when they change.
- Never commit data files (`data/`, `*.parquet`, `*.csv`; the small synthetic fixtures of the tests are fine) or `.env` files, which hold the API keys (`CDS_API_KEY`, `ENTSOE_API_KEY`, `EIA_API_KEY`, `ZENODO_API_KEY`, `SANDBOX_ZENODO_API_KEY`).

## pandas 3 pitfalls

- `to_numpy()` and `.values` can return read-only arrays (Copy-on-Write): create a new array instead of modifying it in place.
- Datetime resolution is inferred, often microseconds, while weather data uses nanoseconds: convert with `.as_unit("ns")` before merging or comparing timestamps from different sources.
- Text columns have the `str` dtype, so assigning numbers into them fails: replace the whole column, e.g. `df[col] = pd.to_numeric(df[col])`.
- Chained assignment such as `df[col][mask] = value` never changes `df`: use `df.loc[mask, col] = value`.

## Adding a data source or a model

The interfaces of a data source (its module and YAML file) and of a model are described once, in [CONTRIBUTING.md](CONTRIBUTING.md#adding-an-electricity-demand-data-source); follow them, and:

- keep the YAML file of a data source free of comments: explain the format of the data, its quirks and the entities left out in the docstring at the top of the module, and leave the dates of the data to the YAML file;
- use the helpers of `utils/` instead of copying their code, and follow `ons.py` or `hydroquebec.py`;
- add a test that parses a small synthetic fixture of the source's files, served by the `fake_downloads` fixture;
- for a model, add it to `MODEL_MODULES` in `ml_models/registry.py` and to the modules that mypy checks in `tests/ml_models/test_registry.py`; the module reads no file, the scripts pass its settings.

## Pull requests

- Titles follow [Conventional Commits](https://www.conventionalcommits.org/), e.g. `fix(assemble): keep all rows when merging datasets`.
- Every commit needs a DCO `Signed-off-by` line from the human contributor. Do not add it on their behalf unless they explicitly ask you to.
- Keep pull requests focused, and say in the description which AI tools were used and for what.
