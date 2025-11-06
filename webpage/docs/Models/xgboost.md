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

## Jupyter Notebooks

You can find all the relevant files in the `models/xgboost` folder.

### XGBoost.ipynb

The main training notebook that implements the XGBoost model for electricity demand forecasting.

#### Data Ingestion

- Loads annual electricity demand data from parquet files
- Processes temperature data from multiple regions
- Loads electricity demand data

#### Data Processing

- Combines electricity demand, temperature, and GDP data
- Removes duplicates and NaN values
- Calculates load percentage for each hour relative to yearly load
- Renames columns for consistency

#### Data Splitting

- Splits data into training, validation, and test sets
- Test set: Last available year for each region
- Validation set: Second-to-last year for each region
- Training set: All remaining years

#### Model Training

- Trains XGBoost models on the processed dataset
- Includes visualizations and cross-validation
- Saves trained models for inference

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
