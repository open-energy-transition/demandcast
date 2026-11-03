# Current state

This page shows, at a high level, the electricity demand data that DemandCast retrieves and the errors of the forecasts of its models. Its figures and numbers are drawn by `plot.py` with `figure: status` (see [Analyzing and plotting data](plot.md)).

## Data

--8<-- "status/numbers.md"

The map shows the countries and subdivisions for which retrieval modules of electricity demand data are available, with the years of their data.

![Countries and subdivisions for which retrieval modules of electricity demand data are available](status/available_entities_light_mode.png#only-light)
![Countries and subdivisions for which retrieval modules of electricity demand data are available](status/available_entities_dark_mode.png#only-dark)

The figure below shows the years of data by GDP PPP per capita and by annual electricity demand per capita, by continent, and how they changed in each country between its first and last year of data. It shows which kinds of countries the training data covers, and therefore where the models extrapolate when they forecast the demand of the countries without data.

![Years of hourly and sub-hourly electricity demand data by GDP PPP and annual electricity demand per capita](status/data_availability_by_gpd_ppp_and_electricity_demand.png)

The [data retrieval](retrieval.md) page describes the data sources, and how their data is cleaned and combined.

## Forecast errors

The models forecast the hourly electricity demand of each year of a country or subdivision. Their error is the weighted absolute percentage error (WAPE): the sum of the absolute differences between the forecast and the actual hourly demand, divided by the sum of the actual demand. Lower is better. The models are scored in two ways: a validation, on the most recent year of the countries and subdivisions with data, and a cross-validation, on countries and subdivisions whose data the model never saw.

### Validation

The validation trains the model on all the years of data but the most recent one of each country and subdivision, and scores it on that year. The countries and subdivisions with a single year of data are only scored, so the model never saw them in training. It tells how well the model forecasts a new year of the places it learned from.

--8<-- "status/ml_validation.md"

Each bar is the error of a country or subdivision, hatched with lines if the model never saw it in training, and with dots if its mean demand is below 300 MW.

![WAPE of the validation of each country and subdivision](status/wape_validation.png)

The boxes show how the errors spread: for all the countries and subdivisions, for those that the model saw in training or not, and by mean demand. The red line is the median of the group, and the green diamond the error of the group as a whole, in which the largest systems weigh the most.

![Distribution of the WAPE of the validation](status/wape_validation_distribution.png)

The figure below compares the actual hourly demand with the forecast, over a full year, for the country or subdivision with the lowest error and for that with the highest. The forecast has the annual demand of the actual one, so the two differ by the error of the hourly profile, which the WAPE measures.

![Actual and forecast hourly demand of the best and the worst country or subdivision of the validation](status/wape_validation_best_and_worst.png)

### Cross-validation

The cross-validation trains a model without part of the data in turn, and scores it on the part left out, which the model never saw, as when the models forecast the countries and subdivisions without data.

--8<-- "status/ml_cross_validation.md"

The figures show the error of each country and subdivision, their distribution, and the actual and forecast hourly demand of those with the lowest and the highest error, as for the validation.

![WAPE of the cross-validation of each country and subdivision](status/wape_cross_validation.png)

![Distribution of the WAPE of the cross-validation](status/wape_cross_validation_distribution.png)

![Actual and forecast hourly demand of the best and the worst country or subdivision of the cross-validation](status/wape_cross_validation_best_and_worst.png)

The [machine learning](ML.md) page describes the models and how they are validated.
