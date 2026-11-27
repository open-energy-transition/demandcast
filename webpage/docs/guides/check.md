# Run checks

`check.py` runs one of four checks of the data and of the code's inputs. Use it after you add a data source, a country or subdivision, or a shape, after a retrieval, or to find out whether the websites of the data sources still work.

| Check | What it does | When to run it | Network? | Writes |
|---|---|---|---|---|
| [`data_availability`](#data-availability) | Lists which countries and subdivisions have the socio-economic data the models need | After adding a shape, or when the World Bank, Ember, IMF or IIASA data changes | Yes | `checks/data_availability_summary.csv` (in the code) |
| [`data_sources`](#live-check-of-the-data-sources) | Downloads a sample of each electricity demand data source and checks it | When a retrieval fails; every week on GitHub | Yes | `data/results/checks/data_sources_report.json` and `.md` |
| [`flags`](#report-of-the-flags) | Gathers the flags of the cleaned electricity demand and compares them with their reviews | After retrieving electricity demand | No | `data/results/checks/flags_report.csv` and `.md` |
| [`related_entities`](#related-entities) | Computes which countries and subdivisions share people | After adding a code to a data source or changing a shape | Once, for the gridded population | `checks/related_entities.csv` and `checks/related_entities_codes.txt` (in the code) |

The files under `checks/` are in the code folder (`demandcast/checks/`) and belong to the repository: commit them after you run the check. The files under `data/` are in the [data folder](../reference/data-folder.md).

## Run check.py

Each check has its own settings file. From the `demandcast/` folder:

```bash
uv run check.py                                                # check in config/check_config.yaml
uv run check.py --config config/check_data_sources_config.yaml # live check of the data sources
uv run check.py --config config/check_flags_config.yaml        # report of the flags
```

`config/check_config.yaml` holds `check: data_availability` by default. Change it to `check: related_entities` to run that check, or write your own file. The log of each run is in `data/logs/checks_<time>.log`; nothing is printed on the screen.

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `check` | Yes | — | The check to run: `data_availability`, `data_sources`, `flags` or `related_entities`. |
| `data_sources` | No | all | The data sources to check, such as `[ons, hydroquebec]`. Only for `data_sources`. |
| `maximum_age_days` | No | `60` | How old, in days, the latest value of a data source that publishes until today may be. Only for `data_sources`. |
| `maximum_age_days_by_source` | No | none | A different `maximum_age_days` for some data sources, by name. Only for `data_sources`. |
| `time_limit_minutes` | No | `15` | The minutes after which a data source that has not answered fails. Only for `data_sources`. |
| `skipped_data_sources` | No | none | Data sources not to check, each with the reason shown in the report. Only for `data_sources`. |

!!! note
    The options of the live check are accepted, and ignored, with the other checks.

## Data availability

This check decides which countries and subdivisions the other scripts work on, from the socio-economic data that exists for them. It writes `checks/data_availability_summary.csv`, which `utils/availability.py` reads.

### What it computes

It starts from every code with a shape: the countries and standard subdivisions of Natural Earth, and the non-standard subdivisions defined in `shapes/subdivisions/`. It stops with an error if a country code is not an official ISO 3166 alpha-3 code (Kosovo, `XKX`, is added to the list).

For each code, it checks six indicators:

| Column | Source |
|---|---|
| `historical_population` | World Bank (downloaded) |
| `historical_electricity_demand_per_capita` | Ember and the World Bank (downloaded; needs `EMBER_API_KEY`) |
| `historical_gdp_ppp_per_capita` | World Bank and IMF (downloaded) |
| `future_population` | IIASA SSP database (file in the repository) |
| `future_gdp_ppp_per_capita` | IIASA SSP database (file in the repository) |
| `future_electricity_demand_per_capita` | IIASA, by region; a country has it if `iam_regions_mapping.yaml` maps it to a region |

Two rules apply to the subdivisions:

- A subdivision has the data per capita of its country, because the data per capita is assumed to be the same everywhere in a country.
- A subdivision never has the population of its country, since its population is smaller.

It also computes the area of each shape, in an equal-area projection. A country or subdivision of at least 500 km² can get its population and GDP PPP from gridded data (see [Inputs](../concepts/inputs.md)).

### Columns of data_availability_summary.csv

| Column | Meaning |
|---|---|
| `entity_code` | The code, such as `FRA` or `USA_CAL`. |
| `entity_name` | The name of the country, or `Subdivision of <country>`. |
| `historical_population`, `historical_electricity_demand_per_capita`, `historical_gdp_ppp_per_capita` | `True` if the source has the code (or its country, for data per capita). |
| `<indicator>_first_year`, `<indicator>_last_year` | The first and last years with a value, for each historical indicator. Empty for the population of a subdivision. |
| `future_population`, `future_gdp_ppp_per_capita`, `future_electricity_demand_per_capita` | `True` if the projections of IIASA have the code (or its country, for data per capita). |
| `area_greater_than_500_km2` | `True` if the area is at least 500 km². |

### How the other scripts use it

`utils/availability.py` selects the codes that have either:

- the population, the electricity demand per capita and the GDP PPP per capita; or
- the electricity demand per capita and an area of at least 500 km², whose population and GDP PPP per capita come from the gridded data.

It gives two lists:

| List | Needs | Used by |
|---|---|---|
| Codes with historical data | The historical columns only | `retrieve.py` for the socio-economic, gridded and weather data, without a code or with a file of codes |
| Codes with all data | The historical and the future columns | `retrieve.py` (which codes get projections), `assemble.py` for forecasting, and the time zones of subdivisions |

A code with historical data but no projections, such as Kosovo, which IIASA does not project, is retrieved and used for training, but not forecast for future scenarios. When you give `retrieve.py` a file of codes, the codes without the data are logged as errors and left out (see [Retrieve data](retrieve.md)).

!!! warning
    Every column of whether a code has data must hold only `True` or `False`. If you edit the CSV by hand and leave a cell empty, the scripts stop with an error.

## Live check of the data sources

The websites of the data sources change their addresses, formats and access rules, and some stop publishing. The tests cannot notice it, because they read synthetic files. The live check downloads one sample of each data source over the network and checks it.

```bash
uv run check.py --config config/check_data_sources_config.yaml
```

Set the API keys and accounts in your `.env` file first: ENTSO-E and EIA need their API keys, and EPIAS and ISO New England their accounts (see [Retrieve data](retrieve.md)). A data source whose key is missing fails.

### What it checks

All the data sources are checked at the same time, each in its own thread, since each one is a different website. For each data source:

1. It picks the country or subdivision whose data ends last (the first in the YAML file if several end on the same day). An area whose extent changed has one code per period, and the latest one is the one the website still publishes.
2. It downloads the latest request (one file or one API call) of that code. If it has no values, it tries the request before, up to three requests. If the latest request is not found, it tries the one before, since the file of the latest period may not be published yet.
3. It cleans the values as the retrieval does, which converts the times to UTC.
4. It checks the result against the rules below.

A data source fails if the download or the parsing raises an error, or if:

| Rule | What it catches | Threshold |
|---|---|---|
| Values are not numbers | A changed file format | Any value that is not numeric |
| Times have no time zone | A changed time format | Any |
| No values | An empty file | 0 values after cleaning |
| Negative values | Wrong values | Any value below 0 |
| Time step too long | Daily or monthly data instead of hourly | The most common step is more than one hour |
| Data too old | A website that stopped publishing | The latest value is older than `maximum_age_days`, for a data source whose `end_date` is `today` |
| Data after the end date | A YAML file that is out of date | Values more than 7 days after the `end_date` of the YAML file (files of a year often include the first hours of the next) |

The data sources whose files you download by hand (`eskom`, `niti`) are always skipped, with the reason "Its files are downloaded manually."

### Settings of check_data_sources_config.yaml

| Option | Value in the file | Why |
|---|---|---|
| `check` | `data_sources` | Runs the live check. |
| `data_sources` | empty (all) | Set a list, such as `[ons, hydroquebec]`, to check only some. An unknown name stops the check. |
| `maximum_age_days` | `60` | Most data sources publish within weeks. |
| `maximum_age_days_by_source` | `caiso: 180`, `tsoc: 700` | CAISO publishes a month one to four months after its end. TSOC publishes a file per year, from five weeks to about nine months after the year ends, so its latest value can be almost two years old. |
| `time_limit_minutes` | `15` | A website that does not answer cannot keep the check from ending. |
| `skipped_data_sources` | `tepco: Its website refuses the requests from the runners of GitHub Actions.` | TEPCO answers the computers of GitHub Actions, where the weekly check runs, with HTTP 403. OCCTO gives the same demand of the Kanto area. |

### The report

The check writes two files in `data/results/checks/`, which replace those of the previous check:

| File | What it holds |
|---|---|
| `data_sources_report.md` | A summary (`Checked on <time> UTC: N failed, N passed, N skipped.`), then a table of the failed data sources (data source, entity, request, problem, failures in a row), a table of the passed ones (data source, entity, request, number of values, latest value in UTC), and the list of the skipped ones with their reasons. |
| `data_sources_report.json` | `checked_at`, and a list `results` with, for each data source: `data_source`, `status` (`passed`, `failed` or `skipped`), `code`, `request`, `number_of_values`, `first_time`, `last_time`, `messages` (the problems, or the reason for skipping), `seconds` and `failures_in_a_row`. |

Error messages are cut to 300 characters, and API keys and passwords are removed from them.

`failures_in_a_row` counts the checks that a data source has failed in a row, this one included. The check reads it from the JSON report of the previous check in the same folder. It is 0 for a data source that passed or was skipped. A website can be out of reach for a while, so a single failure is not alarming.

!!! tip
    A check of a few data sources replaces the report of the full check. The next full check then counts the failures of the other data sources from 1 again.

### The weekly live check on GitHub

The workflow `.github/workflows/live-check.yml` runs the live check every Monday at 04:23 UTC, and when started by hand. It runs only on the `main` branch.

1. It downloads the report of the latest successful run of the workflow on `main`, so that the failures in a row continue.
2. It runs `uv run --locked check.py --config config/check_data_sources_config.yaml`, with the API keys and accounts of ENTSO-E, EIA, EPIAS and ISO New England, which are secrets of the `live-checks` environment.
3. It adds the Markdown report to the summary of the run, and uploads both files as the artifact `data-sources-report`, kept for 90 days.
4. A separate job, without the code or the keys, reads the JSON report. If a data source has failed two checks in a row or more, it opens an issue labelled `live-check`, titled "Data sources that fail the live check", or updates the open one, with the whole report as its body. If none has, it closes the open issue.

The same workflow runs the tests that need network access (`uv run --locked pytest -m network`), which the other runs of the tests leave out.

## Report of the flags

The cleaning of the electricity demand marks the changes that need a person to look at them, such as a dip at midday or a shift of the daily profile. These marks are [flags](../concepts/glossary.md#flag); [Electricity demand data](../concepts/flags.md) explains each flag and its rule. A flag never removes a value: its review decides what happens to the flagged hours.

This check gathers the flags of all the countries, subdivisions and data sources into one report, and compares them with the reviews. It reads only the data folder, so it needs no network.

```bash
uv run check.py --config config/check_flags_config.yaml
```

`config/check_flags_config.yaml` has a single option, `check: flags`.

### Inputs

| Input | What it holds |
|---|---|
| `data/electricity_demand/cleaned/<code>_<data source>_flags.parquet` | The flags of the cleaned demand of a data source. |
| `data/electricity_demand/combined/<code>_flags.parquet` | The flags of the combined demand of a code, whose data source is `combined`. |
| `checks/reviewed_flags.yaml` | The reviews. |

### The report

The check writes two files in `data/results/checks/`:

`flags_report.md` has these sections:

| Section | What it lists |
|---|---|
| Summary | For each flag: the number of flags, of series (code and data source) and of flags not reviewed. |
| Not reviewed | The flags without a review, by data source, code and flag, with their periods. Look at these first. |
| Reviewed | The flags with a review, with their periods, verdict and note. |
| Reviews without flags | The reviews, or the periods of reviews, that match no flag: the error was fixed and the review can be removed, or a period is misspelt. "All" means a review without periods whose flag the series does not have. |
| Combined series | The number of combined flags that take the review of their main source, that have their own review and that are not reviewed, then the tables "Not reviewed" (with the main source) and "With their own review". |

The first sections count only the flags of the data sources; the combined flags have their own section.

`flags_report.csv` has one row per flag:

| Column | Meaning | Unit |
|---|---|---|
| `data_source` | The data source, or `combined` for the combined demand. | — |
| `main_source` | The data source itself, or, for a combined flag, the data source of most of the hours of its period. | — |
| `code` | The country or subdivision. | — |
| `flag` | The flag, such as `midday_dip` or `low_value`. | — |
| `period` | The name of the flagged period: a quarter (`DJF 2022`), a year (`2021`) or a day (`2020-03-15`). | — |
| `start`, `end` | The first and last local days of the flag. | date |
| `value`, `reference` | The value that was flagged and the value it is compared with; their meaning depends on the flag. | depends on the flag |
| `verdict`, `note` | The verdict and note of the review, empty if not reviewed. | — |
| `review_of` | The data source of the review that applies: `combined`, the main source, or empty. | — |

### Review a flag

1. Retrieve the electricity demand (see [Retrieve data](retrieve.md)). The retrieval logs a warning for each flag.
2. Run the report and open `data/results/checks/flags_report.md`.
3. For each row of "Not reviewed", look at the demand of the code in the flagged periods and find the cause.
4. Add a review to `checks/reviewed_flags.yaml`:

    ```yaml
    reviews:
      - data_source: ons
        code: BRA_S
        flag: midday_dip
        periods:
          - MAM 2022
          - JJA 2022
        verdict: net_demand
        note: The load of ONS leaves out the distributed generation until 2023-04-29.
    ```

5. Run the report again. The flag moves to "Reviewed". If the review appears under "Reviews without flags", check the spelling of its periods.
6. Commit `checks/reviewed_flags.yaml`.

Each review has these fields:

| Field | Required? | What it is |
|---|---|---|
| `data_source` | Yes | The data source of the flag, or `combined`. |
| `code` | Yes | The code of the country or subdivision. |
| `flag` | Yes | The name of the flag. |
| `periods` | No | The periods it reviews, spelt exactly as in the report. Without it, the review covers all the periods of the flag. |
| `verdict` | Yes | `source_error`, `reading_error`, `definition_change`, `net_demand`, `real_event` or `false_positive`. |
| `note` | Yes | Why, in one sentence, with a source if you have one. |

A misspelt field name is an error, so a review of some periods never becomes a review of all of them by mistake. [Reviews](../concepts/flags.md#reviews-of-flags) explains each verdict and what it does to the flagged hours, such as leaving the days of a `source_error` out of the training. You do not need to re-run the retrieval: the next assembly of the training data combines the series again with the new reviews.

### Reviews of combined flags

A flag of the combined demand takes:

1. the review with the data source `combined` for that code, flag and period, if there is one;
2. otherwise, if its main source has the same flag in the same period, the review of that flag.

So a flag that comes from the data of a source is reviewed once, under that source. Only a flag that the main source does not have needs its own review with `data_source: combined`. Such a flag comes from the combination itself, such as a step where one data source fills the hours after another.

## Related entities

Two countries or subdivisions are related when they share people: a country and its subdivisions, a grid and the state it supplies, or the periods of a grid whose area grew. A model must not train on an entity related to the one it is scored on: it would see the demand of the same people at the same hours. [Models](../concepts/models.md#related-entities) explains how the splits of the training and the cross-validation use this.

This check computes the shares of people, and `utils/relations.py` reads them. Run it after you add a code to a data source or change a shape:

```yaml
# config/check_config.yaml, or your own file
check: related_entities
```

```bash
uv run check.py
```

### How it works

1. It takes all the codes of the YAML files of the data sources.
2. For each pair of codes of the same country (the same first three letters), it computes the area that their shapes share.
3. It skips the pairs whose shared area is less than 0.1% of the area of the smaller one, such as neighbours whose borders touch. Areas are compared in an equal-area projection (EPSG:6933).
4. It counts the people of each entity and of the shared area, from the gridded population of 2020 (Gridded Population of the World of SEDAC, cells of 30 arc seconds whose centres are in the shape). The grid is downloaded into the data folder the first time.
5. For each entity, the share is the people of the shared area divided by its people.

| Rule | What it means | Threshold |
|---|---|---|
| Minimum shared area | Smaller overlaps are slivers of the borders, not shared areas | 0.1% of the area of the smaller entity |
| Related | The shared area holds a real part of the people of one of them | At least 10% of the people of either entity |

### Files it writes

`checks/related_entities.csv` has one row per pair that overlaps:

| Column | Meaning |
|---|---|
| `Entity code` | The code of one entity. |
| `Other code` | The code of the other entity. |
| `Share of entity` | The share of the people of the entity that live in the shared area, from 0 to 1. |
| `Share of other` | The same for the other entity. |
| `Related` | Whether the pair is related by its shares. |

`utils/relations.py` recomputes whether a pair is related from the two shares, so the `Related` column is for reading only, and it does not include the exceptions below.

`checks/related_entities_codes.txt` lists, one per line, the codes that the check considered. It tells a code without overlaps apart from a code that was never checked.

### Exceptions

`config/related_entities.yaml` lists the pairs that do not follow the shares:

```yaml
# Pairs of codes that are related whatever their shares.
related: []
# Pairs of codes that are not related whatever their shares.
unrelated: []
```

Each pair is a list of two codes, such as `- [<code>, <other code>]`. Use `related` for a grid and the country whose demand includes it, for example. Both lists are empty in the repository. The exceptions apply after the shares, and `unrelated` after `related`.

### Why a test fails after you add a code

The test `test_all_codes_were_checked` (in `tests/utils/test_relations.py`) fails when a data source has a code that is missing from `related_entities_codes.txt`. Without this check, a new code would have no shares, and the cross-validation would not keep it apart from the entities that share its people. To fix it, run the check and commit both files.

!!! warning
    The test does not notice a changed shape of an existing code. Run the check again yourself after you change a shape.
