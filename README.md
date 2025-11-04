<h1 align="center"><b>DemandCast</b></h1>

<h2 align="center"><b>Global hourly electricity demand forecasting</b></h2>

<h3 align="center"><b>A project developed by</b></h3>

<p align="center">
    <a href="https://openenergytransition.org/">
        <img src="webpage/docs/figures/oet_logo.png" alt="OET Logo" width="256"/>
    </a>
</p>

<h3 align="center"><b>Supported by</b></h3>

<p align="center">
    <a href="https://www.breakthroughenergy.org/">
        <img src="webpage/docs/figures/be_logo.png" alt="Breakthrough Energy Logo" width="512"/>
    </a>
</p>

<p align="center">
    <a href="https://open-energy-transition.github.io/demandcast/">
        <b>Documentation</b>
    </a>
</p>

## About

DemandCast is a Python-based project focused on collecting, processing, and forecasting hourly electricity demand data. The aim of this project is to support energy planning studies by using machine learning models to generate hourly time series of future electricity demand or for countries without available data.

### Features

- Retrieval of open hourly and sub-hourly electricity demand data from public sources ([ETL](https://github.com/open-energy-transition/demandcast/tree/main/ETL)).
- Retrieval of weather and socio-economic data ([ETL](https://github.com/open-energy-transition/demandcast/tree/main/ETL)).
- Forecasting using machine learning models ([models](https://github.com/open-energy-transition/demandcast/tree/main/models/)).
- Modular design for adding new countries or data sources.
- Support for reproducible, containerized development.

The project is in active development, we are always looking for suggestions and contributions!

## Repository structure

```
demandcast/
├── .github/                # Github specifics such as actions
├── ETL/                    # Scripts for extracting, transforming, and loading data
├── models/                 # Machine learning models for demand forecasting
├── webpage/                # Documentation website files (MkDocs)
├── .gitattributes          # Git attributes for handling line endings
├── .gitignore              # File lists that git ignores
├── .pre-commit-config.yaml # Pre-commit configuration
├── CONTRIBUTING.md         # Guide to contributing
├── LICENSE                 # License file
├── README.md               # Project overview and instructions
├── ruff.toml               # Ruff configuration
└── security.md             # Security policy
```

## DemandCast structure

![DemandCast](webpage/docs/figures/demandcast_illustration.png)

## Historical electricity demand collection progress

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="webpage/docs/figures/available_entities_dark_mode.png">
  <source media="(prefers-color-scheme: light)" srcset="webpage/docs/figures/available_entities_light_mode.png">
  <img alt="Countries and subdivisions for which retrieval scripts of electricity demand data are available" src="webpage/docs/figures/available_entities.png">
</picture>

Find the code that we used to retrieve the data in their respective files inside the [ETL](https://github.com/open-energy-transition/demandcast/tree/main/ETL) folder.

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/open-energy-transition/demandcast.git
cd demandcast
```

### 2. Set up your environment

This project uses [`uv`](https://github.com/astral-sh/uv) as a package manager to install the required dependencies and create an environment stored in `.venv`.

`uv` can be used within the provided Dockerfile or installed standalone (see [installing uv](https://docs.astral.sh/uv/getting-started/installation/)).

The `ETL` folder and each subfolder in the `models` directory—each representing a separate model—contain their own `pyproject.toml` files that define the dependencies for that module.

To set up the environment, run:
```bash
cd path/to/folder
uv sync
```

Alternatively, you may use a package manager of your choice (e.g., `conda`) to install the dependencies listed in the respective `pyproject.toml`. If you choose this approach, please adjust the commands below to align with the conventions of your selected package manager.

### 3. Run scripts

Scripts can be run directly using:

```bash
cd path/to/folder
uv run script.py
```

Jupyter notebooks ([details](https://docs.astral.sh/uv/guides/integration/jupyter/#using-jupyter-within-a-project)) can be launched with:

```bash
cd path/to/folder
uv run --with jupyter jupyter lab --allow-root
```

## Development workflow

### Run tests and check test coverage

```bash
cd path/to/folder
uv run pytest --cov=utils --cov-report=term-missing
```

### Pre-commit and lint code

To ensure code quality, we use [pre-commit](https://pre-commit.com/) hooks. These hooks automatically run checks on your code before committing changes. Among the pre-commit hooks, we also use [ruff](https://docs.astral.sh/ruff/) to enforce code style and linting. All the pre-commit hooks are defined in the `.pre-commit-config.yaml` file.

To run pre-commit hooks, you can use:
```bash
uvx pre-commit
```

## Documentation

The [documentation](https://open-energy-transition.github.io/demandcast/) is currently hosted on GitHub pages connected to this repository. It is built with [mkdocs](https://github.com/squidfunk/mkdocs-material).

To run it locally:

```bash
cd webpage
uv run mkdocs serve
```

## Maintainers

The project is maintained by the [Open Energy Transition](https://openenergytransition.org/) team. The team members currently involved in this project are:

- [Kevin Steijn](https://github.com/ElectricMountains) (kevin.steijn at openenergytransition dot org)
- [Vamsi Priya Goli](https://github.com/Vamsipriya22) (goli.vamsi at openenergytransition dot org)
- [Enrico Antonini](https://github.com/eantonini) (enrico.antonini at openenergytransition dot org)

## Contributing

We welcome contributions in the form of:

- Country-specific ETL modules
- New or improved forecasting models
- Documentation and testing enhancements

Please follow the repository’s structure and submit your changes via pull request.

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
