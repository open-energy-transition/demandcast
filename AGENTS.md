# AGENTS.md

Instructions for AI coding agents working on DemandCast. Human contributors should read [CONTRIBUTING.md](CONTRIBUTING.md).

## Project

DemandCast retrieves hourly electricity demand, weather and socio-economic data from public sources, and trains machine learning models (XGBoost, and an optional LSTM) to forecast hourly electricity demand for countries and subdivisions. It is a Python 3.12+ project managed with [uv](https://docs.astral.sh/uv/).

## Layout

- `demandcast/`: the Python project; run Python commands from this folder.
  - `retrieve.py`, `assemble.py`, `train.py`, `validate.py`, `cross_validate.py`, `forecast.py`, `plot.py`, `check.py`, `upload.py`: pipeline scripts, each configured by `config/<script>_config.yaml` (another file can be passed with `--config`).
  - `retrievals/`: data retrieval. Each electricity demand source is a module plus a YAML file in `retrievals/electricity_demand_data_sources/`.
  - `ml_models/`: models sharing one interface (`get_initialized_model`, `train`, `predict`, `save`, `load`).
  - `utils/`: shared helpers; CI requires at least 95% test coverage.
  - `tests/`: the pytest suite.
  - `archive/`: legacy notebooks and scripts; do not modify.
- `webpage/`: the MkDocs documentation site, a separate uv project.

## Commands

```bash
cd demandcast
uv sync --extra lstm             # install all dependencies
uv run --extra lstm pytest       # run the tests
cd ..
uvx pre-commit run --all-files   # lint, format and check everything
```

## Conventions

- Ruff formatting and linting, with lines of at most 79 characters (72 for docstrings and comments), NumPy-style docstrings and type hints.
- Scripts read their settings from YAML files, validated with pydantic models.
- Data source modules return a `pandas.Series` of demand in MW with a time-zone-aware index; stored timestamps are in UTC.
- Add tests for every change, and mock network access: tests must not download data.
- Change dependencies in `pyproject.toml` and run `uv lock`; never edit `uv.lock` by hand.
- Never commit data files (`data/`, `*.parquet`, `*.csv`) or `.env` files.

## Pull requests

- Titles follow [Conventional Commits](https://www.conventionalcommits.org/), e.g. `fix(assemble): keep all rows when merging datasets`.
- Every commit needs a DCO `Signed-off-by` line from the human contributor. Do not add it on their behalf unless they explicitly ask you to.
- Keep pull requests focused, and say in the description which AI tools were used and for what.
