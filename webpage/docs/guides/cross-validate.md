# Cross-validate a model

`cross_validate.py` measures how well the model of `ml_config.yaml` predicts countries and subdivisions that it never saw in training. Use it to estimate the error of a forecast for an entity without demand data. [Cross-validation](../concepts/models.md#cross-validation) explains the method.

Before you start, assemble data with `target_use: training` (see [Assemble a dataset](assemble.md)).

## Run it

```bash
cd demandcast
uv run cross_validate.py                         # settings of config/cross_validate_config.yaml
uv run cross_validate.py --config config/my_cv.yaml
uv run --extra lstm cross_validate.py            # for the LSTM
```

It trains one model per fold, so it takes much longer than `train.py`: 200 models for 200 entities.

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `n_jobs` | No | `1` | The number of folds to train at the same time. `-1` uses all the processors. Each parallel fold holds its own copy of the data in memory |
| `data_path` | No | latest data | The assembled data. Empty for the latest `assembled_data_for_training_<time>.parquet` |
| `holdout` | No | `entity` | What each fold holds out: `entity`, one country or subdivision, or `country`, a country with all its subdivisions |

The algorithm, features and model settings come from `ml_config.yaml` and `<algorithm>_config.yaml` (see [Model settings](train-validate.md#model-settings)). A cross-validation does not use a trained model file.

## Folds

A *fold* trains a model without some entities and scores it on them.

1. The script groups the entities of the data into folds. With `holdout: entity`, each entity is a fold, named after its code. With `holdout: country`, each country is a fold, named after its ISO code, with every code made of that code and a `_` suffix (such as `USA`, `USA_CAL` and `USA_TEX`).
2. Each fold leaves out of training its scored entities and every entity [related](../concepts/models.md#related-entities) to them. The related entities are not scored in that fold.
3. It trains a model on all the years of the remaining entities. There is no temporal split, so no validation set and no early stopping: XGBoost warns if `early_stopping_rounds` is set.
4. It scores the model on all the years of each scored entity, and on its own training rows.

Example: with `holdout: entity`, the fold `ARG_A` (a province of Argentina) leaves out `ARG_A` and Argentina (`ARG`), but trains on the other provinces. With `holdout: country`, the fold `ARG` leaves out Argentina and all its provinces.

## Output files

The files go to `data/results/cross_validation/with_<algorithm>/using_<data>/`, where `<algorithm>` is the algorithm in lower case (such as `xgboost`) and `<data>` the name of the data file without extension. `<time>` is the local time of the run, `YYYYMMDD_HHMMSS`.

| File | What it holds |
|---|---|
| `all_<time>.parquet`, `all_<time>.csv` | The errors and the description of each held-out entity (same content) |
| `summary_<time>.csv` | The testing errors by group of entities (see [Reporting by group](../concepts/models.md#reporting-by-group)) |
| `predictions_<time>.parquet` | The actual and predicted load of each held-out hour in MW, with the [columns of the predictions of a validation](train-validate.md#columns-of-predictions_timeparquet) |
| `models_<time>.zip` | The model of each fold, named after the fold, such as `ARG_A.json` |
| `all_<time>.manifest.json` | The manifest: the data, the metric, the `holdout`, the model settings, the entities each fold scores (`scored`) and does not train on (`left_out`), and the checksums of the other files and of each model |
| `data/logs/model_cross_validation_<time>.log` | The log, with the statistics of the errors and the summary by group |

### Columns of `all_<time>`

One row per held-out entity.

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the held-out entity | – |
| `Training MAPE`, `Training WAPE` | The errors of the fold's model on all its training rows together, shared by all the entities of the fold | fraction |
| `Testing MAPE`, `Testing WAPE` | The errors of the fold's model on the rows of the entity | fraction |
| `Testing absolute error (MWh)`, `Testing demand (MWh)` | The sums of the absolute errors and of the demand of the entity | MWh |
| `Holdout` | The `holdout` of the run | – |
| `Scored years`, `Scored hours`, `Mean load (MW)`, `Size class`, `Continent`, `Data source`, `Embedded generation` | The description of the entity (see [Reporting by group](../concepts/models.md#reporting-by-group)) | – |

There is no `Seen in training` column: a held-out entity is never seen.

## Read the results

- Compare the median testing WAPE with that of a [validation](train-validate.md#validate-a-model). It is larger, because the model never saw the entity.
- Use `holdout: country` for the error on a country without any data, and `holdout: entity` for a subdivision whose country or neighbours have data.
- Look at the summary by `Size class` and `Continent` to find where the model is weak.

`plot.py` draws figures from the latest results (see [Plot figures](plot.md)).
