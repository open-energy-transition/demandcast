# Analyzing and plotting data

The script `plot.py` generates various plots to visualize the historical electricity demand data and model results. It reads its configuration from `config/plot_config.yaml` by default. You can run the script using:

```bash
uv run plot.py
```

Set the `figure` field in `config/plot_config.yaml` to specify the type of plot to generate. Available options include:

- `map_of_available_entities` to visualize the countries and subdivisions for which electricity demand data has been retrieved.
- `data_availability` to visualize the availability of electricity demand data clustered by GDP, PPP per capita and annual electricity demand per capita.
- `ml_results` to visualize the results of machine learning models and their error metrics.

## Machine learning model results

The folders `ml_models/validation/` and `ml_models/cross_validation/` contain CSV files with the Mean Absolute Percentage Error (MAPE) results of different versions of the machine learning models used for electricity demand forecasting. The MAPE is the difference between the predicted and actual electricity demand, expressed as a percentage of the actual demand. Each file corresponds to a specific model and entity group.

To plot the results, update `config/plot_config.yaml` with the desired `figure` and `version` values, then run:

```bash
uv run plot.py
```

Examples of relevant configuration values:

- `figure: ml_results`
- `version: <model_version>`
- `compare_with_version: <other_model_version>` (optional)
- `by_group: true` (optional)

To use a different config file, pass it with `-c`:

```bash
uv run plot.py -c /path/to/plot_config.yaml
```

The resulting plots will be saved in the `demandcast/figures` directory.
