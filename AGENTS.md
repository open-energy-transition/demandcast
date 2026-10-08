# AGENTS.md

Instructions for AI coding agents working on DemandCast. Human contributors should read [CONTRIBUTING.md](CONTRIBUTING.md).

## Project

DemandCast retrieves hourly electricity demand, weather and socio-economic data from public sources, and trains machine learning models (XGBoost, and an optional LSTM) to forecast hourly electricity demand for countries and subdivisions. It is a Python 3.12+ project managed with [uv](https://docs.astral.sh/uv/).

## Pipeline

Each step is a script in `demandcast/`, configured by `config/<script>_config.yaml` (pass another file with `--config`):

1. `retrieve.py` downloads demand, weather and socio-economic data into `data/<variable>/`.
2. `assemble.py` merges the retrieved data into one dataset for training or forecasting, in `data/assembled/`.
3. `train.py` trains a model; `validate.py` evaluates it on each entity's most recent year, and `cross_validate.py` on entities left out of training.
4. `forecast.py` predicts hourly demand in MW with a trained model.
5. `plot.py`, `check.py` and `upload.py` draw figures, check data availability, and upload data to Google Cloud Storage and Zenodo.

Folder locations are defined in `config/directories_config.yaml`; use `utils.config.read_folders_structure()` instead of hard-coding paths.

## Layout

- `demandcast/`: the Python project. Run all Python commands from this folder, because modules are imported as top-level packages (`import utils.config`, not `import demandcast.utils.config`).
  - `retrievals/`: data retrieval. Each electricity demand source is a module plus a YAML file in `retrievals/electricity_demand_data_sources/`.
  - `ml_models/`: the models. `registry.py` lists them and defines the interface of their modules (`ModelModule`).
  - `utils/`: shared helpers; CI requires at least 95% test coverage.
  - `tests/`: the pytest suite, in folders that mirror the code: the tests of `utils/ml.py` are in `tests/utils/test_ml.py`, and those of the scripts are at the top of `tests/`.
  - `archive/`: legacy notebooks and scripts; do not modify.
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
- Tests must not use the network: mock downloads (for example `utils.fetcher.fetch_data`) and write files to `tmp_path`. Mark the rare tests that need real downloaded data with `@pytest.mark.network`.
- The code must also work on Windows: build paths with `os.path.join` or `pathlib`, also in tests.
- Change dependencies in `pyproject.toml` and run `uv lock`; never edit `uv.lock` by hand.
- `README.md` and `webpage/docs/index.md` share most of their content: update both.
- Never commit data files (`data/`, `*.parquet`, `*.csv`; the small synthetic fixtures of the tests are fine) or `.env` files, which hold the API keys (`CDS_API_KEY`, `ENTSOE_API_KEY`, `EIA_API_KEY`, `ZENODO_API_KEY`, `SANDBOX_ZENODO_API_KEY`).

## pandas 3 pitfalls

- `to_numpy()` and `.values` can return read-only arrays (Copy-on-Write): create a new array instead of modifying it in place.
- Datetime resolution is inferred, often microseconds, while weather data uses nanoseconds: convert with `.as_unit("ns")` before merging or comparing timestamps from different sources.
- Text columns have the `str` dtype, so assigning numbers into them fails: replace the whole column, e.g. `df[col] = pd.to_numeric(df[col])`.
- Chained assignment such as `df[col][mask] = value` never changes `df`: use `df.loc[mask, col] = value`.

## Adding a data source

1. Add `retrievals/electricity_demand_data_sources/<source>.py` with `redistribute()`, `get_available_requests()`, `get_url()` and `download_and_extract_data()` (or `download_and_extract_data_for_request()`). Follow an existing module.
2. Add `<source>.yaml` listing its entities: `country_name` and `country_code` (ISO 3166 alpha-3), `subdivision_name`, `subdivision_code` and `time_zone` for subdivisions, and `start_date` and `end_date` (a date or `today`).
3. Add shapes for non-standard subdivisions in `shapes/`, the source to `run_all.sh`, and a test that parses a small synthetic fixture of the source's files: `tests/retrievals/electricity_demand_data_sources/test_<source>.py`, with the fixture in its `fixtures/` folder, served by the `fake_downloads` fixture (see `test_aemo_nem.py` and issue #161).

## Adding a model

1. Add `ml_models/<model>.py` with the interface of `ModelModule` in `ml_models/registry.py`, and its settings in `config/<model>_config.yaml`, validated with pydantic.
2. Add the module to `MODEL_MODULES` in `ml_models/registry.py`, and to the modules that mypy checks in `tests/ml_models/test_registry.py`, whose contract test then runs the model.
3. Put heavy dependencies in an optional extra in `pyproject.toml`, like `lstm`.

## Pull requests

- Titles follow [Conventional Commits](https://www.conventionalcommits.org/), e.g. `fix(assemble): keep all rows when merging datasets`.
- Every commit needs a DCO `Signed-off-by` line from the human contributor. Do not add it on their behalf unless they explicitly ask you to.
- Keep pull requests focused, and say in the description which AI tools were used and for what.
