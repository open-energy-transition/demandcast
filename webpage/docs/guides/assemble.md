# Assemble a dataset

`assemble.py` merges the retrieved data into one table, with one row per hour and per country or subdivision. Run it after you retrieve the data (see [Retrieve data](retrieve.md)) and before you train a model or forecast.

## Run it

```bash
cd demandcast
uv run assemble.py                                  # settings of config/assemble_config.yaml
uv run assemble.py --config config/my_assembly.yaml # another settings file
```

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `target_use` | Yes | – | `training`: with the electricity demand, for `train.py`, `validate.py` and `cross_validate.py`. `forecasting`: the inputs only, for `forecast.py` |
| `file` | No | all entities | A [codes file](../reference/configuration.md#a-codes-file) that lists the countries and subdivisions to assemble. A relative path starts from the folder you run the script in |
| `start_year`, `end_year` | No | all years | The first and last [local year](../concepts/glossary.md#local-day) to keep. Give both or neither |
| `scenario_for_annual_electricity_demand_per_capita` | No | historical | The scenario of the annual electricity demand per capita, such as `SSP2-45` |
| `scenario_for_gdp_ppp_per_capita` | No | historical | The scenario of the GDP PPP per capita, such as `SSP2` |
| `scenario_for_population` | No | historical | The scenario of the population, such as `SSP2` |
| `scenario_for_temperature` | No | historical | The scenario of the temperature, such as `SSP2-4.5`. Give `climate_model_for_temperature` too |
| `climate_model_for_temperature` | No | historical | The climate model of the temperature, such as `CESM2`. Give `scenario_for_temperature` too |

`start_year` and `end_year` select the local years of the temperature; the merge then keeps the same years of the other inputs.

## Training or forecasting

| | `target_use: training` | `target_use: forecasting` |
|---|---|---|
| Entities, without `file` | Every entity that a data source of electricity demand lists | Every entity with all the data the models need: shapes, and historical and projected population, electricity demand per capita and GDP PPP per capita (from the data availability check, see [Run checks](check.md)) |
| Entities, with `file` | The codes of the file that qualify as above; the others are logged as errors and left out | The same |
| Electricity demand | Merged; only the hours eligible for training | Not used |
| Years | Only those with enough hours (see [Year coverage](#year-coverage)) | All |
| Target column | `Load (fraction of annual total)` | None |
| Extra files | `_coverage.csv` and `_provenance.csv` | None |

If no code of `file` qualifies, the script stops with `None of the codes in the file are available` and lists the valid codes.

## Inputs

The inputs are the rows of `DATASETS` in `assemble.py`. Each is a folder of the data folder with one Parquet file per entity, or per entity and local year. [Inputs](../concepts/inputs.md) explains what each one means and lists its scenarios.

| Input | Folder | Columns | Scenarios |
|---|---|---|---|
| Annual electricity demand per capita | `annual_electricity_demand_per_capita/` | `Annual electricity demand per capita (kWh)` | IAMC (such as `SSP2-45`) |
| GDP PPP per capita | `gdp_ppp_per_capita/` | `GDP PPP per capita (2021 international $)` | SSP (`SSP1` to `SSP5`) |
| Population | `population/` | `Population` | SSP |
| Temperature | `temperature/`, one file per local year | The seven temperature columns, the calendar columns and `Local year` | Those of each climate model |
| Electricity demand (training only) | `electricity_demand/combined/` | `Load (MW)` | None |

To add an input, add a row to `DATASETS` with its folder, columns and scenarios, and its option `scenario_for_<name>` (and `climate_model_for_<name>` for a climate input) to the `ConfigModel`.

## Scenarios and climate models

Leave every scenario empty for historical data, as for training or for a forecast of a past year. To forecast a future year, choose one scenario per input. The script then reads the files that the retrieval wrote for that scenario: `<code>_<SCENARIO>.parquet` for an indicator, and `<code>_<year>_<MODEL>_<SCENARIO>.parquet` for the temperature, in upper case with underscores for hyphens and dots.

Each scenario and climate model is checked against the catalogue (`utils/catalogue.py`), in any case. A wrong one stops the script with the list of valid values.

!!! warning
    Give the temperature scenario and its climate model together. With only one, the settings pass the check but no temperature file matches: the log warns "No temperature files found" for each entity, and the script stops with `No objects to concatenate`.

Choose consistent scenarios: the same SSP for population and GDP, and demand per capita and temperature scenarios of that SSP. For example:

```yaml
target_use: forecasting
file: config/spain_only.yaml
start_year: 2030
end_year: 2030
scenario_for_annual_electricity_demand_per_capita: SSP2-45
scenario_for_gdp_ppp_per_capita: SSP2
scenario_for_population: SSP2
scenario_for_temperature: SSP2-4.5
climate_model_for_temperature: CESM2
```

## How the rows are built

1. **Select the entities**, as in [Training or forecasting](#training-or-forecasting).
2. **Refresh the combined demand** (training only). A combined series that is not current is combined again from the cleaned data, so the eligible hours follow the current reviews (see [When the combination runs again](../concepts/electricity-demand.md#when-the-combination-runs-again)).
3. **Load each input of each entity.** A missing file is logged and skipped. Then:
    - the electricity demand keeps only its [eligible](../concepts/electricity-demand.md#eligibility-for-training) hours, and the log counts those left out;
    - text columns, such as the data source of each hour, are dropped;
    - rows with a missing value are dropped;
    - rows are averaged into hours, labelled by their end in UTC (this aligns entities whose times fall on the half hour);
    - rows where a column of the input is zero or negative are dropped.
4. **Keep the years** from `start_year` to `end_year`, if given.
5. **Merge the inputs** on `Time (UTC)` and `Entity code`, keeping only the hours that every input has. The log lists, for each input, the entities the merge left out.
6. **Add `Local holiday indicator`** (see [Input features](../concepts/models.md#input-features)).
7. **Keep the years with enough hours** (training only, see [Year coverage](#year-coverage)).
8. **Compute the target** `Load (fraction of annual total)` (training only, see [The target](../concepts/models.md#the-target)).
9. **Sort** the rows by entity and time (the LSTM needs consecutive hours) and write the files.

## Year coverage

The target divides each hour by the annual demand, estimated from the hours with data. A year without its winter or summer would get the wrong annual demand. So the training data keeps only the years that pass both rules:

| Rule | What it catches | Threshold |
|---|---|---|
| Year coverage | Years with too few hours | At least 90% of the hours of the local year |
| Lowest month coverage | Years missing most of a season | At least 50% of the hours of every month |

The log lists the years left out; `_coverage.csv` lists every year.

## Output files

The files go to the `assembled/` folder of the [data folder](../reference/data-folder.md#assembled-data). `<time>` is the local time of the run, `YYYYMMDD_HHMMSS`. When you give no path, the other scripts take the [latest file](../reference/data-folder.md#which-file-is-the-latest) of the purpose they need.

| File | What it holds |
|---|---|
| `assembled_data_for_<target_use>_<time>.parquet` | The assembled data |
| `assembled_data_for_<target_use>_<time>.manifest.json` | Its [manifest](../reference/data-folder.md#manifests) |
| `assembled_data_for_training_<time>_coverage.csv` | The coverage of each year of each entity (training only) |
| `assembled_data_for_training_<time>_provenance.csv` | The data sources and definitions of the demand of each year (training only) |
| `logs/assembly_of_retrieved_data_<time>.log` | The log |

### Columns of the assembled data

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` | The end of the hour, in UTC | – |
| `Entity code` | The code of the country or subdivision | – |
| `Annual electricity demand per capita (kWh)`, `GDP PPP per capita (2021 international $)`, `Population` | The values of the local year | kWh, 2021 international $, people |
| `Local hour of the day`, `Local weekend indicator`, `Local month of the year`, `Local year` | The calendar of the start of the hour in local time | – |
| The seven temperature columns | See [Inputs](../concepts/inputs.md#temperature) | K, or a rank |
| `Load (MW)` | The mean electricity demand of the hour (training only) | MW |
| `Local holiday indicator` | 1 on a public holiday, else 0 | – |
| `Load (fraction of annual total)` | The target (training only) | fraction |

The calendar columns and `Local year` are decimal numbers, such as `2023.0`, because the hourly averaging turns them into floats.

### Columns of `_coverage.csv`

| Column | Meaning |
|---|---|
| `Entity code`, `Local year` | The entity and the local year |
| `Hours` | The hours of the year in the merged data |
| `Year coverage` | `Hours` over the hours of the year (fraction) |
| `Lowest month coverage` | The lowest share of the hours of a month (fraction) |
| `Kept` | Whether the year is in the dataset |

### Columns of `_provenance.csv`

This file records where the demand of the kept hours came from, from the combined demand at assembly time. The validation and cross-validation read it to describe the entities (see [Reporting by group](../concepts/models.md#reporting-by-group)).

| Column | Meaning |
|---|---|
| `Entity code`, `Local year` | The entity and the local year |
| `Source` | The data source of the hours |
| `Definition` | What the demand counts of the [embedded generation](../concepts/glossary.md#embedded-generation); empty if the data source does not say |
| `Hours` | The number of hours with this source and definition |

## Common problems

| Symptom | Fix |
|---|---|
| `Both start_year and end_year must be provided` | Set both, or neither |
| An entity is missing from the output | Read the log: one of its inputs lacks the hours of the others, or none of its years has enough hours |
| `None of the codes in the file are available` | Check the codes; for training, retrieve their electricity demand |
| `does not say which hours can be used for training` | A combined file without the `Eligible` column could not be combined again: retrieve the electricity demand of the entity again |

For `No objects to concatenate` and a missing year, see the [FAQ](../help/faq.md#assembling-training-and-forecasting).
