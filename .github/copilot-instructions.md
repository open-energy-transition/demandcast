# DemandCast Copilot Instructions

## Repository Overview

**DemandCast** is a Python-based project for collecting, processing, and forecasting hourly electricity demand data globally. It supports energy planning studies using machine learning models to generate hourly time series of future electricity demand or for countries without available data.

- **Primary Language**: Python 3.12+
- **Package Manager**: `uv` (Astral package manager)
- **Repository Size**: ~6,300 Python files, modular architecture
- **License**: AGPL-3.0

## Repository Structure

```
demandcast/
├── ETL/                     # Extract, Transform, Load data pipelines
│   ├── pyproject.toml       # ETL module dependencies
│   ├── retrieve.py          # Main ETL script
│   ├── retrievals/          # Data source retrieval scripts
│   ├── utils/               # ETL utility functions
│   └── tests/               # ETL test suite
├── models/                  # Machine learning models
│   └── xgboost/             # XGBoost model implementation
│       ├── pyproject.toml   # Model dependencies
│       ├── inference.py     # Model inference script
│       └── serve.py         # Model serving API
├── webpage/                 # MkDocs documentation site
│   ├── docs/                # Documentation markdown files
│   ├── mkdocs.yml           # MkDocs configuration
│   └── pyproject.toml       # Docs dependencies
├── .github/
│   └── workflows/           # CI/CD pipelines
├── ruff.toml                # Ruff linter/formatter config
├── .pre-commit-config.yaml  # Pre-commit hooks config
└── README.md                # Project documentation
```

## Build and Development Workflow

### Environment Setup

**CRITICAL**: Each subfolder (ETL, models/xgboost, webpage) has its own `pyproject.toml` and requires separate environment setup.

1. **Install `uv` package manager** (if not already installed):
   ```bash
   pip install uv
   ```

2. **Setup environment for a specific module**:
   ```bash
   cd <module-path>  # e.g., cd ETL or cd models/xgboost
   uv sync
   ```
   - This creates a `.venv` directory with all dependencies
   - Takes 30-60 seconds for ETL module (many dependencies)
   - Takes 10-20 seconds for webpage module (fewer dependencies)

3. **Run scripts in the module environment**:
   ```bash
   cd <module-path>
   uv run <script.py>
   ```

### Testing

**ETL Module Tests**:
```bash
cd ETL
uv sync  # ALWAYS run before tests if .venv doesn't exist
uv run pytest --cov=utils --cov-report=term-missing
```
- Test suite takes ~37 seconds
- Requires 95% code coverage (enforced in CI)
- Some tests may fail in restricted network environments (expected)
- Tests are in `ETL/tests/` directory

**Note**: There are currently no test suites for the `models/xgboost` or `webpage` modules.

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
  2. **pytest-ETL** (10 min timeout): Runs ETL tests with 95% coverage requirement
- **Matrix testing**: Currently only tests ETL module

**Documentation Deployment** (`.github/workflows/docs.yml`):
- **Trigger**: Push to main branch
- **Action**: Builds and deploys MkDocs site to GitHub Pages
- Uses `mkdocs gh-deploy --force`

**Docker Build** (`.github/workflows/docker-publish.yml`):
- **Trigger**: Push to main, version tags, PRs
- **Images built**:
  - `ghcr.io/open-energy-transition/demandcast-etl`
  - `ghcr.io/open-energy-transition/demandcast-xgboost`
- Both use Python 3.12 base and include Google Cloud CLI

### Pre-commit Hooks

Defined in `.pre-commit-config.yaml`:
1. Basic file hygiene (trailing whitespace, EOF newlines, merge conflicts)
2. Ruff linter/formatter (auto-fix enabled)
3. Prettier for YAML/JSON
4. Mypy type checker (ignores missing imports)
5. nbstripout for Jupyter notebooks

## Key Development Facts

### Project Layout Details

**ETL Module** (`ETL/`):
- Main entry point: `retrieve.py` (CLI for data retrieval)
- Data sources: `retrievals/electricity_demand_data_sources/` (40+ country-specific scripts)
- Utilities: `utils/` (directories, entities, fetcher, geospatial, shapes, time_series, uploader)
- Key utilities have 95%+ test coverage
- Run all retrievals: `./run_all.sh` (batch script for all data sources)

**Models** (`models/`):
- Currently contains only XGBoost model
- Includes Jupyter notebooks for development
- `inference.py`: Model inference script
- `serve.py`: FastAPI-based model serving

**Common Patterns**:
- Each module manages its own virtual environment
- Python 3.12 is the target version (see `.python-version` files)
- All modules use `uv` for dependency management
- Lock files (`uv.lock`) are committed to version control

### Dependencies

**ETL Module** (heavy dependencies):
- Geospatial: geopandas, cartopy, rasterio, shapely, pyproj
- Data processing: pandas, numpy, xarray, pyarrow
- APIs: entsoe-py, cdsapi, google-cloud-storage
- ~94 total packages installed

**XGBoost Model** (lighter dependencies):
- ML: xgboost-cpu, scikit-learn
- Data: pandas, xarray, dask
- Serving: fastapi
- ~20 total packages

**Webpage** (minimal dependencies):
- mkdocs-material (includes all needed plugins)
- ~29 total packages

### Common Issues and Workarounds

1. **Network-related test failures**: Some tests download geospatial data from external sources (naturalearth.s3.amazonaws.com). These may fail in restricted environments but work in CI.

2. **Pre-commit network issues**: Initial pre-commit setup requires downloading hook repositories. If this fails, you can use `uvx ruff` directly for linting.

3. **Module isolation**: ALWAYS `cd` into the correct module directory (ETL, models/xgboost, or webpage) before running `uv sync` or `uv run` commands. The `.venv` is module-specific.

4. **Coverage requirements**: The ETL pytest must achieve 95% coverage (`--cov-fail-under=95`). Check coverage report output if changes drop below this threshold.

5. **Ruff line length**: Code must adhere to 79-character line length (PEP 8). Ruff auto-format handles this.

6. **Docker builds**: Dockerfiles are in each module (ETL/Dockerfile, models/xgboost/Dockerfile). They install Google Cloud CLI and use `uv sync --frozen` for reproducible builds.

## Validation Steps

Before submitting changes:

1. **Lint your code**:
   ```bash
   uvx ruff check --fix .
   uvx ruff format .
   ```

2. **Run tests** (for ETL changes):
   ```bash
   cd ETL
   uv run pytest --cov=utils --cov-report=term-missing --cov-fail-under=95
   ```

3. **Check documentation builds** (for doc changes):
   ```bash
   cd webpage
   uv run mkdocs build
   ```

4. **Verify pre-commit passes** (optional but recommended):
   ```bash
   uvx pre-commit run --all-files
   ```

## Important Notes

- **Always use `uv run`** instead of activating virtual environments directly
- **Module-specific commands**: Navigate to the correct module directory first
- **Coverage is enforced**: ETL utils must maintain 95% test coverage
- **Docstrings are required**: NumPy style docstrings enforced by ruff
- **Line length**: 79 characters for code, 72 for docstrings/comments
- **Type hints**: Encouraged but mypy is lenient (ignores missing imports)

## Trust These Instructions

These instructions have been validated by running all commands and observing their behavior. Only perform searches or exploration if:
- Information here is incomplete or unclear
- You encounter errors not documented here
- You need details about specific data sources or model implementations

When in doubt, trust the module structure and use `uv` commands as documented above.
