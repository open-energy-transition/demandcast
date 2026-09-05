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

**Temporal Splitting**

Unlike typical machine learning where data is randomly split, temporal splitting is required for time-series forecasting. Random splitting would "leak" future information into training, making results unrealistically good. The dataset is split using the following logic:

- **Test set**: For each region, the most recent calendar year for which that region has data
- **Validation set**: For each region, the second-most-recent calendar year for which that region has data (optional)
- **Training set**: For each region, all remaining earlier years with data

Regions with fewer than three years of data contribute only to the splits that are possible given their available years.

This ensures the model is evaluated on future time periods it hasn't seen during training, which is critical for time-series forecasting.

**Leave-One-Group-Out (LOGO) Cross-Validation**

LOGO cross-validation tests model generalization across regions by training on all regions except one and evaluating on the held-out region. This process is repeated for each region, providing insight into how well the model can forecast electricity demand for new regions or countries without historical data.

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

## LSTM Algorithm

Long Short-Term Memory (LSTM) networks extend DemandCast's forecasting toolkit as an alternative to XGBoost, bringing a sequence-aware architecture that is well-suited to the hourly, temporally ordered structure of electricity demand data.

### Motivation

The motivation for including an LSTM model builds on peer-reviewed work that benchmarks deep sequence models against classical time-series and gradient boosting approaches for energy demand forecasting (e.g. [Ul Rehman and Iqbal, 2025](https://doi.org/10.1186/s42162-025-00587-5)). Research comparing LSTM, Seq2Seq, and Prophet on smart-meter data demonstrates that LSTM networks consistently outperform statistical baselines when capturing daily and weekly periodicities in disaggregated load profiles. Electricity demand is an inherently sequential signal: the load at any given hour is influenced by the hours immediately preceding it—morning warm-up, evening peak, overnight trough—and an architecture that learns these temporal dependencies directly from the input sequence is a natural complement to XGBoost. Where XGBoost sees each row as an independent observation and relies on engineered temporal features (hour-of-day, month, weekend flag) to encode context, the LSTM models that context implicitly through its recurrent hidden state. Together, the two algorithms offer a gradient-boosting baseline and a sequence-learning alternative that can be compared under identical evaluation protocols.

### Architecture

The LSTM implementation in DemandCast (`ml_models/lstm.py`) is built on PyTorch's `nn.LSTM` module paired with a single linear output layer. The network accepts input tensors of shape `(batch, n_timesteps, n_features)`, passes them through one or more stacked LSTM layers, and projects the final hidden state to a scalar prediction via `nn.Linear(n_units, 1)`. Dropout can be applied between stacked layers when `n_layers > 1`.

The `LSTMRegressor` class wraps this network in a scikit-learn-compatible estimator (`BaseEstimator`, `RegressorMixin`), giving it `fit()` and `predict()` methods that accept `pandas.DataFrame` and `pandas.Series` inputs. This interface allows the model to be passed directly to `sklearn.model_selection.cross_validate` and `LeaveOneGroupOut`, using the same evaluation infrastructure as XGBoost without modification.

Sequence construction is entity-aware. Each training or inference sample requires a lookback window of `n_timesteps` consecutive rows. Rather than drawing rows across entity (country or region) boundaries, the sequence builder identifies contiguous runs of the same entity label from the `"group"` column of the prepared dataset and zero-pads the leading edge of each new run. This ensures that predictions for the first hours of a new entity are not contaminated by data from the preceding entity in the DataFrame.

### LSTM Configuration

The LSTM-specific configuration is specified in `demandcast/config/lstm_config.yaml`. All parameters are required; the values listed below are the defaults.

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

The LSTM model requires `torch>=2.0.0`, which is included in `demandcast/pyproject.toml`. CPU-only installation is sufficient for the default configuration; no GPU is required. Training time on CPU with the default hyperparameters is comparable to XGBoost for typical dataset sizes.

### Input and Output Format

The LSTM model consumes the same `prepared_dataset` structure produced by `utils.ml.prepare_dataset` as XGBoost. Each split (`"training"`, `"validation"`, `"testing"`) is a dictionary containing:

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
- **Categorical features treated as numeric**: The LSTM receives all features as `float32` tensors. Categorical features (hour of day, month, weekend flag, temperature rank) are passed as integer-encoded numbers, the same encoding used by XGBoost. The LSTM does not apply embedding layers to these features.
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

On this benchmark, XGBoost outperforms LSTM by a wide margin on every entity. This should not be read as general evidence that sequence models are unsuited to load forecasting — the result is best explained by the small size of this particular benchmark. With only three entities and a few years of hourly data each, there are too few independent sequences for the LSTM to learn its recurrent weights across a `n_timesteps=24` lookback window without underfitting. The training-set MAPE supports this reading: it is close to the testing-set MAPE for LSTM (~0.166–0.167 training vs ~0.155–0.175 testing), rather than substantially lower as would be expected if the model were overfitting. XGBoost, by contrast, benefits from engineered temporal features (hour-of-day, month, weekend flag) that hand it context an LSTM must otherwise learn implicitly from data volume it does not yet have here.

**XGBoost remains the recommended default algorithm** for DemandCast, and this benchmark supports that recommendation for datasets of comparable size. LSTM should be treated as an optional alternative, best suited to future benchmarks with more entities and longer historical spans, where enough sequential data exists for the recurrent architecture to learn temporal dependencies without underfitting. Users experimenting with the LSTM algorithm on small datasets should expect it to underperform XGBoost until dataset scale increases substantially.

**Benchmark configuration:**

- Entities: DNK, AUT, PRT
- Years: 2021-2023
- Test set: most recent year per entity (`reserve_testing_set: true`)
- LSTM: default hyperparameters (`n_timesteps=24`, `n_units=32`, `n_layers=1`, `epochs=5`)
- XGBoost: default hyperparameters (see [XGBoost Configuration](#xgboost-configuration))

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

The trained model is saved to `ml_models/trained/{algorithm_name}_model_YYYYMMDD_HHMMSS.json`. Model configuration is specified in `ml_config.yaml` and `xgboost_config.yaml`.

### Model Validation

The script `demandcast/validate.py` performs a validation of the trained model on the reserved test set and computes performance metrics (e.g., MAPE).

**Usage:**
```bash
cd demandcast
uv run validate.py [--config path/to/config.yaml]
```

**Configuration variables** (`validate_config.yaml`):

```yaml
used_validation_set: false         # Whether validation set was used in training

model_path:                        # Path to trained model file
data_path:                         # Path to assembled data file
```

Results are saved to `ml_models/validation/with_{trained_model_name}/using_{data_file_name}/{case}_YYYYMMDD_HHMMSS.parquet`, containing metrics for each region in the test set.

### Cross-Validation

The script `demandcast/cross_validate.py` performs Leave-One-Group-Out cross-validation to test model generalization across regions.

**Usage:**
```bash
cd demandcast
uv run cross_validate.py [--config path/to/config.yaml]
```

**Configuration variables** (`cross_validate_config.yaml`):

```yaml
use_validation_set: false          # Use validation set during training

scoring_metric: neg_mean_absolute_percentage_error  # Metric for scoring

n_jobs: 1                          # Number of parallel jobs

data_path:                         # Path to assembled data file
```

Cross-validation results are saved to `ml_models/cross_validation/using_{model_name}/with_{data_file_name}/{case}_YYYYMMDD_HHMMSS.parquet`, containing metrics for each held-out region.

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

Forecasts are saved to `ml_models/forecasts/with_{trained_model_name}/using_{data_file_name}/{case}_YYYYMMDD_HHMMSS.parquet`, containing predicted electricity demand for the forecast period.

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
