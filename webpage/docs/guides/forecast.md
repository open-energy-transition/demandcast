# Forecast

`forecast.py` predicts the hourly electricity demand, in MW, of each country or subdivision of a dataset assembled for forecasting. Run it once you have a trained model and the inputs of the years you want to forecast.

## Before you start

You need:

1. A trained model of the algorithm of `ml_config.yaml` (see [Train and validate](train-validate.md)).
2. Data assembled with `target_use: forecasting` for the entities and years you want (see [Assemble a dataset](assemble.md)). Leave the scenarios empty for past years; choose scenarios for future years.
3. `scaling_variables` in `ml_config.yaml`, normally `Annual electricity demand per capita (kWh)` and `Population`. Without them the script stops, because it cannot convert the predictions to MW.

## Run it

```bash
cd demandcast
uv run forecast.py                                # settings of config/forecast_config.yaml
uv run forecast.py --config config/my_forecast.yaml
uv run --extra lstm forecast.py                   # with an LSTM model
```

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `model_path` | No | latest model | The path of the trained model. Empty for the latest model of the algorithm of `ml_config.yaml` in `data/models/<algorithm>/` |
| `data_path` | No | latest data | The path of the assembled data. Empty for the latest `assembled_data_for_forecasting_<time>.parquet` in `data/assembled/` |

Relative paths are relative to the folder you run from, normally `demandcast/`. The model must match the `algorithm` of `ml_config.yaml`: an LSTM model needs `algorithm: LSTM`.

## What it does

1. Reads the assembled data and checks it against its manifest. Data assembled for training stops the script.
2. Finds the model and checks it against its manifest. The features (in order), the categorical features, the scaling variables and the target must be those of the training; otherwise the script stops.
3. Predicts the load relative to the annual mean of each hour (see [The target](../concepts/models.md#the-target)).
4. Sets negative predictions to zero.
5. Scales the predictions of each complete local year of each entity to a mean of 1. A *complete* year has a row for each of its hours (8760, or 8784 in a leap year). Incomplete years, and years whose predictions are all zero, are not scaled, and the log lists them.
6. Converts the predictions to MW with the annual demand of each row, the product of the scaling variables:

    ```text
    Forecast load (MW) = prediction / hours in the year × annual demand per capita (kWh) × population / 1000
    ```

7. Writes the forecasts and their manifest.

So the forecasts of each complete year sum to its annual demand in MWh: the model gives the hourly shape, and the scenario gives the total. An incomplete year does not sum exactly to its share of the annual demand.

The script stops if a prediction is not a finite number, if an hour of an entity has two rows, or if the annual demand of a row is not a positive number.

## Output files

The files go to `data/results/forecasts/with_<model>/using_<data>/`, where `<model>` and `<data>` are the names of the model and data files without extension. `<time>` is the local time of the run, `YYYYMMDD_HHMMSS`.

| File | What it holds |
|---|---|
| `all_<time>.parquet` | The forecasts, one row per hour and entity |
| `all_<time>.manifest.json` | The manifest: the model and data with their checksums, the columns, the unit (`MW`) and, in `annual_totals`, the scaling status of each year of each entity |
| `data/logs/model_forecasting_<time>.log` | The log |

### Columns of the forecasts

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` | The end of the hour, in UTC | – |
| `Entity code` | The code of the country or subdivision | – |
| The features of `ml_config.yaml` | The inputs of the model for the hour (see [Input features](../concepts/models.md#input-features)); categorical features are stored as categories | as in the assembled data |
| `Local year` | The local year of the start of the hour | – |
| Other columns of the assembled data | Any column that is not a feature, target or scaling variable | as in the assembled data |
| `Forecast load (MW)` | The forecast mean demand of the hour | MW |

`Population` and the other scaling variables that are not features are not in the output. The time is the end of each hour in UTC, like the electricity demand: the hour from 00:00 to 01:00 UTC has the time 01:00.

### `annual_totals` in the manifest

One record per entity and local year:

| Field | Meaning |
|---|---|
| `Entity code` | The code of the entity |
| `Local year` | The local year |
| `Hours` | The number of distinct hours of the year in the data |
| `Mean before scaling` | The mean of the predictions of the year, before the scaling |
| `Status` | `scaled`; `incomplete`, for a year without all its hours; or `zero`, for a complete year whose predictions are all zero |

A `Mean before scaling` far from 1 means the model's shape alone would have missed the annual total by that factor.

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `A forecast needs the scaling_variables` | `scaling_variables` is empty in `ml_config.yaml` | Restore it |
| `No data assembled for forecasting found` | No forecasting data in `data/assembled/` | Run `assemble.py` with `target_use: forecasting` |
| `The data ... was assembled for training, not for forecasting` | `data_path` points to training data | Assemble data for forecasting |
| `The data is not prepared as for the training of the model` | `ml_config.yaml` changed since the training | Restore the settings, or train again |
| `The annual demand of N rows is not a positive number` | A scaling variable is missing or zero for some rows | Retrieve the indicator again for those entities and years |
| The forecast misses the last hours of a year (status `incomplete`) | The temperature does not cover the whole local year, such as for the current year | Forecast complete years, or accept unscaled predictions |
