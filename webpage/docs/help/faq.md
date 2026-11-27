# FAQ and troubleshooting

Answers to common questions and fixes for common errors, grouped by step. If your problem is not here, look at the newest log file in `data/logs/`, then [open an issue](https://github.com/open-energy-transition/demandcast/issues).

## General

### The script printed nothing. Did it work?

The scripts write their messages to a log file, not to the terminal. Open the newest file in `data/logs/`, named after the step and the time of the run.

### How do I redo a step?

Most steps skip files that already exist. Delete the output files of the step, then run it again. Leftover `*.part` files from a crashed run are incomplete and safe to delete.

### I passed `--config`, but my model settings did not change.

`--config` replaces only the settings of the script. The model settings, `ml_config.yaml`, `xgboost_config.yaml` and `lstm_config.yaml`, are always read from `demandcast/config/`. Edit them there.

### My paths like `data/assembled/...` are not found.

Relative paths start from the folder you run the script in, which should be `demandcast/`. If you set `DEMANDCAST_DATA_FOLDER`, use absolute paths, or leave the path empty to use the latest file.

### Files appear in two different data folders.

Give `DEMANDCAST_DATA_FOLDER` an absolute path: a relative one is read from the folder you run the script in. See [Install](../getting-started/install.md#4-choose-where-the-data-goes).

## API keys

### "The … API key is not set. Please set the … environment variable."

Add the key named in the error to `demandcast/.env`. See the [list of keys](../getting-started/install.md#3-add-your-api-keys). A key set in your shell takes priority over `.env`.

### I need `EMBER_API_KEY` for a check or a figure.

`check.py` with `check: data_availability`, and `plot.py` with `figure: data_availability` or `figure: status`, download the Ember data. Add the free key.

### Keys work locally but are rejected in Docker.

Docker's `--env-file` keeps everything after `=`, including comments and quotes. Put comments on their own lines. See [Use Docker](../guides/docker.md).

## Retrieving data

### "The data source 'ENTSOE' is not recognized."

Use the lowercase name of the data source, as in [Data sources](../reference/data-sources.md): `entsoe`.

### "Code X is not available in data source Y."

The data source does not cover that code. The error lists the codes it covers.

### "The option year does not apply to the electricity_demand".

The electricity demand has no year options: it downloads all the years in the source's YAML file. To download only recent data, use `latest_requests`.

### `file` seems to be ignored.

`code` is also set, and it wins over `file`. Leave `code` empty.

### `FileNotFoundError` for my codes file.

The path of `file` starts from the folder you run the script in. Run from `demandcast/`, or give an absolute path.

### "None of the codes in the file are available."

Weather and socio-economic data are retrieved only for codes in `checks/data_availability_summary.csv`. After you add a data source with new codes, run `check.py` with `check: data_availability`.

### `scenario: SSP3-7.0` "is not available for every climate model".

Not every climate model has every scenario. Without `climate_model`, only `SSP1-2.6`, `SSP2-4.5` and `SSP5-8.5` work. Set `climate_model` too, to one of the models that the error lists.

### `scenario: SSP2-4.5` fails for the population.

Each variable uses its own scenario names: `SSP2` for population and GDP, `SSP2-45` for the annual demand per capita, `SSP2-4.5` for the climate. See [Inputs](../concepts/inputs.md).

### The temperature retrieval takes forever or fills the disk.

Without year options, it retrieves 1990 to 2100 for every climate model and scenario. Always set `year`, or `start_year` and `end_year`. The CDS can also queue requests for hours; `reanalysis_source: arco` avoids the queue for past years.

### Eskom or NITI Aayog fails with `FileNotFoundError`.

These sources need files downloaded by hand into `data/electricity_demand/raw/manual_downloads/`. Keep the older files next to the newer ones. See [Retrieve data](../guides/retrieve.md#files-downloaded-by-hand).

### TEPCO fails with HTTP 403.

Its website refuses the downloads of its monthly files, from 2025, from outside Japan; the yearly files until 2024 still download. OCCTO covers the same area.

### "The retrieval of … failed for N of M codes."

The other codes were saved. Run again with `code:` set to one failed code to see its full error.

### The annual flags (`annual_total`, `annual_change`) are missing.

Retrieve `population` and `annual_electricity_demand_per_capita` before the electricity demand, or retrieve the demand again with `offline: true` afterwards.

### The annual demand per capita of a country is the same in its last years.

Ember and the World Bank publish late: the last value of a country is carried forward up to last year, as for the population and the GDP PPP per capita.

## Cleaning, flags and reviews

### I changed a cleaning or flag rule, ran `assemble.py`, and nothing changed.

`assemble.py` cleans again only the sources that have processed data. The log warns about each source whose cleaned data alone was copied, and each combined series without cleaned data: retrieve their electricity demand again.

### Every code is cleaned or combined again, and it is slow.

Any change to the code in `cleaning/`, even a comment, or to the reviews or the YAML files of the sources, changes the [fingerprint](../concepts/glossary.md#fingerprint) of the combined series; a change to `electricity_demand.py` or `flags.py` also changes that of the cleaned data of every source. This is expected.

### My review fails with "Input should be a valid string".

Quote the periods: `- "2020"`, `- "2016-09-28"`.

### My review has no effect.

Its `period` must match the flag exactly, such as `DJF 2022`, and its data source must be the source's name or `combined`. The [flags report](../guides/check.md) lists the reviews that match no flag.

### A source with good data is not used.

It does not give the same quantity as the better source over their common hours, for example net instead of gross demand. See [Combination](../concepts/electricity-demand.md#combination).

### A second source does not fill a short gap.

Other sources fill only gaps of at least a day, by design.

### `assemble.py` stops: the demand "does not say which hours can be used for training".

The combined file could not be combined again because its cleaned data is missing. Retrieve the electricity demand again.

## Assembling, training and forecasting

### "No … data was found for any of the … codes" in `assemble.py`.

The input has no files for any of the codes, in the folder that the error names, for the scenario and climate model that you chose. Retrieve it first.

### A year is missing from the training data.

A year needs at least 90% of its hours, and half of the hours of each month. See `assembled_data_for_training_<time>_coverage.csv`.

### `validate.py` refuses a model trained with `reserve_testing_set: false`.

Validation needs a testing set. Train with `reserve_testing_set: true`.

### `validate.py` or `forecast.py` refuses an older model.

You changed `features`, `categorical_features`, `scaling_variables` or `target` in `ml_config.yaml` since the training, or ran the related-entities check again. Restore the settings or train again.

### `validate.py` says the data of the training is not found.

Give the path of a copy of the same file in `data_path`. It must be the same file: its checksum is checked.

### `No module named 'torch'`.

The LSTM needs `uv sync --extra lstm`, then `uv run --extra lstm <script>.py`.

### After switching to the LSTM, the scripts cannot find my XGBoost model.

The latest model is taken from the folder of the algorithm in `ml_config.yaml`. Switch it back, or give `model_path`.

### The forecast of the current year does not add up to the annual demand.

Only complete years are scaled to the annual demand. The manifest of the forecasts records the status of each year in `annual_totals`.

### Cross-validation runs out of memory.

Each parallel job copies the data. Lower `n_jobs`.

## Checks and figures

### A test fails after I added a data source.

- `test_numbers_of_the_readme_are_current`: run `plot.py` with `figure: status`, or paste the sentence of the error into the README and `webpage/docs/status/numbers.md`.
- `test_all_codes_were_checked`: run `check.py` with `check: related_entities` and commit the two files it writes in `checks/`.

## Sharing, publishing and Docker

### A file differs between my computer and the bucket.

`sync.py` never overwrites. Delete the version you do not want, together with its manifest, and copy again.

### After downloading the data folder, the next retrieval extracts every weather grid again.

Expected: the downloaded files get new modification times. Nothing is downloaded again.

### A temperature year downloaded from the bucket is incomplete.

It was extracted before the reanalysis of its year was complete. The file records when it was extracted, which a copy keeps, so the next retrieval of the temperature of that year extracts it again (see [When files are extracted again](../concepts/inputs.md#when-files-are-extracted-again)). Retrieve it before you assemble the data.

### A folder of the data folder that is a symbolic link is not uploaded.

`sync.py` does not follow linked folders, and names them in a warning of the log. Point `DEMANDCAST_DATA_FOLDER` at the real folder instead.

### Where is my Zenodo draft?

Its address is in the log, `data/logs/publication_<time>.log`.

### My data is gone after the Docker container stopped.

Mount the data folder into the container. See [Use Docker](../guides/docker.md).
