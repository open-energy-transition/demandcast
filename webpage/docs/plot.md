# Analyzing and plotting data

The script `plot.py` generates various plots to visualize the historical electricity demand data and model results. It reads its configuration from `config/plot_config.yaml` by default. You can run the script using:

```bash
uv run plot.py
```

Set the `figure` field in `config/plot_config.yaml` to specify the type of plot to generate. Available options include:

- `map_of_available_entities` to visualize the countries and subdivisions for which electricity demand data has been retrieved.
- `data_availability` to visualize the availability of electricity demand data clustered by GDP, PPP per capita and annual electricity demand per capita.
- `ml_results` to visualize the results of machine learning models and their error metrics.
- `status` to draw the figures and count the numbers of the [current state](status.md) page: the map and the data availability figures, the countries, subdivisions, data sources and years of data, and the figures and median WAPE of a validation and of a cross-validation of the models, in two sections: the latest of each, by the time in the names of their files, or those of the files given in `validation_results` and `cross_validation_results`, checked against their manifests, which must record their summary and predictions, with the cross-validation described by the holdout that its manifest records. It copies them into `webpage/docs/status/` and writes the numbers into the README, between the markers `<!-- status:start -->` and `<!-- status:end -->`. Run it from a clone of the repository, and commit the files that it changes.

## Machine learning model results

The `ml_results` figure shows the testing error of a version of a machine learning model for each country and subdivision: by default the Weighted Absolute Percentage Error (WAPE), the sum of the absolute differences between the predicted and actual electricity demand over the sum of the actual demand, or, with `metric: MAPE`, the Mean Absolute Percentage Error (MAPE), the mean of these differences as percentages of the actual demand. It can also compare two versions, or show the error of the model trained on the data of each continent and income group against that of the model trained on all the data.

A version has two figures, and a third if its results have their predictions. The first has a bar for the error of each country and subdivision, hatched with lines for the codes that the model never saw in training, and with dots for the small ones, whose mean load is below 300 MW. The second, `<metric>_<version description>_distribution.png`, shows the distribution of the errors: of all the codes and, if the results describe them (those of `validate.py` and `cross_validate.py`, see [reporting by group](ML.md#reporting-by-group)), by whether the model saw them in training and by demand size, the mean load of their scored hours (below 300 MW, from 300 MW to 5 GW, and from 5 GW). Each group has a box of the errors of its codes, with their number under its name, and, for the WAPE, a diamond for the pooled WAPE of the group, that of all the hours of its codes in MW (see [reporting by group](ML.md#reporting-by-group)). The third, `wape_<version description>_best_and_worst.png`, compares the actual and forecast hourly demand of the codes with the lowest and the highest WAPE, in local time, over the local year with the most scored hours, the latest of them, with the WAPE of that year, and, next to it, over its typical week, the complete week from Monday to Sunday whose WAPE is the closest to the median WAPE of the complete weeks of the year, shaded in the year; the missing hours are gaps in the lines.

A version is a trained model, such as `xgboost_model_20261029_144400`, whose latest results that `validate.py` saved are read, by the time in their names and checked against their manifest, in `data/results/validation/with_<version>/using_<data>/all_<time>.parquet`, or, with `results: cross_validation`, the algorithm of a cross-validation, such as `xgboost`, whose latest results that `cross_validate.py` saved are read. The title and the name of the file say whether the results are those of a validation or of a cross-validation, and the algorithm and version of the model, after the metric: `wape_validation_xgboost_model_20261029_144400.png` for the validation of the XGBoost model trained at that time, and `wape_cross_validation_xgboost_country_20261029_161733.png` for the cross-validation of XGBoost by country, run at that time. The figure is wide enough for the code of each country and subdivision under its bar. The figure by group reads the results of the models trained on the data of each group, named after the group (`AF`, `AS`, `EU`, `NA`, `OC`, `SA`, `lower_middle_income`, `upper_middle_income` and `high_income`) instead of `all`. The MAPE files of earlier versions, in a folder of the version, `data/results/validation/<version>/all.csv` with the columns `entity_code` and `MAPE_test`, are read from there; `demandcast/tests/figures/mape_examples/` has two of them. They have no WAPE, so they are plotted with `metric: MAPE`.

Set the `figure` and `version` values in `config/plot_config.yaml`:

- `figure: ml_results`
- `version: <model_version>`
- `results: validation` (default) or `cross_validation`
- `metric: WAPE` (default) or `MAPE`
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
