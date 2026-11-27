# Data folder

This page lists every folder and file that the scripts write, what each one holds, and which script writes and reads it. Use it to find a file, to clean up a run, or to check why a script refuses a file.

## Where the data folder is

Everything that the scripts download, compute or log goes to one folder, the *data folder*:

- by default, `demandcast/data/`, next to the scripts;
- or the folder named by the environment variable `DEMANDCAST_DATA_FOLDER`, if it is set and not empty.

A relative value of `DEMANDCAST_DATA_FOLDER` is read from the folder you run the script in, not from the code folder. Use an absolute path to avoid surprises:

```bash
export DEMANDCAST_DATA_FOLDER=/mnt/storage/demandcast-data
uv run retrieve.py
```

Git ignores `demandcast/data/`. Never commit data files: the licences of many data sources do not allow their redistribution.

The scripts create each folder the first time they write to it. To share a data folder with your team, copy it to a bucket with `sync.py` (see [Share the data folder](../guides/sync.md)).

## The tree

`<code>` is the code of a country or subdivision, such as `FRA` or `USA_CAL`. `<source>` is the name of an electricity demand data source, such as `entsoe`. `<time>` is the local time of the run, as `YYYYMMDD_HHMMSS`.

```
data/
├── electricity_demand/
│   ├── raw/
│   │   ├── <source>/
│   │   │   ├── manifest.json            # requests and versions of the raw data
│   │   │   └── files/<sha256>           # each response, saved once
│   │   └── manual_downloads/            # files you download by hand
│   ├── processed/
│   │   └── <code>_<source>.parquet
│   ├── cleaned/
│   │   ├── <code>_<source>.parquet
│   │   ├── <code>_<source>_removed.parquet
│   │   └── <code>_<source>_flags.parquet
│   └── combined/
│       ├── <code>.parquet
│       ├── <code>_sources.parquet
│       └── <code>_flags.parquet
├── gridded_weather/
│   ├── raw/
│   │   ├── <variable>_<year>[_<model>_<scenario>].nc
│   │   └── points/<variable>_<latitude>_<longitude>.parquet
│   └── processed/
│       └── <code>_<variable>_<year>[_<model>_<scenario>].nc
├── gridded_population/
│   ├── raw/                             # global grids of SEDAC and Figshare
│   ├── processed/<code>_0.25_deg_<year>[_<scenario>].nc
│   └── totals/<code>.json
├── gridded_gdp_ppp/
│   ├── raw/                             # global grids of Zenodo
│   └── processed/<code>_0.25_deg_<year>[_<scenario>].nc
├── temperature/
│   └── <code>_<year>[_<model>_<scenario>].parquet
├── population/
│   └── <code>[_<scenario>].parquet
├── gdp_ppp_per_capita/
│   ├── <code>[_<scenario>].parquet
│   └── IAM_national_gdp_ppp_per_capita.csv
├── annual_electricity_demand_per_capita/
│   └── <code>[_<scenario>].parquet
├── assembled/
│   ├── assembled_data_for_<use>_<time>.parquet
│   ├── assembled_data_for_<use>_<time>.manifest.json
│   ├── assembled_data_for_training_<time>_coverage.csv
│   └── assembled_data_for_training_<time>_provenance.csv
├── models/<algorithm>/
│   ├── <algorithm>_model_<time>.<json|pt>
│   └── <algorithm>_model_<time>.manifest.json
├── results/
│   ├── validation/with_<model>/using_<dataset>/
│   ├── cross_validation/with_<algorithm>/using_<dataset>/
│   ├── forecasts/with_<model>/using_<dataset>/
│   ├── figures/
│   └── checks/
└── logs/
    └── <process>_<time>.log
```

The functions of `utils/paths.py` build all these paths. The sections below describe each folder.

## Electricity demand

The electricity demand goes through four stages. [Electricity demand data](../concepts/electricity-demand.md) explains each stage, the cleaning rules, the flags and the columns of each file.

| File | What it holds | Written by | Read by |
|---|---|---|---|
| `raw/<source>/manifest.json` | The requests of each code and the versions of their responses, with the dates of the first and last retrievals that got them. API keys and passwords are hidden. | `retrieve.py` (`variable: electricity_demand`) | `retrieve.py`, to process the data again without downloading it |
| `raw/<source>/files/<sha256>` | The content of each response, named by its SHA-256 checksum, so that identical responses are stored once | `retrieve.py` | `retrieve.py` |
| `raw/manual_downloads/<prefix>*` | Files that you download by hand for the sources without an automated download (`eskom` and `niti`) | You | `retrieve.py` |
| `processed/<code>_<source>.parquet` | The demand of one data source for one code, in MW at the source's resolution, in UTC, with the date each value was first retrieved | `retrieve.py` | The cleaning |
| `cleaned/<code>_<source>.parquet` | The hourly cleaned demand | `retrieve.py` | The combination, `check.py` (`check: flags`) |
| `cleaned/<code>_<source>_removed.parquet` | The periods of the values that the cleaning removed, with the rule that removed them | `retrieve.py` | You, to inspect the cleaning |
| `cleaned/<code>_<source>_flags.parquet` | The flagged periods of the cleaned demand | `retrieve.py` | The combination, `check.py` (`check: flags`) |
| `combined/<code>.parquet` | One hourly series per code from all its data sources, with the source of each hour and whether the hour can be used for training | `retrieve.py`, and `assemble.py` when the series is out of date | `assemble.py`, `check.py` (`check: flags`) |
| `combined/<code>_sources.parquet` | What the combination did with each data source of the code | `retrieve.py`, `assemble.py` | You |
| `combined/<code>_flags.parquet` | The flagged periods of the combined series | `retrieve.py`, `assemble.py` | `check.py` (`check: flags`) |

The raw data and the manual downloads are described in [Retrieve data](../guides/retrieve.md).

## Weather and gridded data

[Weather and socio-economic inputs](../concepts/inputs.md) explains these datasets. All grids have a resolution of 0.25 degrees.

| File | What it holds | Written by | Read by |
|---|---|---|---|
| `gridded_weather/raw/<variable>_<year>[_<model>_<scenario>].nc` | A global grid of a year, downloaded when you retrieve more than five codes at once | `retrieve.py` (`variable: gridded_weather` or `temperature`) | `retrieve.py`, which cuts each code out of it |
| `gridded_weather/raw/points/<variable>_<latitude>_<longitude>.parquet` | The hourly series of one ERA5 grid point, named by its signed coordinates with two decimals, such as `temperature_+48.75_+2.25.parquet` | `retrieve.py` (`variable: temperature`, `reanalysis_source: points`) | `retrieve.py` |
| `gridded_weather/processed/<code>_<variable>_<year>[_<model>_<scenario>].nc` | The grid of one code and one year. With five codes or fewer, it is downloaded straight here. | `retrieve.py` | `retrieve.py` (`variable: temperature`) |
| `gridded_population/raw/` | The global population grids: `<year>.tif` for the historical years and `<SSP>/<SSP>_<year>.tif` for the projections | `retrieve.py` (`variable: gridded_population`) | `retrieve.py` |
| `gridded_population/processed/<code>_0.25_deg_<year>[_<scenario>].nc` | The population count of one code and one year | `retrieve.py` | `retrieve.py` (temperature, population, GDP PPP per capita) |
| `gridded_population/totals/<code>.json` | The population in the shape of a code, by year (and scenario), at the resolution of the global grids, with the fingerprint of the shape | `retrieve.py` (`variable: population` or `gdp_ppp_per_capita`) | `retrieve.py` |
| `gridded_gdp_ppp/raw/` | The extracted archive of Zenodo: `GDP<year>.tif` and `GDP<year>_ssp<n>.tif` | `retrieve.py` (`variable: gridded_gdp_ppp`) | `retrieve.py` |
| `gridded_gdp_ppp/processed/<code>_0.25_deg_<year>[_<scenario>].nc` | The GDP PPP of one code and one year | `retrieve.py` | `retrieve.py` (GDP PPP per capita) |

In the names of the weather files, the scenario has its hyphens and dots replaced by underscores (`SSP2-4.5` becomes `SSP2_4_5`). The climate model keeps its spelling, such as `CESM2`.

## Indicators

Each indicator has one Parquet file per code with hourly values, at the end of each hour in UTC. [Weather and socio-economic inputs](../concepts/inputs.md) gives their columns and units.

| File | What it holds | Written by | Read by |
|---|---|---|---|
| `temperature/<code>_<year>.parquet` | The hourly temperature of the most populous cells of a code in one local year, from the reanalysis | `retrieve.py` (`variable: temperature`) | `assemble.py` |
| `temperature/<code>_<year>_<model>_<scenario>.parquet` | The same, from a climate model and scenario | `retrieve.py` | `assemble.py` |
| `population/<code>.parquet`, `population/<code>_<scenario>.parquet` | The population, historical or for one SSP scenario | `retrieve.py` (`variable: population`) | `assemble.py` |
| `gdp_ppp_per_capita/<code>[_<scenario>].parquet` | The GDP PPP per capita | `retrieve.py` (`variable: gdp_ppp_per_capita`) | `assemble.py` |
| `gdp_ppp_per_capita/IAM_national_gdp_ppp_per_capita.csv` | The projected GDP PPP per capita of each country, computed once from the IIASA files of the code folder | `retrieve.py` | `retrieve.py` |
| `annual_electricity_demand_per_capita/<code>[_<scenario>].parquet` | The annual electricity demand per capita, historical or for one IAMC scenario | `retrieve.py` (`variable: annual_electricity_demand_per_capita`) | `assemble.py` |

The historical values of an indicator are in `<code>.parquet`. Each scenario has its own file, with the hyphens of the scenario replaced by underscores (`SSP2-45` becomes `SSP2_45`). A retrieval of some years replaces the values of those years and keeps the others.

## Assembled data

`assemble.py` writes one dataset per run into `assembled/`. `<use>` is the `target_use` of the settings: `training` or `forecasting`.

| File | What it holds |
|---|---|
| `assembled_data_for_<use>_<time>.parquet` | One row per hour and code, with all the inputs and, for training, the target |
| `assembled_data_for_<use>_<time>.manifest.json` | Its [manifest](#manifests) |
| `assembled_data_for_training_<time>_coverage.csv` | The share of hours of each year of each code, and whether the year is kept for training |
| `assembled_data_for_training_<time>_provenance.csv` | The hours of each data source and of each definition of its demand, in each local year of each code |

[Assemble a dataset](../guides/assemble.md) gives the columns. `train.py`, `validate.py` and `cross_validate.py` read the latest dataset for training; `forecast.py` reads the latest dataset for forecasting.

## Models

`train.py` saves each trained model in `models/<algorithm>/`, where `<algorithm>` is the `algorithm` of `config/ml_config.yaml` in lower case (`xgboost` or `lstm`).

| File | What it holds |
|---|---|
| `xgboost_model_<time>.json` | A trained XGBoost model |
| `lstm_model_<time>.pt` | A trained LSTM model |
| `<algorithm>_model_<time>.manifest.json` | Its [manifest](#manifests) |

`validate.py` and `forecast.py` use the latest model unless you give `model_path` (see [Train and validate](../guides/train-validate.md)).

## Results

Each result goes into a folder named after the model and the dataset that made it:

- `with_<model>` is the file name of the model without its extension, such as `with_xgboost_model_20260115_093000`. A cross-validation trains its own models, so its folder is named after the algorithm, such as `with_xgboost`.
- `using_<dataset>` is the file name of the assembled data without its extension.

| Folder | Files | Written by |
|---|---|---|
| `results/validation/with_<model>/using_<dataset>/` | `all_<time>.parquet` and `all_<time>.csv` (errors of each code), `summary_<time>.csv` (errors by group of codes), `predictions_<time>.parquet` (predictions in MW of the scored hours), `all_<time>.manifest.json` | `validate.py` |
| `results/cross_validation/with_<algorithm>/using_<dataset>/` | The same files, and `models_<time>.zip` (the model of each fold) | `cross_validate.py` |
| `results/forecasts/with_<model>/using_<dataset>/` | `all_<time>.parquet` (hourly forecasts in MW) and `all_<time>.manifest.json` | `forecast.py` |
| `results/figures/` | The PNG figures of `plot.py` | `plot.py` |
| `results/checks/` | `data_sources_report.json` and `data_sources_report.md` (`check: data_sources`), `flags_report.csv` and `flags_report.md` (`check: flags`) | `check.py` |

The CSV and Parquet files of the same errors share one manifest. The columns of each file are in [Train and validate](../guides/train-validate.md), [Cross-validate](../guides/cross-validate.md) and [Forecast](../guides/forecast.md). The figures and their names are in [Plot figures](../guides/plot.md), and the check reports in [Run checks](../guides/check.md).

The data source check reads its previous JSON report to count how many checks in a row each source has failed. Keep `data_sources_report.json` between runs if you want that count.

## Logs

Each script run writes its messages (level INFO and above) to a new file in `logs/`: `<process>_<time>.log`. The messages go only to this file, not to the terminal. Only the progress bars and Python warnings appear in the terminal.

| Script | `<process>` |
|---|---|
| `retrieve.py` | `retrieval_of_<variable>`, or `retrieval_of_electricity_demand_from_<source>` |
| `assemble.py` | `assembly_of_retrieved_data` |
| `train.py` | `model_training` |
| `validate.py` | `model_validation` |
| `cross_validate.py` | `model_cross_validation` |
| `forecast.py` | `model_forecasting` |
| `plot.py` | `plotting` |
| `check.py` | `checks` |
| `sync.py` | `sync_upload` or `sync_download` |
| `publish.py` | `publication` |
| `benchmark/run.py` | `benchmark` (also printed to the terminal) |

`sync.py` leaves out `logs/` by default (its `excluded_folders` setting).

## How files are written

Many steps skip a file that already exists: the downloads, the grids, the temperature, the raw responses. A file cut short by a crash or a killed run would then pass for a complete one. To prevent this, the code writes every data file *atomically*, through `utils.files.writing`:

1. The file is written under a temporary name next to its final path: the path, a random 32-character hexadecimal number and `.part`, such as `FRA.parquet.3f2a….part`.
2. When the writing ends without an error, the temporary file is renamed to the final name. The rename replaces any older file at once.
3. When the writing fails, the temporary file is deleted.

Figures go through `utils.figures.save_figure`, which uses the same mechanism and saves at 300 dpi, cropped to their content.

A `.part` file left behind by a killed run is harmless: no script reads it, and `sync.py` never copies it. You can delete it.

The global archives of the gridded population and GDP are extracted into a temporary folder first, which is renamed once complete, for the same reason.

## When a file is made again

Most steps keep the files that exist and make only the missing or outdated ones. A file is made again when:

| File | Made again when |
|---|---|
| Downloaded global grids (`raw/` of the gridded data) | The file or folder is missing |
| Grids of a code (`processed/` of the gridded data) | The file is missing, or it records other bounds than those of the current shape of the code |
| Reanalysis weather | Also when it may be incomplete: written more than a day ago, and either written less than 7 days after its year ended or ending before the last hour of a past year |
| `temperature/` files | Missing, made by another version of the extraction, from another shape, or outdated as above |
| `gridded_population/totals/<code>.json` | The shape of the code changed (its fingerprint differs) |
| `combined/<code>.parquet` | Its fingerprint (rules, reviews, YAML files of the sources, flags) changed, or a cleaned file of the code is newer |
| ERA5 point series | The CDS may have later hours that are needed, at most once a day |

[Retrieve data](../guides/retrieve.md) and [Weather and socio-economic inputs](../concepts/inputs.md) describe these rules in detail. To force a step to run again, delete its files.

## Manifests

A *manifest* is a JSON file that describes how a file was made. The assembled datasets, the trained models and the results each have one, next to them. Its name is the name of the file without its extension, followed by `.manifest.json`: `all_20260115_093000.parquet` has `all_20260115_093000.manifest.json`. The module `utils/manifest.py` writes and checks them.

The manifest lets a script check that a model, its data and its results belong together, and that no file was replaced after it was made.

### Fields of every manifest

| Field | Meaning |
|---|---|
| `manifest_version` | The version of the manifest format (2). A script refuses a manifest of a higher version than it knows. |
| `kind` | `dataset`, `model` or `results` |
| `file` | The name of the file it describes |
| `sha256` | The SHA-256 checksum of that file |
| `files` | The checksum of each format of the same content, such as the CSV and Parquet files of the same errors |
| `created` | The time it was written, in UTC |
| `code` | `commit`: the git commit of the code, with `+changes` if tracked files had uncommitted changes, or `null` without git. `lockfile`: the checksum of `uv.lock`. |

Paths to other files in a manifest are relative to the data folder, with forward slashes. They stay valid when you copy the data folder elsewhere, such as from a bucket. A file outside the data folder is recorded by its absolute path.

### Fields of each kind

| Kind | Extra fields |
|---|---|
| `dataset` (assembled data) | `purpose` (`training` or `forecasting`); `settings` (the settings of `assemble.py`); `columns` (name and type); `rows`; `entities` (codes); `inputs` (for each input: the number of files read and one checksum of their paths and contents); `provenance` (name and checksum of the provenance CSV, training only) |
| `model` | `algorithm`; `dataset` (path and checksum of the training data); `ml_settings` (the settings of `config/ml_config.yaml`); `model_settings` (the settings of `config/<algorithm>_config.yaml`); `features` (names and types, in order); `target` (column and transformation); `preprocessing` (mean and scale of the standardization of the features, empty for XGBoost); `splits` (the code and local year pairs of each set) |
| `results` | `case` (`validation`, `cross_validation` or `forecasts`); `model` (name and checksum); `dataset` (name, path and checksum); `columns`; `summary`, `predictions` and, for a cross-validation, `models` (name and checksum of each companion file) |
| `results` of a validation or cross-validation | `metric` (MAPE and WAPE, as fractions, lower is better) |
| `results` of a cross-validation | `holdout`, `ml_settings`, `model_settings`, `folds` |
| `results` of a forecast | `units` (`MW`); `annual_totals` (for each year of each code: its hours, the mean before scaling and whether it was scaled to the annual demand) |

### When a script refuses a file

Before a script uses a file with a manifest, it checks the file against it. It stops with an error when:

| Check | Done by | Fails when |
|---|---|---|
| Manifest version | Every script that reads a manifest | The manifest is of a higher version than the code reads |
| Kind | `train.py`, `validate.py`, `cross_validate.py`, `forecast.py` (dataset); `validate.py`, `forecast.py` (model); `plot.py` (results) | The manifest is of another kind |
| Name | The same, and `publish.py` | The manifest does not list the file |
| Checksum | The same, and `publish.py` | The file differs from the recorded one: it was changed or replaced after the manifest was written |
| Purpose | `train.py`, `validate.py`, `cross_validate.py`, `forecast.py` | The data was assembled for another use (training versus forecasting) |
| Target | `validate.py`, `forecast.py` | The model was trained on another target or transformation |
| Preparation | `validate.py`, `forecast.py` | `features` (in order), `categorical_features`, `scaling_variables` or `target` in `config/ml_config.yaml` differ from the training |
| Training data | `validate.py` | The data is not the data of the training, or the training data is missing (give its copy in `data_path`) |
| Sets | `validate.py` | The training and testing sets differ from those of the training, or the model was trained without a testing set |
| Companion files | `plot.py` | The summary or the predictions of the results differ from the recorded ones |
| Model of the results | `publish.py` | Results of a release come from another model than the model of the release |

A file without a manifest is still used, with a warning in the log, because its origin cannot be checked. Two exceptions: `validate.py` then needs `used_validation_set`, and `publish.py` refuses forecasts without a manifest.

### Which file is the latest

When you do not give a path, the scripts take the file with the latest `<time>` in its name. Only names made exactly of the prefix, the time and the extension count. A copy such as `xgboost_model_20260115_093000 (copy).json` or a manifest is never taken for the latest.

The time in the names is the local time of the computer that ran the script.

## Inputs in the code folder

The inputs that come with the code stay in `demandcast/`, next to the scripts. The scripts read them; only a few are written, on purpose.

| Path | What it holds | Written by |
|---|---|---|
| `config/<script>_config.yaml` | The settings of each script (see [Configuration files](configuration.md)) | You |
| `config/ml_config.yaml`, `config/xgboost_config.yaml`, `config/lstm_config.yaml` | The settings of the models | You |
| `config/*.yaml` lists | The countries, continents, subdivisions, related-entity exceptions and Zenodo creators (see [Code architecture](architecture.md#config)) | You |
| `shapes/subdivisions/<ISO3>.yaml` | The definitions of the non-standard subdivisions of each country | You; `shapes/eia.py` writes `USA.yaml` |
| `retrievals/electricity_demand_data_sources/<source>.yaml` | The description of each data source | You |
| `retrievals/socio_economic_data_sources/manual_downloads/` | The IIASA files of the SSP projections, downloaded by hand and kept in the repository | You |
| `retrievals/socio_economic_data_sources/iam_regions_mapping.yaml` | The region of the integrated assessment models of each country | You |
| `checks/reviewed_flags.yaml` | The reviews of the flags of the electricity demand | You |
| `checks/data_availability_summary.csv` | Which codes have the socio-economic data; the other scripts read it to choose the codes | `check.py` (`check: data_availability`) |
| `checks/related_entities.csv`, `checks/related_entities_codes.txt` | The shares of people of overlapping entities, and the codes that the check considered | `check.py` (`check: related_entities`) |
| `publishing/release/README.md`, `publishing/release/metadata.yaml` | The README and metadata of a Zenodo release | You |
| `.env` | Your API keys (never commit it) | You |

Two more places outside the data folder are written by the scripts:

- `plot.py` with `figure: status` writes the figures and numbers of the [Current state](../status.md) page into `webpage/docs/status/`, and the same numbers into `README.md`.
- cartopy downloads the Natural Earth shapes into its own folder, by default in your user folder (`~/.local/share/cartopy` on Linux), not in the data folder.
