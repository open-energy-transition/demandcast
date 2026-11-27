# Train and validate a model

`train.py` trains a model on data assembled for training, and `validate.py` scores it on the years kept out of its training. This page also explains the [model settings](#model-settings) that all the model scripts share.

First assemble data with `target_use: training` (see [Assemble a dataset](assemble.md)). [Models](../concepts/models.md) explains the target, the splits and the metrics.

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
| `reserve_testing_set` | Yes | – | `true` keeps the latest local year of each entity out of training, as the testing set. `false` trains on all years |
| `use_validation_set` | Yes | – | `true` also keeps a validation set out of training (see [Splitting the data in time](../concepts/models.md#splitting-the-data-in-time)) |
| `data_path` | No | latest data | The assembled data. Empty for the latest `assembled_data_for_training_<time>.parquet` |

The algorithm and the features are in [`ml_config.yaml`](#ml_configyaml).

!!! tip
    Keep `reserve_testing_set: true` while you develop, so you can validate the model. A final model for forecasts may train on all years with `reserve_testing_set: false`, but `validate.py` refuses it.

### What it does

1. Reads the model settings, then the assembled data, checked against its manifest. Data assembled for forecasting stops the script.
2. Splits the rows into sets by local year, leaving out the years held out of [related entities](../concepts/models.md#related-entities). The log gives the size of each set.
3. Converts the target to the load relative to the annual mean (see [The target](../concepts/models.md#the-target)).
4. Trains the model on the training set and saves it with its manifest.

### Output files

`<algorithm>` is `xgboost` or `lstm`, and `<time>` the local time of the run, `YYYYMMDD_HHMMSS`.

| File | What it holds |
|---|---|
| `data/models/xgboost/xgboost_model_<time>.json` | An XGBoost model |
| `data/models/lstm/lstm_model_<time>.pt` | An LSTM model, with the statistics of its features |
| `data/models/<algorithm>/<algorithm>_model_<time>.manifest.json` | The [manifest](../concepts/models.md#manifests) |
| `data/logs/model_training_<time>.log` | The log |

The other scripts take the latest model of the algorithm of `ml_config.yaml`, unless you give a path.

## Validate a model

```bash
cd demandcast
uv run validate.py
```

### Options of `validate_config.yaml`

| Option | Required? | Default | What it does |
|---|---|---|---|
| `model_path` | No | latest model | The trained model. Empty for the latest model of the algorithm of `ml_config.yaml` |
| `data_path` | No | the data of the training | The assembled data. Empty for the data recorded in the model's manifest, or, for a model without a manifest, the latest data assembled for training |
| `used_validation_set` | No | from the manifest | Whether the training had a validation set. Needed only for a model without a manifest; otherwise ignored |

The data must be that of the training, with the same checksum. Use `data_path` only for a copy of that file, such as after moving the data folder.

### What it does

1. Finds the model and checks it against its manifest. A model trained without a testing set stops the script.
2. Reads the data of the training and splits it again, with the testing set and, if the training had one, the validation set.
3. Checks that the features (in order), target, settings of `ml_config.yaml`, data and sets are those of the training, and stops otherwise (see [When a script refuses a file](../concepts/models.md#when-a-script-refuses-a-file)).
4. Predicts every set and computes the errors of each entity in each set (see [Metrics](../concepts/models.md#metrics)).
5. Describes each entity of the testing set, summarizes the testing errors by group, and writes the results.

The splits depend on `demandcast/checks/related_entities.csv` and `demandcast/config/related_entities.yaml`. If either changes after the training, the sets can differ and the validation stops: train again.

### Output files

The files go to `data/results/validation/with_<model>/using_<data>/`, where `<model>` and `<data>` are the names of the model and data files without extension.

| File | What it holds |
|---|---|
| `all_<time>.parquet`, `all_<time>.csv` | The errors and the description of each entity (same content) |
| `summary_<time>.csv` | The testing errors by group of entities (see [Reporting by group](../concepts/models.md#reporting-by-group)) |
| `predictions_<time>.parquet` | The actual and predicted load of each hour of the testing set, in MW |
| `all_<time>.manifest.json` | The manifest: model, data, metric, and checksums of the summary and predictions |
| `data/logs/model_validation_<time>.log` | The log, with the errors of each set and the summary by group |

### Columns of `all_<time>`

One row per entity. `<Set>` is `Training`, `Validation` (if used) and `Testing`. An entity without rows in a set has empty values for that set: a superseded entity (see [Related entities](../concepts/models.md#related-entities)) has only training errors.

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the entity | – |
| `<Set> MAPE`, `<Set> WAPE` | The errors of the predictions | fraction |
| `<Set> absolute error (MWh)`, `<Set> demand (MWh)` | The sums of the absolute errors and of the demand | MWh |
| `<Set> MAPE of the complete years scaled to their annual totals` | The MAPE of the predictions scaled as in a forecast, on the complete years only; empty for an entity without one | fraction |
| `Seen in training`, `Training years`, `Scored years`, `Scored hours`, `Mean load (MW)`, `Size class`, `Continent`, `Data source`, `Embedded generation` | The description of the entity in the testing set (see [Reporting by group](../concepts/models.md#reporting-by-group)) | – |

### Columns of `predictions_<time>.parquet`

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the entity | – |
| `Time (UTC)` | The end of the hour, in UTC | – |
| `Local year` | The local year of the hour | – |
| `Load (MW)` | The actual load | MW |
| `Forecast load (MW)` | The prediction times the mean load of its local year, so it has the same annual demand as the actual load | MW |

## Model settings

The model settings are always read from `demandcast/config/`: `--config` does not change them. Every option is checked, and a misspelt one stops the script. An empty algorithm file gives the defaults.

### `ml_config.yaml`

Settings shared by all algorithms, read by `train.py`, `validate.py`, `cross_validate.py` and `forecast.py`. The data is grouped by `Entity code`, split by `Local year` and ordered by `Time (UTC)`.

| Option | Required? | Default | What it does |
|---|---|---|---|
| `algorithm` | Yes | `XGBoost` in the file | `XGBoost` or `LSTM`, in any case. It also picks the settings file, `<algorithm>_config.yaml` |
| `features` | Yes | the 13 [input features](../concepts/models.md#input-features) | The columns of the assembled data that the model reads, in order |
| `target` | Yes | `Load (fraction of annual total)` | The column that the model learns, as the load relative to the annual mean |
| `categorical_features` | No | none | The features to treat as categories; each must be in `features`. The file lists the hour, weekend, holiday, month and monthly temperature rank |
| `scaling_variables` | No (`forecast.py` needs it) | none | The columns whose product is the annual demand in kWh. The file lists `Annual electricity demand per capita (kWh)` and `Population` |

Other columns of the data are kept aside, and the log lists them as not used. A missing feature, target or scaling variable stops the script.

!!! warning
    A model remembers its `features` (and their order), `categorical_features`, `scaling_variables` and `target`. If you change any of them, `validate.py` and `forecast.py` refuse the model: train it again.

### `xgboost_config.yaml`

Read when `algorithm` is `XGBoost`. All options are optional; hyperparameters without a default (–) keep those of XGBoost, such as 100 trees.

| Option | Default | What it does |
|---|---|---|
| `random_state` | `42` | The random seed, for reproducible results |
| `enable_categorical` | `true` | Lets XGBoost split on the categorical features as categories |
| `evaluation_metric` | `mape` | The metric computed on the validation set for early stopping |
| `early_stopping_rounds` | none | Stop adding trees once the validation metric has not improved for this many rounds (at least 1). The model then predicts with the trees up to its best round, which the log gives |
| `n_estimators` | – | The number of trees (at least 1) |
| `max_depth` | – | The maximum depth of a tree (0 or more) |
| `learning_rate` | – | How much each tree corrects the previous ones (above 0) |
| `subsample` | – | The fraction of the rows that each tree uses (above 0, at most 1) |
| `colsample_bytree` | – | The fraction of the features that each tree uses (above 0, at most 1) |
| `min_child_weight` | – | The minimum weight of a leaf (0 or more) |
| `reg_alpha` | – | The L1 regularization (0 or more) |
| `reg_lambda` | – | The L2 regularization (0 or more) |

Early stopping needs both `use_validation_set: true` and `early_stopping_rounds`. With only one of them, the log warns and the training runs all its rounds.

### `lstm_config.yaml`

Read when `algorithm` is `LSTM`. All options are optional; the file holds the defaults. [LSTM](../concepts/models.md#lstm) explains the network.

| Option | Default | What it does |
|---|---|---|
| `n_timesteps` | `24` | The window length: each prediction reads its own row and the `n_timesteps − 1` rows before it (at least 1) |
| `n_units` | `32` | The hidden units of each LSTM layer (at least 1). Smaller values train faster |
| `n_layers` | `1` | The number of stacked LSTM layers (at least 1) |
| `dropout` | `0.0` | The dropout rate between LSTM layers, from 0 to below 1. It has an effect only when `n_layers` is above 1 |
| `epochs` | `5` | The number of passes over the training data (at least 1). More can improve accuracy but take longer |
| `batch_size` | `256` | The rows per batch, in training and prediction (at least 1) |
| `learning_rate` | `0.001` | The learning rate of the Adam optimizer (above 0) |
| `random_state` | `42` | The seed of PyTorch, for reproducible results |

## Choose the algorithm

Start with XGBoost, the default. To compare it with the LSTM ([Algorithms](../concepts/models.md#algorithms)), run `uv sync --extra lstm`, set `algorithm: LSTM` in `ml_config.yaml`, and run the scripts with `uv run --extra lstm`. The validation and the forecast then use the latest LSTM model, and the cross-validation trains LSTMs.

## Common problems

| Symptom | Fix |
|---|---|
| `No data assembled for training found` | Run `assemble.py` with `target_use: training` |
| `No trained model files found` | Train a model of the algorithm of `ml_config.yaml`, or check `algorithm` |
| `The sets of the validation differ from those of the training` | The related entities changed since the training: train again |
| `... has N years of data, which are all held out` (warning) | The entity has too few years: retrieve more, or accept that the model never sees it |

For a model refused by `validate.py`, missing training data or `No module named 'torch'`, see the [FAQ](../help/faq.md#assembling-training-and-forecasting).
