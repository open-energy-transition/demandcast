# Plot figures

`plot.py` draws one figure at a time: the data availability, the map of the countries and subdivisions with data, the errors of the models, or the figures and numbers of the [Current state](../status.md) page. Use it to look at the data you retrieved, to judge a trained model, or to refresh the Current state page.

## Run plot.py

1. Open `config/plot_config.yaml` and set `figure` (and the other options it needs, see [Options](#options)).
2. From the `demandcast/` folder, run:

    ```bash
    uv run plot.py
    ```

    To use another settings file, pass it with `--config` (or `-c`):

    ```bash
    uv run plot.py --config config/my_plot_config.yaml
    ```

3. Find the figures in `data/results/figures/`. The log of the run is in `data/logs/plotting_<time>.log`.

The `data/` folder is the [data folder](../reference/data-folder.md): `demandcast/data/`, or the folder that the environment variable `DEMANDCAST_DATA_FOLDER` names.

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `figure` | Yes | — | The figure to draw: `data_availability`, `map_of_available_entities`, `ml_results` or `status`. |
| `version` | For `ml_results` | none | The results to plot: a trained model, such as `xgboost_model_20261029_144400`, for a validation; the algorithm, such as `xgboost`, for a cross-validation; or the folder of the MAPE files of an earlier version (see [Results of earlier versions](#results-of-earlier-versions)). |
| `compare_with_version` | No | none | A second version, whose errors are drawn next to those of `version`. Only for `ml_results`. |
| `by_group` | No | `false` | Draw the errors of the models trained on the data of each income group and continent against those of the model trained on all the data. Only for `ml_results`. |
| `results` | No | `validation` | Which results to read: those of `validate.py` (`validation`) or of `cross_validate.py` (`cross_validation`). Only used by `ml_results`. |
| `metric` | No | `WAPE` | The error to plot: `WAPE` or `MAPE`. Only used by `ml_results`. |
| `validation_results` | No | the latest | The Parquet file of the validation results to publish on the Current state page. Only for `status`. |
| `cross_validation_results` | No | the latest | The Parquet file of the cross-validation results to publish on the Current state page. Only for `status`. |

`plot.py` stops before drawing anything if the options do not fit together:

- `ml_results` needs `version`.
- `by_group` and `compare_with_version` cannot be used together.
- `version`, `compare_with_version` and `by_group` are refused for the other figures.
- `validation_results` and `cross_validation_results` are refused for every figure but `status`.

!!! note
    `results` and `metric` are not refused for the other figures: they are ignored. The `status` figure always plots the WAPE of both the validation and the cross-validation.

## Data availability

```yaml
figure: data_availability
```

This figure shows which kinds of countries the electricity demand data covers. It tells you where the models learn from many examples and where they extrapolate. It is saved as `data_availability_by_gdp_ppp_and_electricity_demand.png`.

It has three panels:

| Panel | What it shows |
|---|---|
| Left bars | The years of data, stacked by continent, in four levels of GDP PPP per capita (in thousands of 2021 international dollars): below 10, 10–30, 30–60, above 60. |
| Middle bars | The same years of data, in four levels of annual electricity demand per capita (in MWh): below 2, 2–5, 5–12, above 12. |
| Right scatter plot | One arrow per country, from its first to its last year of data, placed by GDP PPP per capita (x) and annual electricity demand per capita (y), both on log scales. A few countries (Nigeria, Peru, Nepal, Canada, Norway, Luxembourg) are labelled. |

GDP PPP per capita is the gross domestic product per person at [purchasing power parity](../concepts/glossary.md#gdp-ppp): it lets you compare incomes across countries.

How to read it:

- A year of data counts in the level of the GDP PPP and of the electricity demand per capita of its country in that year. A year partly covered counts as the fraction of its days with data.
- A subdivision takes the values per capita of its country, because the subdivisions with data are large systems, often as large as a country. The bars count each country and each subdivision separately.
- An arrow covers the years of the country's own data or of the data of its subdivisions, among the years that have both values per capita.
- The two bar charts share the same vertical scale, so you can compare them.
- A year without a value per capita is not counted. The GDP PPP per capita stops at the year before the current one, so the current year never appears.

The data per capita comes from the network: the electricity demand per capita from Ember and the World Bank, and the GDP PPP per capita from the World Bank and the IMF. You need the `EMBER_API_KEY` in your `.env` file (see [Install](../getting-started/install.md)). The years of data come from the YAML files of the data sources, not from the data you retrieved.

## Map of available entities

```yaml
figure: map_of_available_entities
```

The map colours each place by the years of all the data that covers it. The colour classes are 0–4, 5–9, 10–19 and 20 or more years, from light to dark blue. A year is 365 days here.

How to read it:

- A country with national data is coloured over its whole area.
- The subdivisions are drawn over their country. Where several subdivisions overlap (for example, the periods of a grid whose area grew), the map splits them into pieces. Each piece counts the days of its country and of all the subdivisions that cover it, without counting a day twice.
- The countries and the standard subdivisions use the shapes of Natural Earth. The non-standard subdivisions, defined by the standard subdivisions that make them up, use the shapes of `shapes/subdivisions/` (see [Retrieve data](retrieve.md)).

The years come from the YAML files of the data sources, so the map shows what DemandCast can retrieve, not what you retrieved.

The map is saved four times:

| File | Title | Background | Used by |
|---|---|---|---|
| `available_entities_for_aed.png` | The title and link of the Awesome Electricity Demand list | White | The Awesome Electricity Demand list |
| `available_entities.png` | The title of DemandCast | White | The README, since white reads well with both GitHub themes |
| `available_entities_light_mode.png` | The title of DemandCast, in black | Transparent | The Current state page, light theme |
| `available_entities_dark_mode.png` | The title of DemandCast, in white | Transparent | The Current state page, dark theme |

The Current state page shows the light or dark image with the `#only-light` and `#only-dark` suffixes of MkDocs Material, which follow the theme that the reader picks. The other figures have a single image on a white background.

## Errors of the models

```yaml
figure: ml_results
version: xgboost_model_20261029_144400
results: validation
metric: WAPE
```

This figure shows the testing error of each country or subdivision of a version of a model. Read [Train and validate](train-validate.md) and [Cross-validate](cross-validate.md) to produce the results it reads.

### Errors and versions

The two errors are:

- [WAPE](../concepts/glossary.md#wape) (weighted absolute percentage error): the sum of the absolute differences between the forecast and the actual hourly demand, divided by the sum of the actual demand. Lower is better. This is the default.
- [MAPE](../concepts/glossary.md#mape) (mean absolute percentage error): the mean of these differences, each as a percentage of the actual demand.

A version tells `plot.py` which results to read:

| `results` | `version` | Results read |
|---|---|---|
| `validation` | A trained model, such as `xgboost_model_20261029_144400` | The latest `data/results/validation/with_<version>/using_<data>/all_<time>.parquet` |
| `cross_validation` | An algorithm, such as `xgboost` | The latest `data/results/cross_validation/with_<version>/using_<data>/all_<time>.parquet` |

"Latest" means the latest time in the file name. The results are checked against their [manifest](../concepts/glossary.md#manifest) (`<name>.manifest.json`, next to them) before they are used, so results that changed after they were saved are refused.

### Figures of one version

Without `compare_with_version` or `by_group`, a version gives two figures, and a third for the WAPE when the results have their predictions. The results of `validate.py` and `cross_validate.py` always have them.

| File | What it shows |
|---|---|
| `<metric>_<name>.png` | One bar per country or subdivision, sorted from the lowest to the highest error. |
| `<metric>_<name>_distribution.png` | Box plots of the errors: of all the codes, by whether the model saw them in training, and by mean demand. |
| `wape_<name>_best_and_worst.png` | The actual and forecast hourly demand of the codes with the lowest and the highest WAPE. Only with `metric: WAPE`. |

`<metric>` is `wape` or `mape`. `<name>` tells the results apart:

- `validation_<version>` for a validation, such as `wape_validation_xgboost_model_20261029_144400.png`.
- `cross_validation_<algorithm>_<holdout>_<time>` for a cross-validation, such as `wape_cross_validation_xgboost_country_20261029_161733.png`. The holdout (`entity` or `country`) comes from the manifest of the results, and the time from their file name.

The title says "Validation of XGBoost" or "Cross-validation of XGBoost". The figure grows wider with the number of codes, so each code stays readable under its bar.

**Bars.** Each bar is the error of one country or subdivision. A bar hatched with lines is a code that the model never saw in training. A bar hatched with dots is a small code, whose mean demand is below 300 MW. The cross-validation results do not say which codes the model saw, since it never sees the codes it scores, so their bars have no lines.

**Distribution.** Each box shows the spread of the errors of a group of codes, with the number of codes under its name:

- The red line is the median of the group.
- With the WAPE, the green diamond is the WAPE of all the hours of the group in MW: the largest systems weigh the most.
- The groups are "All codes", then "Seen in training" (Yes or No, only for a validation), then the mean demand of the scored hours: below 300 MW, 300 MW–5 GW, and 5 GW or more.

**Best and worst.** The figure has one row for the code with the lowest WAPE and one for the code with the highest:

- The left panel shows the actual (black) and forecast (orange) demand over one local year. It is the local year with the most scored hours, the latest of them if there is a tie. The title gives the WAPE of that year.
- The right panel shows the typical week: the complete week, Monday to Sunday, whose WAPE is closest to the median WAPE of the complete weeks of the year. It is shaded grey in the left panel.
- Times are local, at the start of each hour. Missing hours are gaps in the lines.

The forecast has the same annual demand as the actual one, so the two differ only by the hourly profile, which the WAPE measures.

### Compare two versions

```yaml
figure: ml_results
version: xgboost_model_20261029_144400
compare_with_version: xgboost_model_20261101_090000
```

This draws `<metric>_<name of version>_vs_<name of other version>.png`. The left panel has a box plot of each version (blue for `version`, orange for `compare_with_version`). The right panel has two bars per code, sorted by the error of `version`. The legend names each version by the `<name>` of its files.

Both versions are read from the same `results` folder, so you compare two validations or two cross-validations, not one of each. Only the codes with an error in both versions are drawn; the log lists the others.

### Errors by group

```yaml
figure: ml_results
version: example1
by_group: true
metric: MAPE
```

This compares, for each code, the error of the model trained on all the data with that of a model trained only on the data of its group. It draws two figures:

- `<metric>_<name>_by_income.png`, for the lower-middle, upper-middle and high-income groups. The low-income group has no results, so it is left out.
- `<metric>_<name>_by_continent.png`, for Africa, Asia, Europe, Oceania, North America and South America.

Each group has a box plot and bars of both errors: blue for the model trained on all the data, orange for the model trained on the data of the group.

The results of each group are named after it: `AF`, `AS`, `EU`, `NA`, `OC`, `SA`, `lower_middle_income`, `upper_middle_income` and `high_income`, instead of `all`.

!!! warning
    `validate.py` and `cross_validate.py` only save results named `all`. The results by group exist only in the MAPE files of earlier versions (see below), so in practice `by_group` needs such a version and `metric: MAPE`.

### Results of earlier versions

Earlier versions saved their results as CSV files in a folder named after the version, such as `data/results/validation/<version>/all.csv`, with the columns `entity_code` and `MAPE_test`. When this folder exists, `plot.py` reads it instead of the Parquet files. These files have no WAPE and no manifest, so plot them with `metric: MAPE`. Their figures are named `mape_<version>...png` and titled `Version <version>`. The folder `demandcast/tests/figures/mape_examples/` has two examples.

## Current state page

```yaml
figure: status
```

The `status` figure refreshes the [Current state](../status.md) page and the README. Run it from a clone of the repository, because it writes files of the repository, and then commit the files it changes.

It does these steps, in order:

1. It draws the map and the data availability figure (both described above).
2. It counts the countries, subdivisions, data sources and years of data, from the YAML files of the data sources.
3. It finds the validation and the cross-validation results to publish, and draws their three WAPE figures each.
4. It writes the numbers into the README, between the markers `<!-- status:start -->` and `<!-- status:end -->`.
5. It copies the figures into `webpage/docs/status/` and writes the texts there.

If a step before 4 fails, the README and the page are left as they were.

### Files it updates

| File | What it holds |
|---|---|
| `README.md` (block between the markers) | The sentence of `numbers.md`. The README also shows `available_entities.png`. |
| `webpage/docs/status/numbers.md` | The date, the countries and subdivisions with data, the countries they cover, the data sources, and the years of data since the first year. |
| `webpage/docs/status/ml_model.md` | The algorithms of the models of the two evaluations. |
| `webpage/docs/status/ml_validation.md` | The median WAPE of the validation: of all the codes, of those the model saw in training, and of those it never saw. |
| `webpage/docs/status/ml_cross_validation.md` | The holdout of the cross-validation, the number of held-out codes and their median WAPE. |
| `webpage/docs/status/available_entities*.png` | The map: white, light and dark versions. |
| `webpage/docs/status/data_availability_by_gdp_ppp_and_electricity_demand.png` | The data availability figure. |
| `webpage/docs/status/wape_validation.png`, `wape_validation_distribution.png`, `wape_validation_best_and_worst.png` | The figures of the validation, renamed without the version. |
| `webpage/docs/status/wape_cross_validation.png`, `wape_cross_validation_distribution.png`, `wape_cross_validation_best_and_worst.png` | The figures of the cross-validation, renamed without the version. |

The figures are also kept, with their full names, in `data/results/figures/`.

### The numbers

The numbers come from the YAML files of the data sources:

- Countries are the codes without `_`; subdivisions are the codes with `_`.
- The countries covered are the countries with national data or data of some of their subdivisions.
- The years of data add up the days that the data sources of each code cover (overlapping periods of a code count once), divided by 365.25. A country and its subdivisions count separately. These are the periods of the data sources, before cleaning and before the selection of complete years for training.
- The date is today's date on your computer.

A test (`tests/figures/test_status.py`) checks that the README block and `numbers.md` match the data sources, apart from the years of data, which grow every day. When you add a data source or change a YAML file, the test fails and its message gives the new sentence. Run `plot.py` with `figure: status`, or paste the sentence into both files.

### Which results it publishes

By default, the page publishes the latest validation and the latest cross-validation, by the time in their file names, across all the trained models and algorithms in `data/results/validation/` and `data/results/cross_validation/`. To publish other results, give their files:

```yaml
figure: status
validation_results: data/results/validation/with_xgboost_model_20261029_144400/using_<data>/all_20261030_101500.parquet
cross_validation_results: data/results/cross_validation/with_xgboost/using_<data>/all_20261029_161733.parquet
```

The files must keep the folder layout `with_<version>/using_<data>/`, because the version is read from it. The results are checked against their manifest, which must record their summary and their predictions; otherwise `plot.py` stops with an error.

If a case has no results, its text says "The models have no validation yet." (or "no cross-validation yet"), and no figure is drawn for it.

The cross-validation text depends on its holdout. With `holdout: entity`, each country or subdivision is left out in turn, and the median WAPE estimates the error for a code without data whose country may have data of its other subdivisions. With `holdout: country`, each country is left out with its subdivisions, and the median WAPE estimates the error for a country without data.

## Output files

All figures are PNG files at 300 dpi, in `data/results/figures/`. Each file gets its final name only once it is complete.

| `figure` | Files |
|---|---|
| `data_availability` | `data_availability_by_gdp_ppp_and_electricity_demand.png` |
| `map_of_available_entities` | `available_entities_for_aed.png`, `available_entities.png`, `available_entities_light_mode.png`, `available_entities_dark_mode.png` |
| `ml_results` | `<metric>_<name>.png`, `<metric>_<name>_distribution.png`, `wape_<name>_best_and_worst.png`; or `<metric>_<name>_vs_<other name>.png`; or `<metric>_<name>_by_income.png` and `<metric>_<name>_by_continent.png` |
| `status` | All the files of the map and the data availability, the three WAPE figures of each case, and the files of the repository listed in [Files it updates](#files-it-updates) |
