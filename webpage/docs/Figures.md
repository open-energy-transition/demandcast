# Analyzing and plotting data

The script `plot.py` generates various plots to visualize the historical electricity demand data and model results. You can run the script using:

```bash
uv run plot.py <type_of_plot>
```

The `<type_of_plot>` argument specifies the type of plot you want to generate. Available options include:

- `map_of_available_entities` to visualize the countries and subdivisions for which electricity demand data has been retrieved.
- `data_availability` to visualize the availability of electricity demand data clustered by GDP, PPP per capita and annual electricity demand per capita.
- `ml_results` to visualize the results of machine learning models and their error metrics.

## Maching learning model results

The folder `ETL/mapes` contains CSV files with the Mean Absolute Percentage Error (MAPE) results of different versions of the machine learning models used for electricity demand forecasting. The MAPE is the difference between the predicted and actual electricity demand, expressed as a percentage of the actual demand. Each file corresponds to a specific model and entity group.

To plot the results, run:

```bash
uv run plot.py ml_results --version <model_version> # To plot results for a specific model version
uv run plot.py ml_results --version <model_version> --compare_with_version <other_model_version> # To compare results between two model versions
uv run plot.py ml_results --version <model_version> --by_group # To plot results grouped by income level and continent
```

The resulting plots will be saved in the `ETL/figures` directory.