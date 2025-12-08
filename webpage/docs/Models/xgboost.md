# XGBoost

"XGBoost is an optimized distributed gradient boosting library designed to be highly efficient, flexible and portable.
It implements machine learning algorithms under the Gradient Boosting framework." ([XGBoost documentation](https://xgboost.readthedocs.io/en/stable/))

## Motivation

The core motivation for using XGBoost to generate hourly electricity demand forecasts is due to previous work in literature.
Our approach involves using socioeconomic and weather parameters passed to an XGBoost model to predict the hourly electricity demand.
For this purpose it is a fast model to train and perform inference,
therefore serves as a great option for a baseline that can be expanded on in future work.

## Features

The following features are used by the model:

### Demand

- **Annual electricity demand (TWh)** (`year_electricity_demand`): Annual electricity demand in TWh
- **Annual electricity demand per capita (MWh)** (`year_electricity_demand_per_capita_mwh`): Annual electricity demand per capita in MWh

### Economic

- **Gross Domestic Product** (`year_gdp`): Annual Gross Domestic Product

### Temporal

- **Hour of the day** (`local_hour`): Integer value from 0 to 23
- **Month of the year** (`local_month`): Integer value from 1 to 12
- **Weekend indicator** (`is_weekend`): Binary value (0 or 1)

### Weather

The grid cells used for these features have a resolution of (0.25° x 0.25°) and are bounded by the respective country borders.

- **Average temperature in most populous grid cell** (`year_temp_top1`): Annual average temperature
- **Average temperature in most populous 3 grid cells** (`year_temp_top3`): Annual average temperature
- **Average temperature for the month** (`monthly_temp_avg_top1`): Monthly average temperature in the most populous grid cell
- **Temperature rank of the month** (`monthly_temp_avg_rank_top1`): Rank from 1 to 12 based on monthly temperature
- **Average yearly temperature** (`year_temp_avg_top1`): Annual average temperature in the most populous grid cell
- **Yearly temperature percentiles**:
  - `year_temp_percentile_5`: 5th percentile of yearly temperatures
  - `year_temp_percentile_95`: 95th percentile of yearly temperatures

## Command-Line Interface

The XGBoost model provides a comprehensive CLI for training, evaluation, and inference. All scripts are located in the `models/xgboost` folder.

### Key Concepts

#### What is Load Percentage?
**`load_mw_percentage`** is the target variable we're predicting. It represents the normalized hourly electricity consumption, which we calculate as follows.
Take each hour's electricity demand (in MW) and divides it by the total yearly electricity demand for that region.
Resulting in a fraction representing the percentage of the year's electricity that was consumed in this hour.
For example, 0.00015 means this hour consumed 0.015% of the year's total electricity

This normalization allows the model to learn patterns across regions of different sizes—a small country and a large country both have values in a comparable range.

#### Why Temporal Splitting?
Unlike typical machine learning where you randomly split data, **temporal splitting** is required due to the nature of time-series forecasting.
Random splitting would "leak" future information into training, making results unrealistically good.

In our case we split the dataset using the following logic:

- **Test set**: Last available year for each region
- **Validation set**: Second-to-last year for each region
- **Training set**: All remaining years

This ensures the model is evaluated on future time periods it hasn't seen during training, which is critical for time-series forecasting.

#### What is Cross-Validation?
**Leave-One-Group-Out (LOGO) cross-validation** tests model generalization across regions.

This tells us how well the model predicts regions it has not seen while training. A vital validation step that informs us how well the model can forecast data for new regions or countries without historical data.

#### Categorical vs Continuous Features
- **Continuous features**: Numbers with meaningful distance (temperature: 20°C is halfway between 10°C and 30°C)
- **Categorical features**: Numbers used as labels (month: February isn't "twice" January, it's just a different category)

XGBoost handles these differently internally. In our config, `hour`, `month`, `weekend`, and `month_temp_rank` are marked categorical because their numeric values are just labels, not measurements.

### Installation

```bash
cd models/xgboost
uv sync  
```

### Quick Start

**Note**: Replace `YYYY-MM-DD-HHMM` with actual timestamps from your files. Each command outputs the exact path to use in the next step.

##### 1. Preprocess raw data
```bash
uv run preprocess.py --data-dir ./data
```
Expected output: "Preprocessing complete! Output: ./data/processed/YYYY-MM-DD-HHMM_processed_dataset.parquet"

Typical runtime: 5-30 minutes depending on data size

##### 2. Train model
```bash
uv run train.py --data ./data/processed/YYYY-MM-DD-HHMM_processed_dataset.parquet
```
Expected output: "Train MAPE: 0.12, Val MAPE: 0.14, Test MAPE: 0.15"

Typical runtime: 2-10 minutes depending on data size

##### 3. Evaluate model (optional - training already evaluates)
```bash
uv run evaluate.py --model ./models/trained/YYYY-MM-DD-HHMM_xgboost_model.bin \
                   --data ./data/processed/YYYY-MM-DD-HHMM_processed_dataset.parquet
```
Useful for re-evaluating a saved model on different data splits

##### 4. Cross-validate (optional - more rigorous evaluation)
```bash
uv run cross_validate.py --data ./data/processed/YYYY-MM-DD-HHMM_processed_dataset.parquet
```
Expected output: "Mean test MAPE: 0.16" (typically slightly higher than single test)

Typical runtime: 10-60 minutes (trains N models where N = number of regions)

##### 5. Make predictions
```bash
uv run predict.py --model ./models/trained/YYYY-MM-DD-HHMM_xgboost_model.bin \
                  --input ./data/processed/YYYY-MM-DD-HHMM_processed_dataset.parquet
```
Use this for new data or generating forecasts for all regions

### CLI Commands

***
#### preprocess.py

This script transforms raw data files into a single, clean dataset ready for model training.

**Usage:**
```bash
uv run preprocess.py [--data-dir PATH] [--output PATH] [--config PATH]
```

**Options:**

- `--data-dir`: Input directory containing raw data folders (default: `./data`)
- `--output`: Output file path (default: `./data/processed/{timestamp}_processed_dataset.parquet`)
- `--config`: Path to config file (default: `./config/default_config.yaml`)

***
#### train.py

Trains a gradient boosting model to predict hourly electricity demand based on weather, economic, and temporal features.

**Usage:**
```bash
uv run train.py [--data PATH] [--output-dir PATH] [--config PATH] [--experiment-name TEXT]
```

**Options:**

- `--data`: Path to preprocessed data file (default: latest in `./data/processed/`)
- `--output-dir`: Output directory for trained model (default: `./models/trained`)
- `--config`: Path to config file (default: `./config/default_config.yaml`)
- `--experiment-name`: Optional experiment name for tracking

***
#### evaluate.py

Re-evaluates a trained model on the data splits.
Useful when you want to check a model's performance without retraining, or when comparing multiple saved models.

**Usage:**
```bash
uv run evaluate.py [--model PATH] [--data PATH] [--output-dir PATH] [--splits TEXT] [--config PATH]
```

**Options:**

- `--model`: Path to trained model file (default: latest in `./models/trained/`)
- `--data`: Path to preprocessed data file (required)
- `--output-dir`: Output directory for metrics (default: `./results/evaluation`)
- `--splits`: Comma-separated list of splits to evaluate (default: `train,val,test`)
- `--config`: Path to config file (default: `./config/default_config.yaml`)

***
#### cross_validate.py

Runs Leave-One-Group-Out cross-validation.
Tests how well the model generalizes to completely new regions (countries/areas it has never seen). More rigorous than simple train/val/test split.

**Usage:**
```bash
uv run cross_validate.py [--data PATH] [--config PATH] [--output-dir PATH]
```

**Options:**

- `--data`: Path to preprocessed data file (required)
- `--config`: Path to config file (default: `./config/default_config.yaml`)
- `--output-dir`: Output directory for CV results (default: `./results/cv`)

***
#### predict.py

Uses a trained model to generate electricity demand predictions for new data.
The output file contains both the input features and the predictions.

**Usage:**
```bash
uv run predict.py --model PATH --input PATH [--output PATH]
```

**Options:**

- `--model`: Path to trained model file (required)
- `--input`: Path to input features file (parquet or CSV) (required)
- `--output`: Output file path (default: `./predictions/{timestamp}_predictions.parquet`)

***

### Configuration

The CLI uses a YAML configuration file at `config/default_config.yaml`. This file controls preprocessing, training, and evaluation behavior. You can customize the model by editing this file or creating your own config with `--config your_config.yaml`.

#### Configuration Parameters

The configuration is organized into five sections:

**1. Preprocessing Section**

```yaml
preprocessing:
  include_annual_demand: true     # Include yearly electricity totals in the dataset
  include_gdp: true               # Include GDP data (economic indicator)

  features:                       # List of 10 input features the model uses
    - local_hour                  # Hour of day (0-23)
    - is_weekend                  # Weekend indicator (0 or 1)
    - local_month                 # Month of year (1-12)
    - year_temp_top1              # Annual avg temp in most populous grid cell
    - year_temp_top3              # Annual avg temp in top 3 grid cells
    - monthly_temp_avg_top1       # Monthly avg temp in most populous grid cell
    - monthly_temp_avg_rank_top1  # Temperature rank of the month (1-12)
    - year_temp_avg_top1          # Yearly avg temp in most populous grid cell
    - year_temp_percentile_5      # 5th percentile of yearly temperatures
    - year_temp_percentile_95     # 95th percentile of yearly temperatures

  target: load_mw_percentage      # What we're predicting (normalized hourly demand)

  categorical_features:           # Features treated as categories
    - local_hour                  
    - is_weekend                  
    - local_month
    - monthly_temp_avg_rank_top1 
```

**2. Training Section**

```yaml
training:
  random_state: 42                # Random seed for reproducibility
  enable_categorical: true        # Use XGBoost's native categorical feature handling
  eval_metric: "mape"             # Metric to optimize during training
```

**3. Cross-Validation Section**

```yaml
cross_validation:
  cv_type: "leave_one_group_out"          # Hold out entire regions for testing
  n_jobs: 1                               # Number of parallel processes (1 = sequential)
  scoring:
    - neg_mean_absolute_percentage_error  # sklearn scoring metric
```

**4. Evaluation Section**

```yaml
evaluation:
  metrics:
    - mape                      # Calculate Mean Absolute Percentage Error
  splits:
    - train                     # Evaluate on training data
    - val                       # Evaluate on validation data
    - test                      # Evaluate on test data
```

**5. Output Section**

```yaml
output:
  timestamp_format: "%Y-%m-%d-%H%M"  # Format for timestamped filenames
  save_formats:
    - parquet                        # Save metrics as Parquet (efficient)
    - csv                            # Save metrics as CSV (human-readable)
```

### Helper Modules

The CLI is built on reusable helper modules located in `utils-xgb/`:

- **`data_loader.py`**: Functions to load electricity, temperature, and GDP data
- **`feature_engineering.py`**: Merge datasets, clean data, calculate features
- **`model_utils.py`**: Model training, evaluation, and cross-validation utilities
- **`utils.py`**: Config loading, I/O operations

## Jupyter Notebooks

Research notebooks are available for experimentation and alternative modeling approaches.

### XGBoost.ipynb

The original research notebook that explores the XGBoost model for electricity demand forecasting. Contains exploratory analysis and initial model development.

### model_per_continent.ipynb

Implements a continent-based modeling approach where separate XGBoost models are trained for each continent.

#### Continent Classification

- Uses `pycountry_convert` to map country codes to continent codes
- Splits the dataset by continent (AF, AS, EU, NA, OC, SA)

#### Data Splitting Functions

- `compute_train_val_test()`: Splits data into training, validation, and test sets
  - Test set: Last available year for each region
  - Validation set: Second-to-last year for each region
  - Training set: All remaining years

#### Data Preparation

- `prepare_data()`: Processes features and converts categorical variables
- Prepares features, target variable (`load_mw_percentage`), and grouping information

#### Model Training and Evaluation

- Trains separate XGBoost models for each continent
- Evaluates using Mean Absolute Percentage Error (MAPE)
- Saves models with continent-specific naming (e.g., `xgboost_model_EU.bin`)
- Generates MAPE metrics for train, validation, and test sets

#### Error Metric Calculation

- `calculate_test_error_metric()`: Computes MAPE per region
- Saves results to both parquet and CSV formats

### model_grouby_income.ipynb

Implements an income-based modeling approach using World Bank country classifications.

#### Income Classification

- Loads World Bank income classification data
- Maps countries to income groups:
  - High income
  - Upper middle income
  - Lower middle income
  - Low income
- Handles special cases

#### Data Splitting Functions

- Uses the same `compute_train_val_test()` approach as the continent model
- Splits by last year (test), second-to-last year (validation), and remaining years (training)

#### Data Preparation

- Same `prepare_data()` function as continent model
- Processes identical feature set with categorical encoding

#### Model Training and Evaluation

- Trains separate XGBoost models for each income group
- Uses MAPE as the evaluation metric
- Saves models with income-group-specific naming (e.g., `xgboost_model_high_income.bin`)
- Generates comprehensive error metrics for all data splits

#### Output Management

- Saves models to `./data/income/` directory
- Generates timestamped MAPE reports for each income group and data split
- Exports results in both parquet and CSV formats

## Model Variants

The project includes three modeling approaches:

1. **Single Global Model** (`XGBoost.ipynb`): One model trained on all available data
2. **Continent-Specific Models** (`model_per_continent.ipynb`): Separate models for each continent
3. **Income-Based Models** (`model_grouby_income.ipynb`): Separate models for each World Bank income classification

Each approach has trade-offs between generalization and region-specific accuracy.
