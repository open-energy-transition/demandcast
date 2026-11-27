# Plot figures

`plot.py` draws one figure at a time: the data availability, the map of the countries and subdivisions with data, the errors of the models, or the figures and numbers of the [Current state](../status.md) page.

## Run plot.py

1. Set `figure`, and the options it needs, in `config/plot_config.yaml`, or in another file passed with `--config` (or `-c`).
2. From the `demandcast/` folder, run:

    ```bash
    uv run plot.py
    uv run plot.py --config config/my_plot_config.yaml
    ```

3. Find the figures in `data/results/figures/` of the [data folder](../reference/data-folder.md), and the log in `data/logs/plotting_<time>.log`.

Figures are PNG files at 300 dpi. Each file gets its final name only once it is complete.

## Options

| Option | Default | What it does |
|---|---|---|
| `figure` | required | The figure: `data_availability`, `map_of_available_entities`, `ml_results` or `status`. |
| `version` | required for `ml_results` | The results to plot: a trained model, such as `xgboost_model_20261029_144400`, for a validation; an algorithm, such as `xgboost`, for a cross-validation; or a folder of MAPE files of an [earlier version](#results-of-earlier-versions). |
| `compare_with_version` | none | A second version, drawn next to `version`. Only for `ml_results`. |
| `by_group` | `false` | Draw the errors of the models trained on each income group and continent against those of the model trained on all data. Only for `ml_results`. |
| `results` | `validation` | Read the results of `validate.py` (`validation`) or of `cross_validate.py` (`cross_validation`). Used by `ml_results`. |
| `metric` | `WAPE` | The error to plot: `WAPE` or `MAPE`. Used by `ml_results`. |
| `validation_results` | the latest | The Parquet file of validation results to publish on the Current state page. Only for `status`. |
| `cross_validation_results` | the latest | The same for the cross-validation. Only for `status`. |

`plot.py` stops before drawing if:

- `ml_results` has no `version`;
- `by_group` and `compare_with_version` are both set;
- `version`, `compare_with_version` or `by_group` is set for another figure;
- `validation_results` or `cross_validation_results` is set for a figure other than `status`.

!!! note
    `results` and `metric` are ignored, not refused, by the other figures. `status` always plots the WAPE of both the validation and the cross-validation.

## Data availability

```yaml
figure: data_availability
```

This figure shows which kinds of countries the electricity demand data covers: where the models learn from many examples and where they extrapolate. It is saved as `data_availability_by_gdp_ppp_and_electricity_demand.png`.

| Panel | What it shows |
|---|---|
| Left bars | Years of data, stacked by continent, in four levels of [GDP PPP](../concepts/glossary.md#gdp-ppp) per capita (thousands of 2021 international dollars): below 10, 10–30, 30–60, above 60. |
| Middle bars | The same years, in four levels of annual electricity demand per capita (MWh): below 2, 2–5, 5–12, above 12. |
| Right scatter plot | One arrow per country, from its first to its last year of data, by GDP PPP per capita (x) and annual electricity demand per capita (y), both on log scales. Nigeria, Peru, Nepal, Canada, Norway and Luxembourg are labelled. |

How to read it:

- A year of data counts in the levels of its country in that year. A partly covered year counts as the fraction of its days with data.
- A subdivision takes the values per capita of its country. The bars count each country and subdivision separately.
- An arrow covers the years of the country's own data or of its subdivisions, among the years with both values per capita.
- Both bar charts share the same vertical scale.
- A year without a value per capita is not counted. The GDP PPP per capita stops at last year, so the current year never appears.

The values per capita are downloaded from Ember and the World Bank (electricity) and the World Bank and the IMF (GDP), so you need `EMBER_API_KEY` (see [Install](../getting-started/install.md)). The years of data come from the YAML files of the data sources, not from the data you retrieved.

## Map of available entities

```yaml
figure: map_of_available_entities
```

The map colours each place by the years of all the data that covers it: 0–4, 5–9, 10–19 and 20 or more years, from light to dark blue. A year is 365 days here.

- A country with national data is coloured over its whole area.
- Subdivisions are drawn over their country. Where they overlap, such as the periods of a grid whose area grew, the map splits them into pieces. Each piece counts the days of its country and of all the subdivisions covering it, without counting a day twice.
- Countries and standard subdivisions use the shapes of Natural Earth; [non-standard subdivisions](retrieve.md#non-standard-subdivisions) those of `shapes/subdivisions/`.

The years come from the YAML files of the data sources: the map shows what DemandCast can retrieve, not what you retrieved.

| File | Title | Background | Used by |
|---|---|---|---|
| `available_entities_for_aed.png` | Title and link of the Awesome Electricity Demand list | White | The Awesome Electricity Demand list |
| `available_entities.png` | DemandCast | White | The README (white reads well with both GitHub themes) |
| `available_entities_light_mode.png` | DemandCast, in black | Transparent | The Current state page, light theme |
| `available_entities_dark_mode.png` | DemandCast, in white | Transparent | The Current state page, dark theme |

The Current state page picks the light or dark image with the `#only-light` and `#only-dark` suffixes of MkDocs Material. The other figures have a white background.

## Errors of the models

```yaml
figure: ml_results
version: xgboost_model_20261029_144400
results: validation
metric: WAPE
```

This figure shows the testing error of each country or subdivision for a version of a model. [Train and validate](train-validate.md) and [Cross-validate](cross-validate.md) produce the results. The error is the [WAPE](../concepts/glossary.md#wape) (default; lower is better) or the [MAPE](../concepts/glossary.md#mape); [Metrics](../concepts/models.md#metrics) defines both.

| `results` | `version` | Results read |
|---|---|---|
| `validation` | A trained model, such as `xgboost_model_20261029_144400` | The latest `data/results/validation/with_<version>/using_<data>/all_<time>.parquet` |
| `cross_validation` | An algorithm, such as `xgboost` | The latest `data/results/cross_validation/with_<version>/using_<data>/all_<time>.parquet` |

"Latest" is the latest time in the file name. The results are checked against their [manifest](../concepts/glossary.md#manifest) (`<name>.manifest.json`, next to them), so results changed after they were saved are refused.

### Figures of one version

Without `compare_with_version` or `by_group`, a version gives:

| File | What it shows |
|---|---|
| `<metric>_<name>.png` | One bar per country or subdivision, from the lowest to the highest error. |
| `<metric>_<name>_distribution.png` | Box plots of the errors: all codes, by whether the model saw them in training, and by mean demand. |
| `wape_<name>_best_and_worst.png` | Actual and forecast hourly demand of the codes with the lowest and highest WAPE. Only with `metric: WAPE` and results with predictions, which `validate.py` and `cross_validate.py` always save. |

`<metric>` is `wape` or `mape`. `<name>` is:

- `validation_<version>` for a validation, such as `wape_validation_xgboost_model_20261029_144400.png`;
- `cross_validation_<algorithm>_<holdout>_<time>` for a cross-validation, such as `wape_cross_validation_xgboost_country_20261029_161733.png`. The holdout (`entity` or `country`) comes from the manifest, the time from the file name.

The title says "Validation of XGBoost" or "Cross-validation of XGBoost". The figure widens with the number of codes, so each code stays readable.

**Bars.** A bar hatched with lines is a code the model never saw in training. A bar hatched with dots is a small code, with a mean demand below 300 MW. A cross-validation never sees the codes it scores, so its bars have no lines.

**Distribution.** Each box shows the errors of a group of codes, with the number of codes under its name. The red line is the median. With the WAPE, the green diamond is the WAPE of all the hours of the group in MW, so the largest systems weigh most. The groups are "All codes", "Seen in training" (Yes or No, validation only), and the mean demand of the scored hours: below 300 MW, 300 MW–5 GW, and 5 GW or more.

**Best and worst.** One row for the code with the lowest WAPE, one for the highest:

- The left panel shows the actual (black) and forecast (orange) demand over the local year with the most scored hours (the latest on a tie), with its WAPE in the title.
- The right panel shows the typical week: the complete week, Monday to Sunday, whose WAPE is closest to the median of the complete weeks of the year. It is shaded grey on the left.
- Times are local, at the start of each hour. Missing hours are gaps.

The forecast has the same annual demand as the actual one, so they differ only by the hourly profile, which the WAPE measures.

### Compare two versions

```yaml
figure: ml_results
version: xgboost_model_20261029_144400
compare_with_version: xgboost_model_20261101_090000
```

This draws `<metric>_<name>_vs_<other name>.png`. The left panel has a box plot per version (blue for `version`, orange for `compare_with_version`); the right panel has two bars per code, sorted by the error of `version`. The legend names each version by its `<name>`.

Both versions are read from the same `results` folder: two validations or two cross-validations, not one of each. Only the codes with an error in both are drawn; the log lists the others.

### Errors by group

```yaml
figure: ml_results
version: example1
by_group: true
metric: MAPE
```

For each code, this compares the error of the model trained on all data (blue) with that of a model trained only on its group (orange), with a box plot and bars. It draws:

- `<metric>_<name>_by_income.png`, for the lower-middle, upper-middle and high-income groups. The low-income group has no results and is left out.
- `<metric>_<name>_by_continent.png`, for Africa, Asia, Europe, Oceania, North America and South America.

The results of a group are named after it instead of `all`: `AF`, `AS`, `EU`, `NA`, `OC`, `SA`, `lower_middle_income`, `upper_middle_income` and `high_income`.

!!! warning
    `validate.py` and `cross_validate.py` save only results named `all`. Results by group exist only in the MAPE files of earlier versions, so `by_group` needs such a version and `metric: MAPE`.

### Results of earlier versions

Earlier versions saved CSV files in a folder named after the version, such as `data/results/validation/<version>/all.csv`, with the columns `entity_code` and `MAPE_test`. When this folder exists, `plot.py` reads it instead of the Parquet files. It has no WAPE and no manifest, so use `metric: MAPE`. Its figures are named `mape_<version>...png` and titled `Version <version>`. `demandcast/tests/figures/mape_examples/` has two examples.

## Current state page

```yaml
figure: status
```

The `status` figure refreshes the [Current state](../status.md) page and the README. Run it from a clone of the repository, then commit the files it changes. In order, it:

1. draws the map and the data availability figure;
2. counts the countries, subdivisions, data sources and years of data, from the YAML files of the data sources;
3. finds the validation and cross-validation results to publish, and draws the three WAPE figures of each;
4. writes the numbers into the README, between `<!-- status:start -->` and `<!-- status:end -->`;
5. copies the figures into `webpage/docs/status/` and writes the texts there.

If a step before 4 fails, the README and the page are left as they were.

### Files it updates

| File | What it holds |
|---|---|
| `README.md` (block between the markers) | The sentence of `numbers.md`. The README also shows `available_entities.png`. |
| `webpage/docs/status/numbers.md` | The date, the countries and subdivisions with data, the countries they cover, the data sources, and the years of data since the first year. |
| `webpage/docs/status/ml_model.md` | The algorithms of the models of the two evaluations. |
| `webpage/docs/status/ml_validation.md` | The median WAPE of the validation: all codes, codes seen in training, codes never seen. |
| `webpage/docs/status/ml_cross_validation.md` | The holdout, the number of held-out codes and their median WAPE. |
| `webpage/docs/status/available_entities*.png` | The white, light and dark maps. |
| `webpage/docs/status/data_availability_by_gdp_ppp_and_electricity_demand.png` | The data availability figure. |
| `webpage/docs/status/wape_validation.png`, `wape_validation_distribution.png`, `wape_validation_best_and_worst.png` | The validation figures, renamed without the version. |
| `webpage/docs/status/wape_cross_validation.png`, `wape_cross_validation_distribution.png`, `wape_cross_validation_best_and_worst.png` | The cross-validation figures, renamed without the version. |

The figures are also kept, with their full names, in `data/results/figures/`.

### The numbers

The numbers come from the YAML files of the data sources:

- Countries are the codes without `_`; subdivisions the codes with `_`.
- The countries covered have national data or data of some of their subdivisions.
- The years of data add up the days the data sources of each code cover (overlapping periods count once), divided by 365.25. A country and its subdivisions count separately. These are the periods of the sources, before cleaning and before the choice of complete years for training.
- The date is today's date on your computer.

`tests/figures/test_status.py` checks that the README block and `numbers.md` match the data sources, apart from the years of data, which grow every day. After you add a data source or change a YAML file, the test fails and its message gives the new sentence. Run `plot.py` with `figure: status`, or paste the sentence into both files.

### Which results it publishes

By default, the page publishes the latest validation and cross-validation, by the time in their file names, across all models and algorithms in `data/results/validation/` and `data/results/cross_validation/`. To publish others, give their files:

```yaml
figure: status
validation_results: data/results/validation/with_xgboost_model_20261029_144400/using_<data>/all_20261030_101500.parquet
cross_validation_results: data/results/cross_validation/with_xgboost/using_<data>/all_20261029_161733.parquet
```

The files must keep the layout `with_<version>/using_<data>/`, from which the version is read. Their manifest must record their summary and predictions, or `plot.py` stops with an error.

A case without results gets the text "The models have no validation yet." (or "no cross-validation yet"), and no figure.

The cross-validation text depends on its holdout. With `holdout: entity`, each country or subdivision is left out in turn: the median WAPE estimates the error for a code without data whose country may have data of other subdivisions. With `holdout: country`, each country is left out with its subdivisions: the median WAPE estimates the error for a country without data.
