# Contributing to DemandCast

Thank you for helping improve DemandCast! We welcome new data sources, models, bug fixes, tests and documentation. Issues labelled [good first issue](https://github.com/open-energy-transition/demandcast/labels/good%20first%20issue) are a good place to start.

By participating, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions, bugs and ideas

- **Questions**: use [GitHub Discussions](https://github.com/open-energy-transition/demandcast/discussions).
- **Bugs, feature requests and new data sources**: [open an issue](https://github.com/open-energy-transition/demandcast/issues/new/choose) using one of the templates.
- **Security vulnerabilities**: do not open a public issue; follow the [security policy](https://github.com/open-energy-transition/demandcast/security/policy).

For larger changes, please open an issue first so that we can agree on the approach before you invest time in it.

## Development setup

DemandCast uses [uv](https://docs.astral.sh/uv/) to manage Python and dependencies.

```bash
git clone https://github.com/<your-username>/demandcast.git  # your fork
cd demandcast/demandcast
uv sync --extra lstm  # create .venv with all dependencies, including the LSTM model
```

Some retrieval modules need API keys in a `demandcast/.env` file; see the [getting started guide](https://open-energy-transition.github.io/demandcast/getting_started/). Never commit this file.

We use [pre-commit](https://pre-commit.com/) to lint, format and check files before each commit:

```bash
uvx pre-commit install          # run the hooks automatically on every commit
uvx pre-commit run --all-files  # run them on the whole repository
```

## Making changes

1. Create a branch from `main` in your fork.
2. Follow the existing style: [Ruff](https://docs.astral.sh/ruff/) formatting and linting (lines of at most 79 characters), NumPy-style docstrings and type hints, checked by mypy. The pre-commit hooks check this for you.
3. Add or update tests for your changes in `demandcast/tests/`, whose folders mirror the code (the tests of `utils/ml.py` are in `tests/utils/test_ml.py`), and run them from the `demandcast/` folder:

   ```bash
   uv run --extra lstm pytest
   ```

   CI also checks that the lines you change are covered by tests.

4. Update the documentation in `webpage/docs/` if you change how something works.

### Adding an electricity demand data source

Each source is a module in `demandcast/retrievals/electricity_demand_data_sources/` with a YAML file listing its countries or subdivisions (ISO 3166 names and codes, time zones and data period). A module provides `redistribute()`, `get_url()`, `get_available_requests(code, start_date, end_date)` and `download_and_extract_data_for_request(request, code)`: the retrieval code passes the code of a country or subdivision and the dates of its data from the YAML file, and then each request with the code. A source that downloads all its data at once returns a single request, `None`. The module returns the demand in MW, with time-zone-aware times that mark the end of each interval. `ons.py` and `hydroquebec.py` are templates; the other modules are moving to this interface. Please also add:

- a small **synthetic** test fixture that mimics the source's file format, in `demandcast/tests/retrievals/electricity_demand_data_sources/fixtures/`, and a test `test_<source>.py` next to it that parses it: the `fake_downloads` fixture serves the file instead of the download, and `assert_demand` checks the result (see `test_aemo_nem.py` and [#161](https://github.com/open-energy-transition/demandcast/issues/161));
- shapes for non-standard subdivisions in `demandcast/shapes/`, if needed;
- the source to `demandcast/run_all.sh`.

### Adding a machine learning model

Each model is a module in `demandcast/ml_models/` that provides the interface of `ModelModule` in `demandcast/ml_models/registry.py`: `get_initialized_model()`, `train()`, `predict()`, `save()` and `load()`, and the extension of its saved files. Its settings go in `demandcast/config/<model>_config.yaml`; `ml_models/xgboost.py` is a good template. Please also:

- add the module to `MODEL_MODULES` in `ml_models/registry.py`, and to the modules that mypy checks in `demandcast/tests/ml_models/test_registry.py`, whose contract test then trains, saves, loads and predicts with the model;
- put heavy dependencies in an optional extra in `demandcast/pyproject.toml`, like `lstm`;
- describe the model in `webpage/docs/ML.md`.

The scripts then use the model when `algorithm` in `demandcast/config/ml_config.yaml` is its name.

## Commits and pull requests

### Sign off your commits (DCO)

Every commit must be signed off to certify that you have the right to submit it under the project's license, as described in the [Developer Certificate of Origin](https://developercertificate.org/). Add `-s` when committing:

```bash
git commit -s -m "feat(retrievals): add Nordpool data source"
```

This appends `Signed-off-by: Your Name <your@email>` to the commit message, using your git name and email. If you forgot, sign off all the commits of your branch and update your pull request:

```bash
git rebase --signoff origin/main
git push --force-with-lease
```

When you commit on GitHub's website, GitHub signs off your commits for you.

### Pull request titles

Pull requests are squash-merged, and their title becomes the commit message on `main`. Titles must follow [Conventional Commits](https://www.conventionalcommits.org/): `type(optional scope): description`, for example:

- `feat(retrievals): add Nordpool data source`
- `fix(assemble): keep all rows when merging datasets`
- `docs: explain how to add a data source`

Common types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci` and `chore`. Add `!` after the type for breaking changes (`feat(ml)!: ...`).

### Review

Fill in the pull request template. On pull requests from forks, CI starts once a maintainer approves it. A maintainer reviews every pull request. Before it is merged, all CI checks must pass and every review conversation must be resolved, including the automatic comments of GitHub Code Quality. For mechanical changes to untested code, such as renames or lint fixes, maintainers can skip the check of the changed lines with the `skip-diff-cover` label. Please keep pull requests focused: several small ones are easier to review than a large one.

## AI-assisted contributions

You may use AI tools to help with your contribution, provided that:

- you say so in the pull request description (which tool, and for what);
- you have reviewed, understood and tested every change, and can explain it during review;
- you are responsible for the contribution: your DCO sign-off certifies that you have the right to submit it.

Please don't open pull requests or issues generated by AI tools without your own review.

## License

By contributing, you agree that your contributions are licensed under the project's [AGPL-3.0 license](LICENSE).
