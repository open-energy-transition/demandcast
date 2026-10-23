# Analyzing and plotting data

The script `plot.py` generates various plots to visualize the historical electricity demand data and model results. It reads its configuration from `config/plot_config.yaml` by default. You can run the script using:

```bash
uv run plot.py
```

Set the `figure` field in `config/plot_config.yaml` to specify the type of plot to generate. Available options include:

- `map_of_available_entities` to visualize the countries and subdivisions for which electricity demand data has been retrieved.
- `data_availability` to visualize the availability of electricity demand data clustered by GDP, PPP per capita and annual electricity demand per capita.
- `ml_results` to visualize the results of machine learning models and their error metrics.
- `status` to draw the figures and count the numbers of the [current state](status.md) page: the map and the data availability figures, and the countries, subdivisions, data sources and years of data. It copies them into `webpage/docs/status/` and writes the numbers into the README, between the markers `<!-- status:start -->` and `<!-- status:end -->`. Run it from a clone of the repository, and commit the files that it changes.

## Machine learning model results

The `ml_results` figure shows the Mean Absolute Percentage Error (MAPE) of a version of a machine learning model for each country and subdivision: the difference between the predicted and actual electricity demand, as a percentage of the actual demand. It can also compare two versions, or show the MAPE of the model trained on the data of each continent and income group against that of the model trained on all the data.

The MAPE files of a version are in its folder in `data/results/validation/<version>/`: `all.csv`, with the testing MAPE of each country and subdivision in the columns `entity_code` and `MAPE_test`, and, for the figure by group, a file with the same columns for each group (`AF.csv`, `AS.csv`, `EU.csv`, `NA.csv`, `OC.csv`, `SA.csv`, `lower_middle_income.csv`, `upper_middle_income.csv` and `high_income.csv`). `validate.py` does not write these files yet: copy the MAPEs of its results into them. `demandcast/tests/figures/mape_examples/` has two example versions.

Set the `figure` and `version` values in `config/plot_config.yaml`:

- `figure: ml_results`
- `version: <model_version>`
- `compare_with_version: <other_model_version>` (optional)
- `by_group: true` (optional, not together with `compare_with_version`)

Then run:

```bash
uv run plot.py
```

To use a different config file, pass it with `-c`:

```bash
uv run plot.py -c /path/to/plot_config.yaml
```

The figures are saved in `data/results/figures/`.
