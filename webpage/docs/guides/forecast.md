# Forecast

`forecast.py` predicts the hourly electricity demand, in MW, of each country or subdivision of a dataset assembled for forecasting.

## Before you start

You need:

1. A trained model of the algorithm of `ml_config.yaml` (see [Train and validate](train-validate.md)).
2. Data assembled with `target_use: forecasting` for the entities and years you want (see [Assemble a dataset](assemble.md)). Leave the scenarios empty for past years; choose scenarios for future years.
3. `scaling_variables` in `ml_config.yaml`, normally `Annual electricity demand per capita (kWh)` and `Population`. Without them the script stops with `A forecast needs the scaling_variables`.

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
| `model_path` | No | latest model | The trained model. Empty for the latest model in `data/models/<algorithm>/`, for the algorithm of `ml_config.yaml` |
| `data_path` | No | latest data | The assembled data. Empty for the latest `assembled_data_for_forecasting_<time>.parquet` in `data/assembled/` |

Relative paths are relative to the folder you run from, normally `demandcast/`. The model must match the `algorithm` of `ml_config.yaml`: an LSTM model needs `algorithm: LSTM`.

## What it does

1. Reads the assembled data, checked against its manifest. Data assembled for training stops the script.
2. Finds the model, checked against its manifest: the features (in order), categorical features, scaling variables and target must be those of the training.
3. Predicts the load relative to the annual mean of each hour.
4. Scales the predictions of each complete local year to the annual demand and converts them to MW (see [From the predictions to MW](../concepts/models.md#from-the-predictions-to-mw)).
5. Writes the forecasts and their manifest.

So the forecasts of each complete year (a row for each of its 8760 or 8784 hours) sum to its annual demand: the model gives the hourly shape, and the scenario the total. Incomplete years are not scaled and do not sum exactly.

## Output files

The files go to `data/results/forecasts/with_<model>/using_<data>/`, where `<model>` and `<data>` are the names of the model and data files without extension. `<time>` is the local time of the run, `YYYYMMDD_HHMMSS`.

| File | What it holds |
|---|---|
| `all_<time>.parquet` | The forecasts, one row per hour and entity |
| `all_<time>.manifest.json` | The manifest: the model and data with their checksums, the columns, the unit (`MW`) and, in `annual_totals`, the scaling status of each year |
| `data/logs/model_forecasting_<time>.log` | The log |

### Columns of the forecasts

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` | The end of the hour, in UTC: the hour from 00:00 to 01:00 UTC has the time 01:00 | – |
| `Entity code` | The code of the country or subdivision | – |
| The `features` of `ml_config.yaml` | The inputs of the model (see [Input features](../concepts/models.md#input-features)); categorical features are stored as categories | as in the assembled data |
| `Local year` and any other column that is not a feature or scaling variable | As in the assembled data | – |
| `Forecast load (MW)` | The forecast mean demand of the hour | MW |

Scaling variables that are not features, such as `Population`, are not in the output.

### `annual_totals` in the manifest

One record per entity and local year:

| Field | Meaning |
|---|---|
| `Entity code`, `Local year` | The entity and the local year |
| `Hours` | The number of distinct hours of the year in the data |
| `Mean before scaling` | The mean of the predictions of the year, before the scaling |
| `Status` | `scaled`; `incomplete`, for a year without all its hours; or `zero`, for a complete year whose predictions are all zero |

A `Mean before scaling` far from 1 means the model's shape alone would have missed the annual total by that factor.

## Common problems

| Symptom | Fix |
|---|---|
| `A forecast needs the scaling_variables` | Restore `scaling_variables` in `ml_config.yaml` |
| `No data assembled for forecasting found` | Run `assemble.py` with `target_use: forecasting` |
| `The data ... was assembled for training, not for forecasting` | `data_path` points to training data: assemble data for forecasting |
| `The data is not prepared as for the training of the model` | `ml_config.yaml` changed since the training: restore the settings, or train again |
| `The annual demand of N rows is not a positive number` | A scaling variable is missing or zero for some rows: retrieve the indicator again for those entities and years |

For a year that does not add up to the annual demand, see the [FAQ](../help/faq.md#assembling-training-and-forecasting). The other stops are listed in [From the predictions to MW](../concepts/models.md#from-the-predictions-to-mw).
