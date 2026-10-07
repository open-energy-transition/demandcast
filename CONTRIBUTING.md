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
2. Follow the existing style: [Ruff](https://docs.astral.sh/ruff/) formatting and linting (lines of at most 79 characters), NumPy-style docstrings and type hints. The pre-commit hooks check this for you.
3. Add or update tests for your changes and run them from the `demandcast/` folder:

   ```bash
   uv run --extra lstm pytest
   ```

   CI also checks that the lines you change are covered by tests.

4. Update the documentation in `webpage/docs/` if you change how something works.

### Adding an electricity demand data source

Each source is a module in `demandcast/retrievals/electricity_demand_data_sources/` with a YAML file listing its countries or subdivisions (ISO 3166 names and codes, time zones and data period). A module provides `redistribute()`, `get_available_requests()`, `get_url()` and `download_and_extract_data()` (or `download_and_extract_data_for_request()`), and returns demand in MW with UTC timestamps; existing modules are good templates. Please also add:

- a small **synthetic** test fixture that mimics the source's file format, and a test that parses it (see [#161](https://github.com/open-energy-transition/demandcast/issues/161));
- shapes for non-standard subdivisions in `demandcast/shapes/`, if needed;
- the source to `demandcast/run_all.sh`.

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

### Pull request titles

Pull requests are squash-merged, and their title becomes the commit message on `main`. Titles must follow [Conventional Commits](https://www.conventionalcommits.org/): `type(optional scope): description`, for example:

- `feat(retrievals): add Nordpool data source`
- `fix(assemble): keep all rows when merging datasets`
- `docs: explain how to add a data source`

Common types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci` and `chore`. Add `!` after the type for breaking changes (`feat(ml)!: ...`).

### Review

Fill in the pull request template. A maintainer reviews every pull request, and all CI checks must pass before it is merged. For mechanical changes to untested code, such as renames or lint fixes, maintainers can skip the check of the changed lines with the `skip-diff-cover` label. Please keep pull requests focused: several small ones are easier to review than a large one.

## AI-assisted contributions

You may use AI tools to help with your contribution, provided that:

- you say so in the pull request description (which tool, and for what);
- you have reviewed, understood and tested every change, and can explain it during review;
- you are responsible for the contribution: your DCO sign-off certifies that you have the right to submit it.

Please don't open pull requests or issues generated by AI tools without your own review.

## License

By contributing, you agree that your contributions are licensed under the project's [AGPL-3.0 license](LICENSE).
