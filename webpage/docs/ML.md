# Machine Learning

The machine learning modules are responsible for training models to forecast hourly electricity demand based on historical data, weather conditions, and socioeconomic indicators. The trained models can then be used to generate forecasts for future periods or for regions without historical data.

## Overview

The machine learning process in DemandCast follows a structured pipeline that transforms raw data into electricity demand forecasts. The process consists of four main stages:

1. **Data Assembly**: Combine electricity demand, temperature, population, GDP, and annual electricity demand data into a unified dataset with consistent time zones and units.
2. **Model Training**: Train machine learning models on historical data to learn patterns in electricity demand based on temporal, weather, and socioeconomic features.
3. **Model Validation**: Evaluate model performance on held-out test data and through cross-validation to assess generalization to unseen regions.
4. **Forecasting**: Apply trained models to generate electricity demand forecasts for future time periods or regions without historical data.

### Key Concepts

**Target Variable: Load (fraction of annual total)**

The target variable represents normalized hourly electricity consumption. Take each hour's electricity demand (in MW) and divide it by the total yearly electricity demand for that region. This produces a fraction of the year's electricity consumed in that hour. For example, 0.00015 means this hour consumed 0.015% of the year's total electricity. This normalization allows the model to learn patterns across regions of different sizes—a small country and a large country both have values in a comparable range.

**What the models learn: Load relative to the annual mean**

The fraction of the annual total of an average hour is about 1/8760, too small for the models: the gain of an XGBoost split scales with the square of the target, so at that magnitude the model barely splits and rarely uses the continuous features. When preparing the data, `ml_models.data.to_load_relative_to_annual_mean()` therefore multiplies the target by the hours in its local year (8760, or 8784 in leap years), giving the load relative to the annual mean, without unit: 1.0 is an average hour, and 1.2 an hour with 20% more demand than average. All models are trained on this target, and the manifest of each model records it (see [the manifests](#manifests)). The assembled data keeps the fraction of the annual total.

**From the predictions to MW**

The annual electricity demand of a forecast, the product of the annual demand per capita (kWh) and the population, is the total of its year, and the hourly profile of the model distributes it. The predictions of a year do not have a mean of exactly 1, so `forecast.py` scales those of each complete local year of each country or subdivision, with all its hours, to a mean of 1 (`ml_models.data.normalize_to_annual_totals()`): their MW then sum to the annual demand. A negative prediction is zero; a prediction that is not a number, or an hour with two predictions, stops the forecast. The predictions of a year without all its hours, and of a complete year whose predictions are all zero, are not scaled, which the log reports, and the manifest of the forecasts gives the status of each year: `scaled`, `incomplete` or `zero`. The predictions are then converted back to the fraction of the annual total and multiplied by the annual demand in kWh, divided by 1000 for MW. The validation and cross-validation score the predictions as the model gives them.

**Temporal Splitting**

Unlike typical machine learning where data is randomly split, temporal splitting is required for time-series forecasting. Random splitting would "leak" future information into training, making results unrealistically good. The dataset is split using the following logic:

- **Test set**: For each region, the most recent local year for which that region has data (optional)
- **Validation set**: For each region, the most recent year with data before the test year, or the most recent year without a test set (optional)
- **Training set**: For each region, all remaining earlier years with data

The years are those that the region has, so a missing year is skipped: with data for 2019, 2021 and 2023, the test set is 2023, the validation set 2021 and the training set 2019. No year of the training set comes after those held out. A region with fewer years than the held-out sets gives its years to the test set first, then to the validation set, and none to training, which the log reports.

This ensures the model is evaluated on future time periods it hasn't seen during training, which is critical for time-series forecasting.

**Leave-One-Group-Out (LOGO) Cross-Validation**

LOGO cross-validation tests model generalization across regions by training on all regions except one and evaluating on the held-out region. This process is repeated for each region. By default, each fold holds out one entity code (`holdout: entity`), so a fold that holds out Argentina still trains on the provinces of Argentina: this measures the error on a held-out entity, not on a country that the model has never seen. With `holdout: country`, each fold holds out a country with all its subdivisions, which measures the error on an unseen country. The results say which holdout they used.

**Feature Types**

Machine learning features can be classified as either categorical or continuous:

- **Continuous features**: Numbers with meaningful distance (e.g., temperature: 20°C is halfway between 10°C and 30°C)
- **Categorical features**: Numbers used as labels (e.g., month: February isn't "twice" January, it's just a different category)

Different algorithms handle these feature types differently, which affects model performance and training efficiency.

### Input Features

The ML models use the following features to predict electricity demand:

**Temporal Features:**

- Local hour of the day (0-23)
- Local month of the year (1-12)
- Local weekend indicator (1 if Saturday or Sunday, 0 otherwise)
- Local holiday indicator (1 on a public holiday of the country, or of the state or province if the [holidays](https://pypi.org/project/holidays/) package knows it, 0 otherwise), added by `assemble.py` (`demandcast/utils/public_holidays.py`)

**Weather Features:**

- Temperature in the most populous grid cell (K)
- Temperature averaged over the 3 most populous grid cells (K)
- Annual average temperature in the most populous grid cell (K)
- Monthly average temperature in the most populous grid cell (K)
- Monthly temperature rank in the most populous grid cell (1 = warmest month, 12 = coldest month)
- 5th percentile temperature in the most populous grid cell (K)
- 95th percentile temperature in the most populous grid cell (K)

**Socioeconomic Features:**

- GDP PPP per capita (2021 international $)
- Annual electricity demand per capita (kWh)

**Categorical Features:**

The following features are treated as categorical (labels rather than measurements): local hour of the day, local month of the year, local weekend indicator, and monthly temperature rank.

## XGBoost Algorithm

DemandCast currently implements XGBoost (eXtreme Gradient Boosting) as its primary machine learning algorithm. XGBoost is an optimized distributed gradient boosting library designed to be highly efficient, flexible, and portable. It implements machine learning algorithms under the Gradient Boosting framework ([XGBoost documentation](https://xgboost.readthedocs.io/en/stable/)).

### Motivation

The core motivation for using XGBoost to generate hourly electricity demand forecasts is based on previous work in the literature that applies gradient boosting models to load forecasting (e.g. [Mattsson et al., 2021](https://doi.org/10.1016/j.esr.2020.100606)). Our approach uses socioeconomic and weather parameters as inputs to predict hourly electricity demand, in line with these studies that combine meteorological and economic indicators for improved forecast accuracy. XGBoost is fast to train and perform inference, handles both categorical and continuous features natively, and provides built-in regularization to prevent overfitting. These characteristics make it an excellent baseline model that can be expanded upon in future work.

### XGBoost Configuration

The XGBoost-specific configuration is specified in `demandcast/config/xgboost_config.yaml` and includes:

- Random seed for reproducibility
- Categorical feature support enablement
- Evaluation metric (Mean Absolute Percentage Error - MAPE)
- Optionally, the hyperparameters `n_estimators`, `max_depth`, `learning_rate`, `subsample`, `colsample_bytree`, `min_child_weight`, `reg_alpha` and `reg_lambda`, which keep the defaults of XGBoost when they are not given. Another setting is an error.

## LSTM Algorithm

Long Short-Term Memory (LSTM) networks extend DemandCast's forecasting toolkit as an alternative to XGBoost, bringing a sequence-aware architecture that is well-suited to the hourly, temporally ordered structure of electricity demand data.

### Motivation

The motivation for including an LSTM model builds on peer-reviewed work that benchmarks deep sequence models against classical time-series and gradient boosting approaches for energy demand forecasting (e.g. [Ul Rehman and Iqbal, 2025](https://doi.org/10.1186/s42162-025-00587-5)). Research comparing LSTM, Seq2Seq, and Prophet on smart-meter data demonstrates that LSTM networks consistently outperform statistical baselines when capturing daily and weekly periodicities in disaggregated load profiles. Electricity demand is an inherently sequential signal: the load at any given hour is influenced by the hours immediately preceding it—morning warm-up, evening peak, overnight trough—and an architecture that learns these temporal dependencies directly from the input sequence is a natural complement to XGBoost. Where XGBoost sees each row as an independent observation and relies on engineered temporal features (hour-of-day, month, weekend flag) to encode context, the LSTM models that context implicitly through its recurrent hidden state. Together, the two algorithms offer a gradient-boosting baseline and a sequence-learning alternative that can be compared under identical evaluation protocols.

### Architecture

The LSTM implementation in DemandCast (`ml_models/lstm.py`) is built on PyTorch's `nn.LSTM` module paired with a single linear output layer. The network accepts input tensors of shape `(batch, n_timesteps, n_features)`, passes them through one or more stacked LSTM layers, and projects the final hidden state to a scalar prediction via `nn.Linear(n_units, 1)`. Dropout can be applied between stacked layers when `n_layers > 1`.

The `LSTMRegressor` class wraps this network in a scikit-learn-compatible estimator, giving it `fit()` and `predict()` methods that accept `pandas.DataFrame` and `pandas.Series` inputs. Cross-validation trains and scores the LSTM and XGBoost with the same Leave-One-Group-Out loop, which passes the entity codes to both the training and the predictions.

Sequence construction is entity-aware and time-aware. Each training or inference sample requires a lookback window of `n_timesteps` consecutive hours. Rather than drawing rows across entity (country or region) boundaries or across gaps, the sequence builder starts a new run at each change of the entity label of the `"group"` column of the prepared dataset, and at each row of the `"time"` column that is not one hour after the row before it, such as after a missing hour or a missing year, and zero-pads the leading edge of each new run. The windows are built batch by batch, so that the windows of all the rows, which would take tens of gigabytes for the whole dataset, are never in memory at once.

The features are standardized with the mean and standard deviation of each feature in the training rows, which are saved with the model and applied to the rows that it predicts: features of very different magnitudes, such as the GDP per capita and the temperature, would otherwise saturate the gates of the LSTM. A model saved before this standardization takes the features as they are.

### LSTM Configuration

The LSTM-specific configuration is specified in `demandcast/config/lstm_config.yaml`. The values listed below are the defaults; the dimensions, epochs and batch size must be at least 1, the dropout from 0 to below 1, and the learning rate positive. Another setting is an error.

| Name | Type | Default | Required / Optional | Description |
|---|---|---|---|---|
| `n_timesteps` | `int` | `24` | Required | Lookback window length in timesteps. Each prediction draws on the preceding `n_timesteps` rows of the same entity. |
| `n_units` | `int` | `32` | Required | Number of LSTM hidden units per layer. Smaller values train faster on CPU. |
| `n_layers` | `int` | `1` | Required | Number of stacked LSTM layers. Dropout only takes effect when `n_layers > 1`. |
| `dropout` | `float` | `0.0` | Required | Dropout rate applied between LSTM layers. Only meaningful when `n_layers > 1`. |
| `epochs` | `int` | `5` | Required | Number of full passes over the training data. Increase for better accuracy at the cost of training time. |
| `batch_size` | `int` | `256` | Required | Mini-batch size used for both training and inference. |
| `learning_rate` | `float` | `0.001` | Required | Adam optimiser learning rate. |
| `random_state` | `int` | `42` | Required | Random seed passed to `torch.manual_seed` for reproducibility. |

To use the LSTM algorithm, set `algorithm: LSTM` in `ml_config.yaml`.

### Dependencies

The LSTM model requires `torch>=2.0.0`, from the optional `lstm` extra of `demandcast/pyproject.toml`: install it with `uv sync --extra lstm`. XGBoost works without it. uv installs the CPU-only build of PyTorch, which is sufficient for the default configuration; no GPU is required. Training time on CPU with the default hyperparameters is comparable to XGBoost for typical dataset sizes.

### Input and Output Format

The LSTM model consumes the same `prepared_dataset` structure produced by `ml_models.data.prepare_split_datasets` as XGBoost. Each split (`"training"`, `"validation"`, `"testing"`) is a dictionary containing:

- `"features"` — `pandas.DataFrame` of input features
- `"target"` — `pandas.Series` of target values
- `"group"` — `pandas.Series` of entity labels (used for entity-boundary sequence construction)
- `"time"` — `pandas.Series` of UTC timestamps
- `"scaling_factor"` — `pandas.Series` of per-row scaling factors

The `predict()` function supports two calling modes that mirror the XGBoost interface:

- **Single-dataset mode**: if `prepared_dataset` contains a `"features"` key at the top level, `predict()` returns a bare `pandas.Series` of predictions.
- **Multi-split mode**: if `prepared_dataset` contains `"training"`, `"validation"`, and/or `"testing"` keys, `predict()` returns a `dict[str, pandas.Series]` mapping each split name to its predictions.

### Assumptions and Limitations

- **Zero-padding for the initial lookback**: For the first `n_timesteps - 1` rows of each entity, the lookback window cannot be filled from historical data. These positions are zero-padded, which means the model's effective context is shorter at the start of each entity's time series. This is standard practice for sequence models applied to short or boundary-constrained series.
- **Categorical features treated as numeric**: The LSTM receives all features as standardized `float32` tensors. Categorical features (hour of day, month, weekend flag, temperature rank) are integer-encoded numbers, the same encoding used by XGBoost, standardized like the other features. The LSTM does not apply embedding layers to these features.
- **Optional algorithm**: LSTM is not the default algorithm. The default is XGBoost, selected by setting `algorithm: XGBoost` in `ml_config.yaml`. To switch to LSTM, set `algorithm: LSTM`.

### Benchmark Results

To compare the two algorithms under identical conditions, both were trained and validated on a benchmark dataset covering three countries (Denmark, Austria, Portugal) with electricity demand, temperature, population, and GDP data for 2021-2023. The most recent year of each entity was reserved as the testing set (`reserve_testing_set: true`), consistent with the temporal splitting described above.

**Per-entity testing set MAPE:**

| Entity | XGBoost | LSTM |
|---|---|---|
| DNK | 0.0931 | 0.1555 |
| AUT | 0.1085 | 0.1754 |
| PRT | 0.0869 | 0.1634 |

**Overall testing set MAPE:**

| Metric | XGBoost | LSTM |
|---|---|---|
| Mean | 0.0962 | 0.1648 |
| Median | 0.0931 | 0.1634 |

On this benchmark, XGBoost outperformed LSTM on every entity. These results were measured before the LSTM standardized its features and broke its sequences at the gaps between hours, both of which change its training, so they do not tell how the two algorithms compare now, nor why: the comparison must be run again, on holdouts recorded in the manifests of the models.

**XGBoost remains the default algorithm** for DemandCast. LSTM is an optional alternative.

**Benchmark configuration:**

- Entities: DNK, AUT, PRT
- Years: 2021-2023
- Test set: most recent year per entity (`reserve_testing_set: true`)
- LSTM: default hyperparameters (`n_timesteps=24`, `n_units=32`, `n_layers=1`, `epochs=5`)
- XGBoost: default hyperparameters (see [XGBoost Configuration](#xgboost-configuration))

**Reproducing the benchmark:** `demandcast/benchmark/` has the configuration files of the retrieval and assembly of the benchmark data, and a script that runs them one after the other and stops at the first step that fails:

```bash
cd demandcast
uv run python -m benchmark.run                 # all six steps
uv run python -m benchmark.run --from-step 5   # resume from the temperature
```

The assembled data is saved in `data/assembled/`; train and validate each model on it as described below, with `reserve_testing_set: true`.

## Training and Validation

The machine learning pipeline in DemandCast is managed through several Python scripts located in the `demandcast/` directory. Each script utilizes a configuration file to specify parameters such as data paths, model settings, and evaluation metrics. All scripts accept only the path to a configuration file:

```bash
cd demandcast
uv run script_name.py [--config path/to/config.yaml]
```

If no config file is specified, the script uses the default `demandcast/config/{script_name}_config.yaml` file. All parameters are configured in the YAML configuration files.

### Data Assembly

The script `demandcast/assemble.py` combines retrieved data from multiple sources into a unified dataset ready for model training or forecasting.

**Usage:**
```bash
cd demandcast
uv run assemble.py [--config path/to/config.yaml]
```

**Configuration variables** (`assemble_config.yaml`):

```yaml
target_use: training               # Target use: 'training' or 'forecasting'

file:                              # Path to YAML file with list of country codes

start_year:                        # Start year for data range
end_year:                          # End year for data range

# Scenario selections for different data types
scenario_for_annual_electricity_demand_per_capita:
scenario_for_gdp_ppp_per_capita:
scenario_for_population:
scenario_for_temperature:

climate_model_for_temperature:     # Climate model for temperature data
```

The script outputs assembled data files to `data/assembled/` with filenames indicating the purpose and timestamp: `assembled_data_for_{target_use}_YYYYMMDD_HHMMSS.parquet`.

Each row is an hour of a country or subdivision, at its end in UTC (`Time (UTC)`). Its electricity demand is the mean demand of the hour, and its temperature the mean temperature of the hour, from the instantaneous temperatures at its start and at its end. Its local hour of the day, weekend indicator, month and year are those of the start of the hour in local time, so that the hour from 23:00 to midnight on a Friday is on a Friday, and the hour before midnight on January 1 belongs to the year before, with the annual values of that year. The datasets are merged on the hours and the countries or subdivisions, keeping only the hours that all of them have.

The fraction of the annual total divides the demand of each hour by the annual demand, estimated from the hours of the year with data, which must then represent the whole year: a year without its winter or its summer would have the wrong annual demand. The training data therefore keeps only the years with at least 90% of their hours and half of the hours of each month, and `assembled_data_for_training_YYYYMMDD_HHMMSS_coverage.csv` lists the hours of each year of each country or subdivision, their share of the year, the lowest share of a month and whether the year is kept.

### Model Training

The script `demandcast/train.py` trains a machine learning model on assembled historical data.

**Usage:**
```bash
cd demandcast
uv run train.py [--config path/to/config.yaml]
```

**Configuration variables** (`train_config.yaml`):

```yaml
reserve_testing_set: true          # Reserve data for testing
use_validation_set: false          # Use validation set during training

data_path:                         # Path to assembled data file
```

The trained model is saved to `data/models/{algorithm_name}/{algorithm_name}_model_YYYYMMDD_HHMMSS.json` (`.pt` for the LSTM), with the name of the algorithm in lower case, and its manifest to `{algorithm_name}_model_YYYYMMDD_HHMMSS.manifest.json`. Without `data_path`, the latest data assembled for training is used. Model configuration is specified in `ml_config.yaml` and `xgboost_config.yaml`.

### Manifests

Each assembled dataset, trained model and result has a manifest next to it, a JSON file with the same name and the extension `.manifest.json` (`demandcast/utils/manifest.py`), which tells what it is and how it was made: its kind, the checksum of each of its files (both the CSV and the Parquet file of a dataset or of results), the commit of the code and the checksum of `uv.lock`, and:

- for an assembled dataset, its purpose (training or forecasting), the settings of `assemble.py`, its columns and types, its countries and subdivisions, and for each input, such as the combined electricity demand or the temperature, the number of files read and a checksum of their paths and contents;
- for a model, its dataset and its checksum, the settings of `ml_config.yaml` and of the model, its features in their order with their types, its target and the transformation of the target, the statistics of its standardization, if any, and the countries and subdivisions and local years of each of its sets;
- for a result, the name and checksum of its model and of its dataset, and the metric of its errors (the MAPE, lower is better, of the load relative to the annual mean) or, for forecasts, their units and the scaling of each year to its annual demand; for a cross-validation, also the settings of `ml_config.yaml` and of the model, the holdout and the entities held out by each fold.

The paths of the data in the manifests are relative to the data folder, so they stay valid in a copy of it. What is checked:

| Step | Checks |
|---|---|
| `validate.py` | The model file is the one of its manifest (its checksum). The dataset is that of the training, by default, and stops if it is missing rather than using another one; the dataset, the target and its transformation, the preparation of the data and the sets are those of the training. |
| `forecast.py` | The model file is the one of its manifest. The target and its transformation and the preparation of the data are those of the training: the features in their order, the categorical features and the scaling variables, which convert the predictions to MW, in any order. |
| `publish.py` | Each file with a manifest is the one of its manifest, each manifest is uploaded once, and results are those of the model of the release; otherwise nothing is uploaded. |

A model trained before the manifests is used without these checks, which the log reports.

### Model Validation

The script `demandcast/validate.py` performs a validation of the trained model on the reserved test set and computes performance metrics (e.g., MAPE). The errors of the validation and of the cross-validation are computed by `demandcast/ml_models/evaluation.py`, on the target of the models, the load relative to the annual mean: they measure the error of the hourly profile, not that of the annual demand. The metrics are the mean absolute percentage error (MAPE), as a fraction, and the weighted absolute percentage error (WAPE), the sum of the absolute errors over the sum of the actual values, which a few hours close to zero cannot dominate, unlike the MAPE: in a first validation, the net demand of North Macedonia at midday in 2025, down to 0.005 MW, gave it a MAPE of 16 and moved the mean MAPE of all the countries and subdivisions from 0.09 to 0.19. The validation gives two MAPEs for each set: that of the predictions as the model gives them, and that of the complete years scaled to their annual totals, as `forecast.py` delivers them (see [from the predictions to MW](#from-the-predictions-to-mw)), which is missing for an entity without a complete year. A constant prediction of 1.2 times a target of 1 has a MAPE of 20%, but none once scaled.

**Usage:**
```bash
cd demandcast
uv run validate.py [--config path/to/config.yaml]
```

**Configuration variables** (`validate_config.yaml`):

```yaml
used_validation_set: false         # Whether validation set was used in training

model_path:                        # Path to trained model file
data_path:                         # Path to assembled data file (default: that of the training of the model)
```

Results are saved to `data/results/validation/with_{trained_model_name}/using_{data_file_name}/all_YYYYMMDD_HHMMSS.parquet` (and `.csv`), with the MAPE of each country and subdivision in each set.

### Cross-Validation

The script `demandcast/cross_validate.py` performs Leave-One-Group-Out cross-validation to test model generalization across regions.

**Usage:**
```bash
cd demandcast
uv run cross_validate.py [--config path/to/config.yaml]
```

**Configuration variables** (`cross_validate_config.yaml`):

```yaml
n_jobs: 1                          # Number of parallel jobs

data_path:                         # Path to assembled data file

holdout: entity                    # Hold out each entity, or each country with its subdivisions ("country")
```

Cross-validation results are saved to `data/results/cross_validation/with_{algorithm}/using_{data_file_name}/all_YYYYMMDD_HHMMSS.parquet` (and `.csv`), with the MAPE of each held-out country and subdivision on the training rows and on its own rows, and the holdout. The models are trained and scored on all the fields of their rows, such as their times, as in a validation.

### Forecasting

The script `demandcast/forecast.py` generates electricity demand forecasts using a trained model.

**Usage:**
```bash
cd demandcast
uv run forecast.py [--config path/to/config.yaml]
```

**Configuration variables** (`forecast_config.yaml`):

```yaml
model_path:                        # Path to trained model file

data_path:                         # Path to assembled data file
```

Forecasts are saved to `data/results/forecasts/with_{trained_model_name}/using_{data_file_name}/all_YYYYMMDD_HHMMSS.parquet` (and `.csv`), with the predicted electricity demand for the forecast period, in MW, whose complete years sum to their annual demand (see [from the predictions to MW](#from-the-predictions-to-mw)).

## Model Configuration

The ML pipeline is configured through YAML files in `demandcast/config/`. The two key configuration files define model behavior and hyperparameters.

### ML Configuration (`ml_config.yaml`)

This file defines the core model structure, features, and training parameters:

```yaml
algorithm: XGBoost                 # ML algorithm to use

group: "Entity code"               # Variable for grouping data (LOGO CV)

features:                          # Features for training
  - "Local hour of the day"
  - "Local weekend indicator"
  - "Local holiday indicator"
  - "Local month of the year"
  - "Temperature - Top 1 (K)"
  - "Temperature - Top 3 (K)"
  - "Monthly average temperature - Top 1 (K)"
  - "Monthly average temperature rank - Top 1"
  - "Annual average temperature - Top 1 (K)"
  - "5 percentile temperature - Top 1 (K)"
  - "95 percentile temperature - Top 1 (K)"
  - "GDP PPP per capita (2021 international $)"
  - "Annual electricity demand per capita (kWh)"

target: "Load (fraction of annual total)"  # Target variable

splitter: "Local year"             # Variable for temporal splitting

time: "Time (UTC)"                 # Time variable

categorical_features:              # Categorical feature list
  - "Local hour of the day"
  - "Local weekend indicator"
  - "Local holiday indicator"
  - "Local month of the year"
  - "Monthly average temperature rank - Top 1"

scaling_variables:                 # Variables for scaling predictions
  - "Annual electricity demand per capita (kWh)"
  - "Population"
```

### XGBoost Configuration (`xgboost_config.yaml`)

This file specifies XGBoost-specific hyperparameters:

```yaml
random_state: 42                   # Random seed for reproducibility
enable_categorical: true           # Enable native categorical feature support
evaluation_metric: "mape"          # Evaluation metric (Mean Absolute Percentage Error)
```

For additional configuration options and detailed parameter descriptions, refer to the YAML files in `demandcast/config/`.
