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
3. Add or update tests for your changes in `demandcast/tests/`, whose folders mirror the code (the tests of `utils/fetcher.py` are in `tests/utils/test_fetcher.py`), and run them from the `demandcast/` folder:

   ```bash
   uv run --extra lstm pytest
   ```

   CI also checks that the lines you change are covered by tests.

4. Build paths with `utils/paths.py` and take scenarios, climate models and years from `utils/catalogue.py`, instead of writing them again. The modules of `utils/` import none of the other packages (`tests/utils/test_dependencies.py` checks it).
5. Update the documentation in `webpage/docs/` if you change how something works.

### Adding an electricity demand data source

This section is the reference for the interface of a data source. Each source is a module, `<source>.py`, and a YAML file, `<source>.yaml`, in `demandcast/retrievals/electricity_demand_data_sources/`; `ons.py` and `hydroquebec.py` are good templates.

The module provides two functions, which the retrieval code calls:

- `get_available_requests(code, start_date, end_date)` gives the requests of a country or subdivision, in chronological order, from its code and the dates of its data in the YAML file. A source that downloads all its data at once returns a single request, `None`.
- `download_and_extract_data_for_request(request, code)` downloads the data of a request and returns a `pandas.Series` of the demand in MW, with time-zone-aware times that mark the end of each interval.

A `get_url` helper that builds the URL of a request is optional, with the parameters that fit the source. The shared helpers in `utils/` cover the common steps, so use them instead of copying their code: `fetcher.fetch_dataframe`, `fetcher.fetch_text`, `fetcher.fetch_excel_file` and `fetcher.fetch_response` (one for each type of result), `fetcher.read_manual_files` for files downloaded by hand, with `time_series.keep_latest_download` to combine several downloads of the same data, `config.read_api_key`, `time_series.split_period` for the periods of the requests, and `time_series.localize_interval_starts`, which moves the starts of intervals in local time to their ends. The docstring at the top of the module explains the format of the data, its quirks, its time zone and the entities left out; leave the dates of the data to the YAML file.

The YAML file has no comments, and gives:

- the `licence` of the data: `redistribute`, whether its terms allow the data to be redistributed, `terms`, a summary of the licence, and `url`, its link;
- the `definition` of its demand, what it counts: a list of periods, in the order of their `start_date`, the first one from the start of the data, each with the `quantity` that the source gives, and whether the `embedded_generation`, the `network_losses`, the `storage_charging` and the `power_plant_use` are `included` by the source, `added` by DemandCast from an estimate, `partial` (counted only in part), `excluded` or `unknown`, with a `note` on the reasons (see [gross demand](https://open-energy-transition.github.io/demandcast/retrieval/#gross-demand));
- `compiled: true` for a source that republishes the data of the system operators, such as the EIA;
- its `entities`, each with `country_name` and `country_code` (ISO 3166 alpha-3), and for a subdivision `subdivision_name`, `subdivision_code` and `time_zone`, with the dates of its data, `start_date` and `end_date` (a date or `today`). Standard subdivisions have ISO 3166 codes, and the others a widely accepted name and code, with their shapes made by a script in `demandcast/shapes/`. An entity whose data covers only part of the area of its shape has `same_area: false`.

`cleaning/combining.py` uses `definition`, `compiled` and `same_area` to rank the sources of a code. Please also add a small **synthetic** test fixture that mimics the source's file format, in `demandcast/tests/retrievals/electricity_demand_data_sources/fixtures/`, and a test `test_<source>.py` next to it that parses it: the `fake_downloads` fixture serves the file instead of the download, and `assert_demand` checks the result (see `test_aemo_nem.py` and [#161](https://github.com/open-energy-transition/demandcast/issues/161)).

To check a source over the network, set `data_sources` in `demandcast/config/check_data_sources_config.yaml` and run `uv run check.py --config config/check_data_sources_config.yaml`: the live check downloads the latest request and checks its values and times.

### Adding a machine learning model

This section is the reference for the interface of a model. Each model is a module in `demandcast/ml_models/` that provides the interface of `ModelModule` in `demandcast/ml_models/registry.py`: a `ConfigModel` of its settings, `get_initialized_model(config)`, `train(prepared_dataset, config)`, `predict()`, `save(model, file_path)` and `load(file_path)`, and the extension of its saved files. Its settings go in `demandcast/config/<model>_config.yaml`, which the scripts read with `ml_models.registry.read_model_configuration` and pass to the module, so the module reads no file itself; its `ConfigModel` derives from `utils.config.StrictSettings`, which rejects unknown settings, and bounds the values of its settings. The prepared dataset that `train` and `predict` get has, aligned row by row, the `features`, the `target` (in training and validation), the entity codes (`group`), the times (`time`), the local years and the scaling factors: the same fields in training, validation, cross-validation and forecasting, so a model can rely on any of them, such as the times to break its sequences at the gaps. A model that fits a preprocessing of its features, such as a standardization, saves it with the model, and exposes its statistics in `mean_` and `scale_` for the manifest of the model. `ml_models/xgboost.py` is a good template. Please also:

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
