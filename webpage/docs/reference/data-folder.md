# Data folder

This page lists every file that the scripts write, who writes and reads it, and the [manifests](../concepts/glossary.md#manifest) that describe them. Use it to find a file, clean up a run, or understand why a script refuses a file.

## Where the data folder is

Everything that the scripts download, compute or log goes to one folder, the *data folder*:

- `demandcast/data/`, next to the scripts, by default;
- the folder named by the environment variable `DEMANDCAST_DATA_FOLDER`, if it is set and not empty.

A relative `DEMANDCAST_DATA_FOLDER` is read from the folder you run the script in, not from the code folder, so prefer an absolute path. [Install](../getting-started/install.md#4-choose-where-the-data-goes) explains how to set it.

Git ignores `demandcast/data/`. Never commit data files: the licences of many data sources forbid redistributing them. The scripts create each folder the first time they write to it. To share the data folder, see [Share the data folder](../guides/sync.md).

## The tree

`<code>` is the code of a country or subdivision, such as `FRA` or `USA_CAL`. `<source>` is an electricity demand data source, such as `entsoe`. `<time>` is the local time of the run, as `YYYYMMDD_HHMMSS`.

```
data/
├── electricity_demand/
│   ├── raw/
│   │   ├── <source>/
│   │   │   ├── manifest.json            # requests and versions of the raw data
│   │   │   └── files/<sha256>           # each response, saved once
│   │   └── manual_downloads/            # files you download by hand
│   ├── processed/<code>_<source>.parquet
│   ├── cleaned/<code>_<source>[_removed|_flags].parquet
│   └── combined/<code>[_sources|_flags].parquet
├── gridded_weather/
│   ├── raw/
│   │   ├── <variable>_<year>[_<MODEL>_<SCENARIO>].nc
│   │   └── points/<variable>_<latitude>_<longitude>.parquet
│   └── processed/<code>_<variable>_<year>[_<MODEL>_<SCENARIO>].nc
├── gridded_population/
│   ├── raw/                             # global grids of SEDAC and Figshare
│   ├── processed/<code>_0.25_deg_<year>[_<scenario>].nc
│   └── totals/<code>.json
├── gridded_gdp_ppp/
│   ├── raw/                             # global grids of Zenodo
│   └── processed/<code>_0.25_deg_<year>[_<scenario>].nc
├── temperature/<code>_<year>[_<MODEL>_<SCENARIO>].parquet
├── population/<code>[_<scenario>].parquet
├── gdp_ppp_per_capita/
│   ├── <code>[_<scenario>].parquet
│   └── IAM_national_gdp_ppp_per_capita.csv
├── annual_electricity_demand_per_capita/<code>[_<scenario>].parquet
├── assembled/
│   ├── assembled_data_for_<use>_<time>.parquet
│   ├── assembled_data_for_<use>_<time>.manifest.json
│   └── assembled_data_for_training_<time>_[coverage|provenance].csv
├── models/<algorithm>/
│   ├── <algorithm>_model_<time>.<json|pt>
│   └── <algorithm>_model_<time>.manifest.json
├── results/
│   ├── validation/with_<model>/using_<dataset>/
│   ├── cross_validation/with_<algorithm>/using_<dataset>/
│   ├── forecasts/with_<model>/using_<dataset>/
│   ├── figures/
│   └── checks/
└── logs/<process>_<time>.log
```

`utils/paths.py` builds all these paths.

## Electricity demand

All files are in `electricity_demand/` and are written by `retrieve.py` (`variable: electricity_demand`). [Electricity demand data](../concepts/electricity-demand.md) explains the four stages and the columns of each file; [Retrieve data](../guides/retrieve.md#raw-data-and-versions) explains the raw data.

| File | What it holds | Read by |
|---|---|---|
| `raw/<source>/manifest.json` | The requests of each code and the versions of their responses, with the dates of the first and last retrievals that got them. API keys and passwords are hidden. | `retrieve.py`, to process the data again without downloading it |
| `raw/<source>/files/<sha256>` | Each response, named by its SHA-256 checksum, so that identical responses are stored once | `retrieve.py` |
| `raw/manual_downloads/<prefix>*` | Files you download by hand, for the sources without an automated download (`eskom` and `niti`) | `retrieve.py` |
| `processed/<code>_<source>.parquet` | The demand of one source for one code, in MW, at the source's resolution, in UTC, with the date each value was first retrieved | The cleaning |
| `cleaned/<code>_<source>.parquet` | The hourly cleaned demand | The combination, `check.py` (`check: flags`) |
| `cleaned/<code>_<source>_removed.parquet` | The periods that the cleaning removed, with the rule that removed them | You |
| `cleaned/<code>_<source>_flags.parquet` | The flagged periods of the cleaned demand | The combination, `check.py` |
| `combined/<code>.parquet` | One hourly series per code from all its sources, with the source of each hour and whether it can be used for training | `assemble.py`, `check.py` |
| `combined/<code>_sources.parquet` | What the combination did with each source of the code | You |
| `combined/<code>_flags.parquet` | The flagged periods of the combined series | `check.py` |

`assemble.py` also writes the three `combined/` files when the combined series is out of date.

## Weather and gridded data

All grids have a resolution of 0.25 degrees, and are written by `retrieve.py`. [Weather and socio-economic inputs](../concepts/inputs.md) explains them.

| File | What it holds | Written with |
|---|---|---|
| `gridded_weather/raw/<variable>_<year>[...].nc` | A global grid of one year, downloaded when you retrieve more than five codes at once; each code is then cut out of it | `variable: gridded_weather` or `temperature` |
| `gridded_weather/raw/points/<variable>_<latitude>_<longitude>.parquet` | The hourly series of one ERA5 grid point, named by its signed coordinates with two decimals, such as `temperature_+48.75_+2.25.parquet` | `variable: temperature`, `reanalysis_source: points` |
| `gridded_weather/processed/<code>_<variable>_<year>[...].nc` | The grid of one code and one year. With five codes or fewer, it is downloaded straight here. Read by the temperature retrieval. | `variable: gridded_weather` or `temperature` |
| `gridded_population/raw/` | The global grids: `<year>.tif` (historical) and `<SSP>/<SSP>_<year>.tif` (projections) | `variable: gridded_population` |
| `gridded_population/processed/<code>_0.25_deg_<year>[_<scenario>].nc` | The population count of one code and year. Read by the temperature, population and GDP PPP per capita retrievals. | `variable: gridded_population` |
| `gridded_population/totals/<code>.json` | The population in the shape of a code, by year (and scenario), at the resolution of the global grids, with the [fingerprint](../concepts/glossary.md#fingerprint) of the shape | `variable: population` or `gdp_ppp_per_capita` |
| `gridded_gdp_ppp/raw/` | The extracted Zenodo archive: `GDP<year>.tif` and `GDP<year>_ssp<n>.tif` | `variable: gridded_gdp_ppp` |
| `gridded_gdp_ppp/processed/<code>_0.25_deg_<year>[_<scenario>].nc` | The GDP PPP of one code and year. Read by the GDP PPP per capita retrieval. | `variable: gridded_gdp_ppp` |

In the weather files, `<MODEL>` is the climate model in upper case, as in `CESM2` or `HADGEM3-GC31-LL`. `<SCENARIO>` is the scenario in upper case, with hyphens and dots replaced by underscores (`SSP2-4.5` becomes `SSP2_4_5`).

## Indicators

Each indicator has one Parquet file per code, with hourly values stamped at the end of each hour in UTC. They are written by `retrieve.py` and read by `assemble.py`. [Weather and socio-economic inputs](../concepts/inputs.md) gives their columns and units.

| File | What it holds |
|---|---|
| `temperature/<code>_<year>.parquet` | The hourly temperature of the most populous cells of a code in one local year, from the reanalysis |
| `temperature/<code>_<year>_<MODEL>_<SCENARIO>.parquet` | The same, from a climate model and scenario. Both are in upper case, with hyphens and dots replaced by underscores, such as `FRA_2030_HADGEM3_GC31_LL_SSP2_4_5.parquet`. |
| `population/<code>[_<scenario>].parquet` | The population, historical or for one SSP scenario |
| `gdp_ppp_per_capita/<code>[_<scenario>].parquet` | The GDP PPP per capita |
| `gdp_ppp_per_capita/IAM_national_gdp_ppp_per_capita.csv` | The projected GDP PPP per capita of each country, computed once from the IIASA files of the code folder. Read by `retrieve.py`. |
| `annual_electricity_demand_per_capita/<code>[_<scenario>].parquet` | The annual electricity demand per capita, historical or for one IAMC scenario |

The historical values are in `<code>.parquet`. Each scenario has its own file, with the hyphens of the scenario replaced by underscores (`SSP2-45` becomes `SSP2_45`). A retrieval of some years replaces the values of those years and keeps the others.

## Assembled data

`assemble.py` writes one dataset per run into `assembled/`. `<use>` is the `target_use` of its settings: `training` or `forecasting`. [Assemble a dataset](../guides/assemble.md) gives the columns.

| File | What it holds |
|---|---|
| `assembled_data_for_<use>_<time>.parquet` | One row per hour and code, with all the inputs and, for training, the target |
| `assembled_data_for_<use>_<time>.manifest.json` | Its [manifest](#manifests) |
| `assembled_data_for_training_<time>_coverage.csv` | The share of hours of each year of each code, and whether the year is kept for training |
| `assembled_data_for_training_<time>_provenance.csv` | The hours of each data source and of each definition of its demand, in each local year of each code |

`train.py`, `validate.py` and `cross_validate.py` read the latest dataset for training; `forecast.py` reads the latest dataset for forecasting.

## Models

`train.py` saves each model in `models/<algorithm>/`, where `<algorithm>` is the `algorithm` of `config/ml_config.yaml` in lower case:

| File | What it holds |
|---|---|
| `xgboost_model_<time>.json` | A trained XGBoost model |
| `lstm_model_<time>.pt` | A trained LSTM model |
| `<algorithm>_model_<time>.manifest.json` | Its [manifest](#manifests) |

`validate.py` and `forecast.py` use the latest model unless you give `model_path` (see [Train and validate](../guides/train-validate.md)).

## Results

Each result goes into a folder named after the model and the dataset that made it:

- `with_<model>`: the file name of the model without its extension, such as `with_xgboost_model_20260115_093000`. A cross-validation trains its own models, so its folder is named after the algorithm, such as `with_xgboost`.
- `using_<dataset>`: the file name of the assembled data without its extension.

| Folder | Files | Written by |
|---|---|---|
| `results/validation/with_<model>/using_<dataset>/` | `all_<time>.parquet` and `all_<time>.csv` (errors of each code), `summary_<time>.csv` (errors by group), `predictions_<time>.parquet` (predictions in MW of the scored hours), `all_<time>.manifest.json` | `validate.py` |
| `results/cross_validation/with_<algorithm>/using_<dataset>/` | The same, plus `models_<time>.zip` (the model of each fold) | `cross_validate.py` |
| `results/forecasts/with_<model>/using_<dataset>/` | `all_<time>.parquet` (hourly forecasts in MW) and `all_<time>.manifest.json` | `forecast.py` |
| `results/figures/` | The PNG figures | `plot.py` |
| `results/checks/` | `data_sources_report.json` and `.md` (`check: data_sources`), `flags_report.csv` and `.md` (`check: flags`) | `check.py` |

The CSV and Parquet files of the same errors share one manifest. The columns are in [Train and validate](../guides/train-validate.md), [Cross-validate](../guides/cross-validate.md) and [Forecast](../guides/forecast.md); the figures in [Plot figures](../guides/plot.md); the reports in [Run checks](../guides/check.md).

!!! note
    The data source check reads its previous JSON report to count how many checks in a row each source has failed. Keep `data_sources_report.json` between runs to keep that count.

## Logs

Each run writes its messages (level INFO and above) to a new file, `logs/<process>_<time>.log`. They do not go to the terminal, which shows only progress bars, Python warnings and errors that stop the script.

| Script | `<process>` |
|---|---|
| `retrieve.py` | `retrieval_of_<variable>`, or `retrieval_of_electricity_demand_from_<source>` |
| `assemble.py` | `assembly_of_retrieved_data` |
| `train.py`, `validate.py`, `cross_validate.py`, `forecast.py` | `model_training`, `model_validation`, `model_cross_validation`, `model_forecasting` |
| `plot.py`, `check.py` | `plotting`, `checks` |
| `sync.py` | `sync_upload` or `sync_download` |
| `publish.py` | `publication` |
| `benchmark/run.py` | `benchmark` (also printed to the terminal) |

`sync.py` does not copy `logs/` by default (its `excluded_folders` setting).

## How files are written

Many steps skip a file that exists, so a file cut short by a crash would pass for a complete one. Every data file is therefore written *atomically*, through `utils.files.writing`:

1. The file is written under a temporary name next to its final path: the path, a random 32-character hexadecimal number and `.part`, such as `FRA.parquet.3f2a….part`.
2. If the writing ends without an error, the temporary file is renamed to the final name, replacing any older file at once.
3. If it fails, the temporary file is deleted.

Figures go through `utils.figures.save_figure`, which works the same way and saves at 300 dpi, cropped to their content. The global archives of the gridded population and GDP are extracted into a temporary folder, renamed once complete.

A `.part` file left by a killed run is harmless: no script reads it and `sync.py` never uploads it. You can delete it.

## When a file is made again

Most steps keep the files that exist and make only the missing or outdated ones. To force a step to run again, delete its files. A file is also made again when:

- its shape changed: the grids of a code record the bounds of its shape, and the temperature files and `gridded_population/totals/` the [fingerprint](../concepts/glossary.md#fingerprint) of its shape ([Inputs](../concepts/inputs.md#countries-subdivisions-and-shapes));
- it may be incomplete: reanalysis weather and temperature files of recent years, and ERA5 point series that the CDS may extend, at most once a day ([Inputs](../concepts/inputs.md#when-files-are-downloaded-again));
- a temperature file was made by another version of the extraction ([Inputs](../concepts/inputs.md#when-files-are-extracted-again));
- a combined electricity demand file has another fingerprint (rules, reviews, source YAML files, flags) or is older than a cleaned file of its code ([Electricity demand](../concepts/electricity-demand.md#when-the-combination-runs-again)).

## Manifests

A *manifest* is a JSON file next to a file, which describes how that file was made. The assembled datasets, the trained models and the results each have one. Its name is the file name without its extension, plus `.manifest.json`: `all_20260115_093000.parquet` has `all_20260115_093000.manifest.json`. `utils/manifest.py` writes and checks them.

It lets a script check that a model, its data and its results belong together, and that no file was replaced. [Models](../concepts/models.md#manifests) explains each kind in plain words.

### Fields of every manifest

| Field | Meaning |
|---|---|
| `manifest_version` | The version of the format (2). A script refuses a higher version than it knows. |
| `kind` | `dataset`, `model` or `results` |
| `file` | The name of the file it describes |
| `sha256` | The SHA-256 checksum of that file |
| `files` | The checksum of each format of the same content, such as the CSV and Parquet files of the same errors |
| `created` | The time it was written, in UTC |
| `code` | `commit`: the git commit, with `+changes` if tracked files had uncommitted changes, or `null` without git. `lockfile`: the checksum of `uv.lock`. |

Paths to other files are relative to the data folder, with forward slashes, so they stay valid in a copy of the data folder, such as one downloaded from a bucket. A file outside the data folder is recorded by its absolute path.

### Fields of each kind

| Kind | Extra fields |
|---|---|
| `dataset` | `purpose` (`training` or `forecasting`); `settings` (of `assemble.py`); `columns` (name and type); `rows`; `entities`; `inputs` (for each input: the number of files read and one checksum of their paths and contents); `provenance` (name and checksum of the provenance CSV, training only) |
| `model` | `algorithm`; `dataset` (path and checksum of the training data); `ml_settings` (`config/ml_config.yaml`); `model_settings` (`config/<algorithm>_config.yaml`); `features` (names and types, in order); `target` (column and transformation); `preprocessing` (mean and scale of the standardized features, empty for XGBoost); `splits` (the code and local year pairs of each set) |
| `results` | `case` (`validation`, `cross_validation` or `forecasts`); `model` (name and checksum); `dataset` (name, path and checksum); `columns`; `summary`, `predictions` and, for a cross-validation, `models` (name and checksum of each companion file) |
| `results` of a validation or cross-validation | `metric` (MAPE and WAPE, as fractions, lower is better) |
| `results` of a cross-validation | `holdout`, `ml_settings`, `model_settings`, `folds` |
| `results` of a forecast | `units` (`MW`); `annual_totals` (for each year of each code: its hours, the mean before scaling, and whether it was scaled to the annual demand) |

### When a script refuses a file

Before a script uses a file that has a manifest, it checks the file against it. It stops with an error when:

| Check | Done by | Fails when |
|---|---|---|
| Version | Every script that reads a manifest | The manifest has a higher version than the code reads |
| Kind | `train.py`, `validate.py`, `cross_validate.py`, `forecast.py` (dataset); `validate.py`, `forecast.py` (model); `plot.py` (results) | The manifest is of another kind |
| Name | The same, and `publish.py` | The manifest does not list the file |
| Checksum | The same, and `publish.py` | The file was changed or replaced after the manifest was written |
| Companion files | `plot.py` | The summary or predictions differ from the recorded ones |
| Model of the results | `publish.py` | Results of a release come from another model than the model of the release |

The machine learning scripts also check the purpose of the data, the target, the features, the sets and the provenance file: see [When a script refuses a file](../concepts/models.md#when-a-script-refuses-a-file).

A file without a manifest is still used, with a warning in the log, because its origin cannot be checked. Two exceptions: `validate.py` then needs `used_validation_set`, and `publish.py` refuses forecasts without a manifest.

### Which file is the latest

When you give no path, the scripts take the file with the latest `<time>` in its name. Only names made exactly of the prefix, the time and the extension count: a copy such as `xgboost_model_20260115_093000 (copy).json`, or a manifest, is never taken. The time is the local time of the computer that ran the script.

## Inputs in the code folder

The inputs that come with the code stay in `demandcast/`, next to the scripts. [Configuration files](configuration.md) explains the settings and lists. Most are written only by you; these are written by scripts:

| Path | What it holds | Written by |
|---|---|---|
| `checks/data_availability_summary.csv` | Which codes have the socio-economic data; the other scripts read it to choose their codes | `check.py` (`check: data_availability`) |
| `checks/related_entities.csv`, `checks/related_entities_codes.txt` | The shares of people of overlapping entities, and the codes that the check considered | `check.py` (`check: related_entities`) |
| `shapes/subdivisions/USA.yaml` | The non-standard subdivisions of the United States, including the EIA regions | `shapes/eia.py` (and you) |

The other inputs, which you edit, are the settings in `config/`, `shapes/subdivisions/<ISO3>.yaml`, the data source files `retrievals/electricity_demand_data_sources/<source>.yaml`, the IIASA files in `retrievals/socio_economic_data_sources/manual_downloads/`, `retrievals/socio_economic_data_sources/iam_regions_mapping.yaml`, the reviews in `checks/reviewed_flags.yaml`, the release files in `publishing/release/`, and your keys in `.env` (never commit it).

Two places outside the data folder are also written:

- `plot.py` with `figure: status` writes the figures and numbers of the [Current state](../status.md) page into `webpage/docs/status/`, and the same numbers into `README.md`.
- cartopy downloads the Natural Earth shapes into its own folder in your user folder (`~/.local/share/cartopy` on Linux by default), not into the data folder.
