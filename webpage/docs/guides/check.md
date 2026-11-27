# Run checks

`check.py` runs one of four checks of the data and of the inputs of the code.

| Check | What it does | When to run it | Network? | Writes |
|---|---|---|---|---|
| [`data_availability`](#data-availability) | Lists which countries and subdivisions have the socio-economic data the models need | After adding a shape, or when the World Bank, Ember, IMF or IIASA data changes | Yes | `checks/data_availability_summary.csv` |
| [`data_sources`](#live-check-of-the-data-sources) | Downloads a sample of each electricity demand data source and checks it | When a retrieval fails; weekly on GitHub | Yes | `data/results/checks/data_sources_report.json` and `.md` |
| [`flags`](#report-of-the-flags) | Gathers the flags of the cleaned electricity demand and compares them with their reviews | After retrieving electricity demand | No | `data/results/checks/flags_report.csv` and `.md` |
| [`related_entities`](#related-entities) | Computes which countries and subdivisions share people | After adding a code to a data source or changing a shape | Once, for the gridded population | `checks/related_entities.csv` and `checks/related_entities_codes.txt` |

`checks/` is in the code folder (`demandcast/checks/`): commit its files after the check. `data/` is the [data folder](../reference/data-folder.md).

## Run check.py

Each check has its own settings file. From the `demandcast/` folder:

```bash
uv run check.py                                                # check of config/check_config.yaml
uv run check.py --config config/check_data_sources_config.yaml # live check of the data sources
uv run check.py --config config/check_flags_config.yaml        # report of the flags
```

`config/check_config.yaml` holds `check: data_availability`. Set `check: related_entities` there, or in your own file, for that check. `config/check_flags_config.yaml` holds only `check: flags`. Each run logs to `data/logs/checks_<time>.log`; nothing is printed on the screen.

## Options

All options but `check` apply only to `data_sources`; the other checks accept and ignore them.

| Option | Default | In `check_data_sources_config.yaml` | What it does |
|---|---|---|---|
| `check` | required | `data_sources` | The check: `data_availability`, `data_sources`, `flags` or `related_entities`. |
| `data_sources` | all | empty (all) | The data sources to check, such as `[ons, hydroquebec]`. An unknown name stops the check. |
| `maximum_age_days` | `60` | `60` | How old, in days, the latest value of a source whose `end_date` is `today` may be. Most sources publish within weeks. |
| `maximum_age_days_by_source` | none | `caiso: 180`, `tsoc: 700` | Another `maximum_age_days` for some sources. CAISO publishes a month one to four months after it ends. TSOC publishes a yearly file five weeks to nine months after the year ends, so its latest value can be almost two years old. |
| `time_limit_minutes` | `15` | `15` | After this time, every source that has not answered fails, so a silent website cannot keep the check from ending. |
| `skipped_data_sources` | none | `tepco: Its website refuses the requests from the runners of GitHub Actions.` | Sources not to check, each with the reason shown in the report. TEPCO answers GitHub Actions runners, where the weekly check runs, with HTTP 403; OCCTO gives the same demand of the Kantō area. |

## Data availability

This check decides which countries and subdivisions the other scripts work on, from the socio-economic data that exists for them. It writes `checks/data_availability_summary.csv`.

### What it computes

It takes every code with a shape: the countries and standard subdivisions of Natural Earth, and the non-standard subdivisions of `shapes/subdivisions/`. A country code that is not an official ISO 3166 alpha-3 code stops it with an error (Kosovo, `XKX`, is added to the list).

For each code, it checks six indicators and the area of the shape, in an equal-area projection. A subdivision has the data per capita of its country, which is assumed to be the same everywhere in it, but never the population of its country.

### Columns of data_availability_summary.csv

| Column | Meaning |
|---|---|
| `entity_code` | The code, such as `FRA` or `USA_CAL`. |
| `entity_name` | The name of the country, or `Subdivision of <country>`. |
| `historical_population` | `True` if the World Bank (downloaded) has the code. |
| `historical_electricity_demand_per_capita` | `True` if Ember or the World Bank (downloaded; needs `EMBER_API_KEY`) has the country. |
| `historical_gdp_ppp_per_capita` | `True` if the World Bank or the IMF (downloaded) has the country. |
| `<indicator>_first_year`, `<indicator>_last_year` | First and last years with a value, for each historical indicator. Empty for a subdivision's population. |
| `future_population`, `future_gdp_ppp_per_capita` | `True` if the IIASA SSP database (a file in the repository) has the code (or its country, for GDP PPP per capita). |
| `future_electricity_demand_per_capita` | `True` if `iam_regions_mapping.yaml` maps the country to a region of the IIASA projections. |
| `area_greater_than_500_km2` | `True` if the area is at least 500 km². |

### How the other scripts use it

`utils/availability.py` selects the codes that have either:

- the population, the electricity demand per capita and the GDP PPP per capita; or
- the electricity demand per capita and an area of at least 500 km². Their population and GDP PPP per capita come from the gridded data (see [Inputs](../concepts/inputs.md)).

| List | Needs | Used by |
|---|---|---|
| Codes with historical data | The historical columns | `retrieve.py`, for all variables but `electricity_demand` (see [Choose countries and subdivisions](retrieve.md#choose-countries-and-subdivisions)) |
| Codes with all data | The historical and future columns | `retrieve.py` (which codes get projections), `assemble.py` for forecasting, and the time zones of subdivisions |

A code with history but no projections, such as Kosovo, is retrieved and used for training, but not forecast for future scenarios.

!!! warning
    The `True`/`False` columns must hold only `True` or `False`. An empty cell, such as one left by editing the file by hand, stops the scripts with an error.

## Live check of the data sources

The websites of the data sources change their addresses, formats and access rules, and some stop publishing. The tests cannot notice it, because they read synthetic files. The live check downloads one sample of each data source and checks it.

Set the keys and accounts of `entsoe`, `eia`, `epias` and `isone` first (see [API keys and accounts](retrieve.md#api-keys-and-accounts)): a source whose key is missing fails.

### What it checks

All sources are checked at once, each in its own thread. For each source:

1. It picks the code whose data ends last (the first in the YAML file on a tie). An area whose extent changed has one code per period, and the website still publishes the latest.
2. It downloads the latest request (one file or API call) of that code. If it has no values, it tries the one before, up to three requests. If the latest is not found, it tries the one before, since the latest file may not be published yet.
3. It cleans the values as the retrieval does, which converts the times to UTC.
4. It checks the result against the rules below.

A source fails if the download or the parsing raises an error, if it has not answered within `time_limit_minutes`, or if:

| Rule | What it catches | Threshold |
|---|---|---|
| Values are not numbers | A changed file format | Any non-numeric value |
| Times have no time zone | A changed time format | Any |
| No values | An empty file | 0 values after cleaning |
| Negative values | Wrong values | Any value below 0 |
| Time step too long | Daily or monthly data instead of hourly | Most common step over one hour |
| Data too old | A website that stopped publishing | Latest value older than `maximum_age_days`, for a source whose `end_date` is `today` |
| Data after the end date | An out-of-date YAML file | Values more than 7 days after `end_date` (yearly files often include the first hours of the next year) |

The sources whose files you download by hand (`eskom`, `niti`) are always skipped, with the reason "Its files are downloaded manually."

### The report

The check replaces the two files in `data/results/checks/`:

| File | What it holds |
|---|---|
| `data_sources_report.md` | A summary (`Checked on <time> UTC: N failed, N passed, N skipped.`), a table of failed sources (source, entity, request, problem, failures in a row), a table of passed sources (source, entity, request, number of values, latest value in UTC), and the skipped sources with their reasons. |
| `data_sources_report.json` | `checked_at`, and `results` with, per source: `data_source`, `status` (`passed`, `failed` or `skipped`), `code`, `request`, `number_of_values`, `first_time`, `last_time`, `messages` (problems, or reason for skipping), `seconds` and `failures_in_a_row`. |

Error messages are cut to 300 characters, with API keys and passwords removed.

`failures_in_a_row` counts the checks a source has failed in a row, this one included, from the JSON report of the previous check in the same folder. It is 0 for a source that passed or was skipped. A website can be out of reach for a while, so one failure is not alarming.

!!! tip
    A check of a few sources replaces the report of the full check. The next full check then counts the failures of the other sources from 1 again.

### The weekly live check on GitHub

`.github/workflows/live-check.yml` runs every Monday at 04:23 UTC, and when started by hand, on the `main` branch only.

1. It downloads the report of the latest successful run on `main`, so the failures in a row continue.
2. It runs `uv run --locked check.py --config config/check_data_sources_config.yaml`, with the keys and accounts of ENTSO-E, EIA, EPIAS and ISO New England from the secrets of the `live-checks` environment.
3. It adds the Markdown report to the run summary, and uploads both files as the artifact `data-sources-report`, kept 90 days.
4. A separate job, without the code or the keys, reads the JSON report. If a source has failed two checks in a row or more, it opens an issue labelled `live-check`, titled "Data sources that fail the live check", or updates the open one, with the report as body. Otherwise it closes the open issue.

The same workflow runs the tests that need the network (`uv run --locked pytest -m network`), which the other test runs leave out.

## Report of the flags

The cleaning marks the changes of the electricity demand that a person should look at, such as a dip at midday. These are [flags](../concepts/glossary.md#flag); [Quality flags and reviews](../concepts/flags.md) explains each one, the reviews and their verdicts. This check gathers the flags of all codes and data sources into one report and compares them with the reviews. It reads only the data folder.

Its inputs:

- `data/electricity_demand/cleaned/<code>_<data source>_flags.parquet`: the flags of a data source;
- `data/electricity_demand/combined/<code>_flags.parquet`: the flags of the combined demand, whose data source is `combined`;
- `checks/reviewed_flags.yaml`: the reviews.

It writes two files in `data/results/checks/`. `flags_report.md` has these sections:

| Section | What it lists |
|---|---|
| Summary | For each flag: the number of flags, of series (code and data source) and of flags not reviewed. |
| Not reviewed | The flags without a review, by data source, code and flag, with their periods. Look at these first. |
| Reviewed | The flags with a review, with their periods, verdict and note. |
| Reviews without flags | Reviews, or periods of reviews, that match no flag: the error was fixed and the review can go, or a period is misspelt. "All" means a review without periods whose flag the series does not have. |
| Combined series | The numbers of combined flags that take the review of their main source, that have their own review, and that are not reviewed; then the tables "Not reviewed" (with the main source) and "With their own review". |

The first sections count only the flags of the data sources.

`flags_report.csv` has one row per flag:

| Column | Meaning |
|---|---|
| `data_source` | The data source, or `combined`. |
| `main_source` | The data source itself, or, for a combined flag, the data source of most hours of its period. |
| `code` | The country or subdivision. |
| `flag` | The flag, such as `midday_dip`. |
| `period` | The flagged period: a quarter (`DJF 2022`), a year (`2021`) or a day (`2020-03-15`). |
| `start`, `end` | First and last local days of the flag. |
| `value`, `reference` | The flagged value and the value it is compared with (see [Flag files](../concepts/flags.md#flag-files)). |
| `verdict`, `note` | The verdict and note of the review, empty if not reviewed. |
| `review_of` | The data source of the review that applies: `combined`, the main source, or empty. |

A combined flag takes the review with `data_source: combined` for its code, flag and period, or else the review of the same flag and period of its main source (see [Flags of the combined series](../concepts/flags.md#flags-of-the-combined-series)).

To review a flag, follow [How to review flags](../concepts/flags.md#how-to-review-flags), then run the report again: the flag moves to "Reviewed". If the review shows under "Reviews without flags", check the spelling of its periods.

## Related entities

Two countries or subdivisions are [related](../concepts/glossary.md#related-entities) when they share people. A model must not train on an entity related to the one it is scored on ([Models](../concepts/models.md#related-entities) explains why and how). This check computes the shares of people, which `utils/relations.py` reads. Run it with `check: related_entities` in `config/check_config.yaml` or your own file.

### How it works

1. It takes all the codes of the YAML files of the data sources.
2. For each pair of codes of the same country (same first three letters), it computes the area their shapes share, in an equal-area projection (EPSG:6933).
3. It skips the pairs whose shared area is under 0.1% of the area of the smaller one, such as neighbours whose borders touch.
4. It counts the people of each entity and of the shared area, from the gridded population of 2020 (SEDAC Gridded Population of the World, cells of 30 arc seconds whose centres are in the shape). The grid is downloaded into the data folder the first time.
5. For each entity, the share is the people of the shared area divided by its people.

A pair is related when the shared area holds at least 10% of the people of either entity.

### Files it writes

`checks/related_entities.csv` has one row per overlapping pair:

| Column | Meaning |
|---|---|
| `Entity code`, `Other code` | The codes of the two entities. |
| `Share of entity`, `Share of other` | The share of the people of each that live in the shared area, from 0 to 1. |
| `Related` | Whether the shares relate the pair. For reading only: `utils/relations.py` recomputes it from the shares, and it leaves out the exceptions below. |

`checks/related_entities_codes.txt` lists the codes the check considered, one per line. It tells a code without overlaps from a code never checked.

### Exceptions

`config/related_entities.yaml` lists the pairs that do not follow the shares:

```yaml
# Pairs of codes that are related whatever their shares.
related: []
# Pairs of codes that are not related whatever their shares.
unrelated: []
```

Each pair is a list of two codes, such as `- [<code>, <other code>]`. Use `related` for a grid and the country whose demand includes it, for example. Both lists are empty in the repository. They apply after the shares, `unrelated` after `related`.

### Why a test fails after you add a code

`test_all_codes_were_checked` (in `tests/utils/test_relations.py`) fails when a data source has a code missing from `related_entities_codes.txt`. Without its shares, the cross-validation would not keep the new code apart from the entities that share its people. Run the check and commit both files.

!!! warning
    The test does not notice a changed shape of an existing code. Run the check again yourself after you change a shape.
