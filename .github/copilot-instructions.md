# DemandCast Copilot Instructions

## Repository Overview

**DemandCast** is a Python-based project for collecting, processing, and forecasting hourly electricity demand data globally. It supports energy planning studies using machine learning models to generate hourly time series of future electricity demand or for countries without available data.

- **Primary Language**: Python 3.12+
- **Package Manager**: `uv` (Astral package manager)
- **Repository Structure**: Single unified module in `demandcast/`
- **License**: AGPL-3.0

## Repository Structure

```
demandcast/
├── .github/
│   └── workflows/           # CI/CD pipelines
├── demandcast/             # Main code directory
│   ├── checks/             # Data availability and quality checks
│   ├── config/             # Configuration files for all scripts
│   ├── figures/            # Plotting modules and generated figures
│   ├── ml_models/          # Machine learning models for forecasting
│   ├── retrievals/         # Data retrieval modules
│   │   ├── electricity_demand_data_sources/  # Country-specific retrieval scripts
│   │   └── socio_economic_data_sources/      # Socio-economic data retrieval
│   ├── shapes/             # Scripts for non-standard subdivision shapes
│   ├── tests/              # Unit tests
│   ├── utils/              # Shared utilities
│   ├── assemble.py         # Data assembly script
│   ├── check.py            # Data checking script
│   ├── cross_validate.py   # Cross-validation script
│   ├── Dockerfile          # Docker configuration
│   ├── forecast.py         # Forecasting script
│   ├── plot.py             # Plotting script
│   ├── pyproject.toml      # Project dependencies
│   ├── retrieve.py         # Main data retrieval script
│   ├── train.py            # Model training script
│   ├── upload.py           # Data upload script
│   ├── uv.lock             # Locked dependencies
│   └── validate.py         # Model validation script
├── webpage/                # MkDocs documentation site
│   ├── docs/               # Documentation markdown files
│   ├── mkdocs.yml          # MkDocs configuration
│   └── pyproject.toml      # Documentation dependencies
├── ruff.toml               # Ruff linter/formatter config
├── .pre-commit-config.yaml # Pre-commit hooks config
└── README.md               # Project documentation
```

## Build and Development Workflow

### Environment Setup

The project uses a single unified environment in the `demandcast/` directory.

1. **Install `uv` package manager** (if not already installed):
   ```bash
   pip install uv
   ```

2. **Setup environment**:
   ```bash
   cd demandcast
   uv sync
   ```
   - This creates a `.venv` directory with all dependencies
   - Takes 30-60 seconds (includes geospatial, ML, and API libraries)

3. **Run scripts**:
   ```bash
   cd demandcast
   uv run <script.py> [--config path/to/config.yaml]
   ```
   - All scripts accept optional `--config` argument
   - Default configs are in `demandcast/config/`

**Note**: The `webpage/` directory has its own separate environment for building documentation.

### Testing

**Test Suite**:
```bash
cd demandcast
uv sync  # ALWAYS run before tests if .venv doesn't exist
uv run pytest --cov=utils --cov-report=term-missing
```
- Test suite takes ~37 seconds
- Requires 95% code coverage for `utils/` module only (enforced in CI)
- Some tests may fail in restricted network environments (expected)
- Tests are in `demandcast/tests/` directory

### Linting and Code Quality

**Pre-commit hooks** (includes ruff, mypy, prettier):
```bash
uvx pre-commit run --all-files
```
- Runs ruff linting with auto-fix
- Runs ruff formatting
- Runs mypy type checking
- Checks YAML, JSON files with prettier
- Strips Jupyter notebook outputs with nbstripout
- May require network access for initial setup

**Direct ruff usage** (if pre-commit has issues):
```bash
uvx ruff check --fix .
uvx ruff format .
```

**Configuration**:
- Ruff config: `ruff.toml` (root level, applies to all Python code)
- Target version: Python 3.12
- Line length: 79 characters (PEP 8)
- Docstring convention: NumPy style
- Key rules: import sorting, docstring linting, pandas linting

### Documentation

**Build and serve docs locally**:
```bash
cd webpage
uv sync  # First time only
uv run mkdocs serve
```
- Serves on `http://127.0.0.1:8000`
- Auto-reloads on file changes
- Documentation in `webpage/docs/` (markdown files)
- MkDocs Material theme

## Continuous Integration

### GitHub Actions Workflows

**CI Workflow** (`.github/workflows/ci.yml`):
- **Triggers**: On push to main, on all PRs
- **Jobs**:
  1. **pre-commit** (10 min timeout): Runs all pre-commit hooks
  2. **pytest** (10 min timeout): Runs tests with 95% coverage requirement for utils
- **Environment**: Single demandcast module

**Documentation Deployment** (`.github/workflows/docs.yml`):
- **Trigger**: Push to main branch
- **Action**: Builds and deploys MkDocs site to GitHub Pages
- Uses `mkdocs gh-deploy --force`

**Docker Build** (`.github/workflows/docker-publish.yml`):
- **Trigger**: Push to main, version tags, PRs
- **Images built**:
  - `ghcr.io/open-energy-transition/demandcast`
- Uses Python 3.12 base and includes Google Cloud CLI

## Project Details

### Scripts and Directory Structure

**Main Scripts and Configuration** (`demandcast/`):
- `retrieve.py` + `retrieve_config.yaml`: Collect electricity demand, weather, and socio-economic data
- `assemble.py` + `assemble_config.yaml`: Combine data for training or forecasting
- `train.py` + `train_config.yaml`, `ml_config.yaml`, `xgboost_config.yaml`: Train ML models
- `validate.py` + `validate_config.yaml`: Validate model performance
- `cross_validate.py` + `cross_validate_config.yaml`: Leave-one-group-out cross-validation
- `forecast.py` + `forecast_config.yaml`: Generate forecasts
- `plot.py` + `plot_config.yaml`: Generate visualizations
- `check.py`: Data quality checks
- `upload.py` + `upload_config.yaml`: Upload data to cloud storage

**Key Directories** (`demandcast/`):
- `retrievals/`: Data source modules (40+ country-specific scripts in `electricity_demand_data_sources/`)
- `ml_models/`: Machine learning implementations (currently XGBoost only)
- `utils/`: Shared utilities (config, entities, fetcher, geospatial, ml, time_series, uploader)
- `tests/`: Unit tests (95%+ coverage requirement for utils)
- `config/`: YAML configuration files for all scripts

**Documentation** (`webpage/`):
- Built with MkDocs Material theme
- Main docs: `docs/index.md`, `docs/getting_started.md`, `docs/retrieval.md`, `docs/ML.md`, `docs/plot.md`, `docs/Dockerfile.md`
- Separate environment from main module

**Configuration Pattern**:
- All scripts accept only `--config` argument pointing to YAML files in `demandcast/config/`
- Dependency management via `uv` with committed lock file (`uv.lock`)

### Dependencies

**Main Module** (`demandcast/`):
- **Geospatial**: geopandas, cartopy, rasterio, shapely, pyproj
- **Data processing**: pandas, polars, numpy, xarray, pyarrow
- **APIs**: entsoe-py, cdsapi, google-cloud-storage
- **ML**: xgboost-cpu, scikit-learn, dask
- **Testing**: pytest, pytest-cov
- Total: ~100+ packages

**Webpage** (minimal dependencies):
- mkdocs-material (includes all needed plugins)
- ~29 total packages

### Common Issues and Workarounds

1. **Network-related test failures**: Some tests download geospatial data from external sources (naturalearth.s3.amazonaws.com). These may fail in restricted environments but work in CI.

2. **Pre-commit network issues**: Initial pre-commit setup requires downloading hook repositories. If this fails, you can use `uvx ruff` directly for linting.

3. **Coverage requirements**: Pytest must achieve 95% coverage for utils (`--cov-fail-under=95`). Check coverage report output if changes drop below this threshold.

4. **Ruff line length**: Code must adhere to 79-character line length (PEP 8). Ruff auto-format handles this.

5. **Docker builds**: Dockerfile is in `demandcast/Dockerfile`. It installs Google Cloud CLI and uses `uv sync --frozen` for reproducible builds.

## Validation Steps

Before submitting changes:

1. **Lint your code**:
   ```bash
   uvx pre-commit run --all-files
   ```

2. **Run tests** (for code changes):
   ```bash
   cd demandcast
   uv run pytest --cov=utils --cov-report=term-missing --cov-fail-under=95
   ```

3. **Check documentation builds** (for doc changes):
   ```bash
   cd webpage
   uv sync  # First time only
   uv run mkdocs build
   ```

## Important Notes

- **Coverage is enforced**: Utils must maintain 95% test coverage
- **Docstrings are required**: NumPy style docstrings enforced by ruff
- **Line length**: 79 characters for code, 72 for docstrings/comments
- **Type hints**: Encouraged but mypy is lenient (ignores missing imports)

## Trust These Instructions

These instructions have been validated by running all commands and observing their behavior. Only perform searches or exploration if:
- Information here is incomplete or unclear
- You encounter errors not documented here
- You need details about specific data sources or model implementations

When in doubt, trust the module structure and use `uv` commands as documented above.
