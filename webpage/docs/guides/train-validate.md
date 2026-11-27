# Train and validate a model

`train.py` trains a model on data assembled for training, and `validate.py` scores it on the years kept out of its training. This page also explains the model settings files that these scripts, `cross_validate.py` and `forecast.py` share.

Before you start, assemble data with `target_use: training` (see [Assemble a dataset](assemble.md)). To understand the target, the splits and the metrics, read [Models](../concepts/models.md).

## Train a model

```bash
cd demandcast
uv run train.py                                # settings of config/train_config.yaml
uv run train.py --config config/my_training.yaml
uv run --extra lstm train.py                   # for the LSTM, with PyTorch installed
```

### Options of `train_config.yaml`

| Option | Required? | Default | What it does |
|---|---|---|---|
| `reserve_testing_set` | Yes | – | `true` keeps the latest local year of each entity out of training, as the testing set that `validate.py` scores. `false` trains on all years |
| `use_validation_set` | Yes | – | `true` also keeps a validation set out of training: the year before the testing year, or the latest year without a testing set. XGBoost uses it to stop early if `early_stopping_rounds` is set; otherwise its year is only left out |
| `data_path` | No | latest data | The path of the assembled data. Empty for the latest `assembled_data_for_training_<time>.parquet` in the data folder |

The algorithm and the features are not here: they are in [`ml_config.yaml`](#ml_configyaml).

!!! tip
    Keep `reserve_testing_set: true` while you develop, so that you can validate the model. For a final model that forecasts, you may train on all years with `reserve_testing_set: false`, but `validate.py` then refuses that model.

### What it does

1. Reads `ml_config.yaml` and the settings file of the algorithm.
2. Reads the assembled data and checks it against its manifest. Data assembled for forecasting stops the script.
3. Splits the rows into sets by local year, leaving out the years held out of related entities (see [Splitting the data in time](../concepts/models.md#splitting-the-data-in-time)). The log gives the size of each set.
4. Converts the target to the load relative to the annual mean (see [The target](../concepts/models.md#the-target)).
5. Trains the model on the training set and saves it with its manifest.

### Output files

| File | What it holds |
|---|---|
| `data/models/<algorithm>/<algorithm>_model_<time>.json` | An XGBoost model (`<algorithm>` is `xgboost`) |
| `data/models/<algorithm>/<algorithm>_model_<time>.pt` | An LSTM model (`<algorithm>` is `lstm`), with the statistics of its features |
| `data/models/<algorithm>/<algorithm>_model_<time>.manifest.json` | The manifest: the dataset and its checksum, the settings, the features in order, the target, and the entities and local years of each set (see [Manifests](../concepts/models.md#manifests)) |
| `data/logs/model_training_<time>.log` | The log |

`<time>` is the local time of the run, `YYYYMMDD_HHMMSS`. The other scripts take the latest model of the algorithm of `ml_config.yaml`, by the time in its name, unless you give a path.

## Validate a model

```bash
cd demandcast
uv run validate.py
```

### Options of `validate_config.yaml`

| Option | Required? | Default | What it does |
|---|---|---|---|
| `model_path` | No | latest model | The path of the trained model. Empty for the latest model of the algorithm of `ml_config.yaml` |
| `data_path` | No | the data of the training | The path of the assembled data. Empty for the data recorded in the manifest of the model. A model without a manifest takes the latest data assembled for training |
| `used_validation_set` | No | from the manifest | Whether the training had a validation set. Needed only for a model without a manifest |

The data must be that of the training: `validate.py` compares its checksum with the one in the manifest. Use `data_path` only to point to a copy of the same file, for example after you moved the data folder.

### What it does

1. Finds the model and checks it against its manifest. A model trained without a testing set stops the script.
2. Reads the data of the training and splits it again, with the testing set and, if the training had one, the validation set.
3. Checks that the model was trained with the same features in the same order, target, preparation settings, data and sets. If anything differs, it stops (see [When a script refuses a file](../concepts/models.md#when-a-script-refuses-a-file)).
4. Predicts every set and computes the MAPE and WAPE of each entity in each set (see [Metrics](../concepts/models.md#metrics)).
5. Describes each entity of the testing set, summarizes the testing errors by group, and writes the results.

The splits depend on `demandcast/checks/related_entities.csv` and `demandcast/config/related_entities.yaml`. If you change either between training and validation, the sets can differ, and the validation stops: train again.

### Output files

The files go to `data/results/validation/with_<model>/using_<data>/`, where `<model>` and `<data>` are the names of the model and data files without extension. `<time>` is the local time of the run.

| File | What it holds |
|---|---|
| `all_<time>.parquet`, `all_<time>.csv` | The errors and the description of each entity (same content) |
| `summary_<time>.csv` | The testing errors by group of entities (see [Reporting by group](../concepts/models.md#reporting-by-group)) |
| `predictions_<time>.parquet` | The actual and predicted load of each hour of the testing set, in MW |
| `all_<time>.manifest.json` | The manifest: model, data, metric, and checksums of the summary and predictions |
| `data/logs/model_validation_<time>.log` | The log, with the errors of each set and the summary by group |

### Columns of `all_<time>`

One row per entity. `<Set>` is `Training`, `Validation` (if used) and `Testing`. An entity without rows in a set has empty values for that set.

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the entity | – |
| `<Set> MAPE` | The mean absolute percentage error of the predictions | fraction |
| `<Set> WAPE` | The weighted absolute percentage error of the predictions | fraction |
| `<Set> absolute error (MWh)` | The sum of the absolute errors of the hours | MWh |
| `<Set> demand (MWh)` | The sum of the demand of the hours | MWh |
| `<Set> MAPE of the complete years scaled to their annual totals` | The MAPE of the predictions scaled as in a forecast, on the complete years only | fraction |
| `Seen in training`, `Training years` | Whether, and for how many years, the model saw the entity in training | –, years |
| `Scored years`, `Scored hours` | The testing years and hours of the entity | years, hours |
| `Mean load (MW)`, `Size class` | The mean testing load, and `Small`, `Medium` or `Large` | MW, – |
| `Continent`, `Data source`, `Embedded generation` | See [Reporting by group](../concepts/models.md#reporting-by-group) | – |

A superseded entity (see [Related entities](../concepts/models.md#related-entities)) has only training errors.

### Columns of `predictions_<time>.parquet`

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the entity | – |
| `Time (UTC)` | The end of the hour, in UTC | – |
| `Local year` | The local year of the hour | – |
| `Load (MW)` | The actual load | MW |
| `Forecast load (MW)` | The prediction times the mean load of its local year, so it has the same annual demand as the actual load | MW |

## Model settings

The model settings are in `demandcast/config/` and are always read from there: `--config` does not change them. Every option is checked, and a misspelt one stops the script.

### `ml_config.yaml`

Settings shared by all algorithms, read by `train.py`, `validate.py`, `cross_validate.py` and `forecast.py`. The data is grouped by `Entity code`, split by `Local year` and ordered by `Time (UTC)`.

| Option | Required? | Default | What it does |
|---|---|---|---|
| `algorithm` | Yes | `XGBoost` in the file | The algorithm: `XGBoost` or `LSTM`, in any case. It also picks the settings file, `<algorithm>_config.yaml` |
| `features` | Yes | the 13 features of [Input features](../concepts/models.md#input-features) | The columns of the assembled data that the model reads, in order |
| `target` | Yes | `Load (fraction of annual total)` | The column that the model learns, as the load relative to the annual mean |
| `categorical_features` | No | none | The features to treat as categories. Each must also be in `features` and hold whole numbers. The file lists the hour, weekend, holiday, month and monthly temperature rank |
| `scaling_variables` | No (but `forecast.py` needs it) | none | The columns whose product is the annual demand in kWh that converts predictions to MW. The file lists `Annual electricity demand per capita (kWh)` and `Population` |

Columns of the data that are not features, target, categorical features or scaling variables are kept aside, and the log lists them. A feature, target or scaling variable missing from the data stops the script.

!!! warning
    A model remembers its `features` (and their order), `categorical_features`, `scaling_variables` and `target`. If you change any of them, `validate.py` and `forecast.py` refuse the model: train it again.

### `xgboost_config.yaml`

Read when `algorithm` is `XGBoost`. Empty hyperparameters keep the defaults of XGBoost (for example 100 trees).

| Option | Required? | Default | What it does |
|---|---|---|---|
| `random_state` | No | `42` | The random seed, for reproducible results |
| `enable_categorical` | No | `true` | Lets XGBoost split on the categorical features as categories |
| `evaluation_metric` | No | `mape` | The metric computed on the validation set, which stops the training with `early_stopping_rounds` |
| `early_stopping_rounds` | No | none | With a validation set, stop adding trees once the metric of the validation set has not improved for this many rounds (at least 1). The model then predicts with the trees up to its best round. Empty for no early stopping |
| `n_estimators` | No | XGBoost default | The number of trees (at least 1) |
| `max_depth` | No | XGBoost default | The maximum depth of a tree (0 or more) |
| `learning_rate` | No | XGBoost default | How much each tree corrects the previous ones (above 0) |
| `subsample` | No | XGBoost default | The fraction of the rows that each tree uses (above 0, at most 1) |
| `colsample_bytree` | No | XGBoost default | The fraction of the features that each tree uses (above 0, at most 1) |
| `min_child_weight` | No | XGBoost default | The minimum weight of a leaf (0 or more) |
| `reg_alpha` | No | XGBoost default | The L1 regularization (0 or more) |
| `reg_lambda` | No | XGBoost default | The L2 regularization (0 or more) |

Early stopping needs both `use_validation_set: true` and `early_stopping_rounds`. With only one of them, the log warns and the training runs all its rounds.

### `lstm_config.yaml`

Read when `algorithm` is `LSTM`. The values in the file are the defaults. See [LSTM](../concepts/models.md#lstm) for how the network works.

| Option | Required? | Default | What it does |
|---|---|---|---|
| `n_timesteps` | No | `24` | The length of the window: each prediction reads its own row and the `n_timesteps − 1` rows before it of the same entity (at least 1) |
| `n_units` | No | `32` | The hidden units of each LSTM layer (at least 1). Smaller values train faster |
| `n_layers` | No | `1` | The number of stacked LSTM layers (at least 1) |
| `dropout` | No | `0.0` | The dropout rate between LSTM layers, from 0 to below 1. It has an effect only when `n_layers` is above 1 |
| `epochs` | No | `5` | The number of passes over the training data (at least 1). More passes can improve accuracy but take longer |
| `batch_size` | No | `256` | The number of rows per batch, in training and prediction (at least 1) |
| `learning_rate` | No | `0.001` | The learning rate of the Adam optimizer (above 0) |
| `random_state` | No | `42` | The seed of PyTorch, for reproducible results |

## Choose the algorithm

| | XGBoost | LSTM |
|---|---|---|
| When to use | The default; start here | To compare a sequence model with XGBoost |
| Install | Included | `uv sync --extra lstm`, and run with `uv run --extra lstm` |
| Uses the validation set | For early stopping | No |
| Model file | `.json` | `.pt` |

To switch, set `algorithm: LSTM` in `ml_config.yaml` and train again. The validation and the forecast then use the latest LSTM model, and the cross-validation trains LSTMs. Without PyTorch installed, the scripts stop with `No module named 'torch'`.

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `No data assembled for training found` | No training data in `data/assembled/` | Run `assemble.py` with `target_use: training` |
| `No trained model files found` | No model of the algorithm of `ml_config.yaml` | Train one, or check `algorithm` |
| `The model was trained without a testing set` | Trained with `reserve_testing_set: false` | Train again with `reserve_testing_set: true` |
| `The data of the training of the model ... is not found` | The training data was moved or deleted | Give the path of a copy in `data_path` |
| `The sets of the validation differ from those of the training` | The related entities changed since the training | Train again |
| `The data is not prepared as for the training of the model` | `ml_config.yaml` changed since the training | Restore the settings, or train again |
| `... has N years of data, which are all held out` (warning) | The entity has too few years | Retrieve more years, or accept that the model never sees it |
