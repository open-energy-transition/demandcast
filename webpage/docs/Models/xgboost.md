# XGBoost

"XGBoost is an optimized distributed gradient boosting library designed to be highly efficient, flexible and portable.
It implements machine learning algorithms under the Gradient Boosting framework." ([XGBoost documentation](https://xgboost.readthedocs.io/en/stable/))

## Motivation

The core motivation for using XGBoost to generate hourly electricity demand forecasts is due to previous work in literature.
Our approach involves using socioeconomic and weather parameters passed to an XGBoost model to predict the hourly electricity demand.
For this purpose it is a fast model to train and perform inference,
therefore serves as a great option for a baseline that can be expanded on in future work.

## Features

The following features are used by the model.
See `serve.py` for more details:

```python
class PredictionInput(BaseModel):
    """Define input data for prediction."""

    is_weekend: int = Field(ge=0, le=1)
    hour: int = Field(ge=0, lt=24)
    month: int = Field(ge=1, le=12)
    month_temp_avg: float
    month_temp_rank: int = Field(ge=1, le=12)
    year_electricity_demand_per_capita: float
    year_gdp_ppp: float = Field(gt=0)
    year_temp_percentile_5: float
    year_temp_percentile_95: float
    year_temp_top3: float
```

<h3>Temporal</h3>

<h4>Hour of the day</h4>
`hour: int = Field(ge=0, lt=24)`

<h4>Month of the year</h4>
`month: int = Field(ge=1, le=12)`

<h4>Weekend indicator</h4>
`is_weekend: int = Field(ge=0, le=1)`

<h3>Electricity Demand</h3>

<h4>Yearly electricity demand per capita</h4>
`year_electricity_demand_per_capita: float`

<h3>Monetary</h3>

<h4>Yearly Gross Domestic Product Purchasing Power Parity</h4>
`year_gdp_ppp: float = Field(gt=0)`

<h3>Weather</h3>

The grid cells used for these features has a resolution of (0.25° x 0.25°) and is bounded by the respective country borders.

<h4>Average temperature for the month</h4>
`month_temp_avg: float`

Calculated based on the temperature in the most populous grid cell.

<h4>Temperature rank of the month</h4>
`month_temp_rank: int = Field(ge=1, le=12)`

Calculated based on the temperature in the most populous grid cell.

<h4>Yearly temperature percentiles</h4>
`year_temp_percentile_5: float`

`year_temp_percentile_95: float`

Calculated based on the temperature in the most populous grid cell.

<h4>Average temperature in most populous grid cell</h4>
`year_temp_top1: float`

<h4>Average temperature in most populous 3 grid cells</h4>
`year_temp_top3: float`

## Implementation

You can find all the relevant files in the `models/xgboost` folder.

### inference.py

Run inference for an XGBoost model that outputs electricity demand.

This module loads the input data, loads the pre-trained XGBoost model,
performs inference using the loaded model, and saves the results.

### serve.py

Serve an XGBoost model for electricity demand prediction using FastAPI.

This module provides a REST API service to serve predictions from
a pre-trained XGBoost model.

It includes endpoints for health checks, model information,
and making predictions based on passed features.

### XGBoost.ipynb

A jupyter notebook containing the code to train and run an XGBoost model based on toktarova(2019) data.
Includes visualizations and cross-validation.
