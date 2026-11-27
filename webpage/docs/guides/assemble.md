# Assemble a dataset

`assemble.py` merges the retrieved data into one table, with one row per hour and per country or subdivision. Run it after you retrieve the data and before you train a model or forecast.

## Run it

```bash
cd demandcast
uv run assemble.py                                  # settings of config/assemble_config.yaml
uv run assemble.py --config config/my_assembly.yaml # another settings file
```

The script needs the data of every input (see [Inputs](#inputs)) for the entities you want. Retrieve them first with `retrieve.py` (see [Retrieve data](retrieve.md)).

## Options

| Option | Required? | Default | What it does |
|---|---|---|---|
| `target_use` | Yes | – | `training` to assemble data with the electricity demand, for `train.py`, `validate.py` and `cross_validate.py`; `forecasting` to assemble the inputs only, for `forecast.py` |
| `file` | No | all entities | The path of a codes file that lists the countries and subdivisions to assemble (see [a codes file](../reference/configuration.md#a-codes-file)). A path relative to the `demandcast/` folder works when you run from it |
| `start_year` | No | all years | The first local year to keep. Give `end_year` too |
| `end_year` | No | all years | The last local year to keep. Give `start_year` too |
| `scenario_for_annual_electricity_demand_per_capita` | No | historical data | The scenario of the annual electricity demand per capita, such as `SSP2-45` |
| `scenario_for_gdp_ppp_per_capita` | No | historical data | The scenario of the GDP PPP per capita, such as `SSP2` |
| `scenario_for_population` | No | historical data | The scenario of the population, such as `SSP2` |
| `scenario_for_temperature` | No | historical data | The scenario of the temperature projection, such as `SSP2-4.5`. Give `climate_model_for_temperature` too |
| `climate_model_for_temperature` | No | historical data | The climate model of the temperature projection, such as `CESM2`. Give `scenario_for_temperature` too |

A *local year* is the calendar year in the time zone of the entity. `start_year` and `end_year` select the local years of the temperature; the merge then keeps the same years of the other inputs. If you give only one of the two, the script stops.

## Training or forecasting

| | `target_use: training` | `target_use: forecasting` |
|---|---|---|
| Entities, without `file` | Every entity that some data source of electricity demand lists | Every entity with all the data the models need: shapes, and historical and projected population, electricity demand per capita and GDP PPP per capita (from the data availability summary, see [Run checks](check.md)) |
| Entities, with `file` | The codes of the file that a data source lists; the others are logged as errors and left out | The codes of the file with all that data; the others are logged as errors and left out |
| Electricity demand | Merged; only the hours eligible for training | Not used |
| Years | Only those with enough hours (see [Year coverage](#year-coverage)) | All |
| Target column | `Load (fraction of annual total)` added | None |
| Extra files | `_coverage.csv` and `_provenance.csv` | None |

If no code of `file` qualifies, the script stops and lists the valid codes.

## Inputs

The inputs are the rows of `DATASETS` in `assemble.py`, in the order of their columns. Each one is a folder of the data folder with one Parquet file per entity, or per entity and local year.

| Input | Folder | Columns | Scenarios | Only for training |
|---|---|---|---|---|
| Annual electricity demand per capita | `annual_electricity_demand_per_capita/` | `Annual electricity demand per capita (kWh)` | IAMC scenarios (such as `SSP2-45`) | No |
| GDP PPP per capita | `gdp_ppp_per_capita/` | `GDP PPP per capita (2021 international $)` | SSP scenarios (`SSP1` to `SSP5`) | No |
| Population | `population/` | `Population` | SSP scenarios | No |
| Temperature | `temperature/`, one file per local year | The seven temperature columns, plus the calendar columns and `Local year` | The scenarios of each climate model | No |
| Electricity demand | `electricity_demand/combined/` | `Load (MW)` | None | Yes |

The annual indicators are stored as hourly series: each hour takes the value of its local year. The temperature files also hold the calendar of each hour in local time (`Local hour of the day`, `Local weekend indicator`, `Local month of the year`, `Local year`). See [Inputs](../concepts/inputs.md) for what each input means and where it comes from.

To add an input, add a row to `DATASETS` with its folder, columns and scenarios. Its option `scenario_for_<name>` (and `climate_model_for_<name>` for a climate input) must then exist in the `ConfigModel`.

## Scenarios and climate models

Leave every scenario empty to assemble historical data, as for training or for a forecast of a past year. To forecast a future year, choose one scenario per input. The files read are those that the retrieval wrote for that scenario: `<code>_<SCENARIO>.parquet` for an indicator, and `<code>_<year>_<MODEL>_<SCENARIO>.parquet` for the temperature, in upper case with underscores for hyphens and dots.

The script checks each scenario and climate model against the catalogue (`utils/catalogue.py`), whatever their case, and stops with the list of valid values if one is not there. The scenarios of each input are listed in [Inputs](../concepts/inputs.md).

!!! warning
    Give the temperature scenario and its climate model together. With only one of them, the settings pass the check, but no temperature file matches: the log warns "No temperature files found" for each entity and the script stops with `No objects to concatenate`.

Choose consistent scenarios: the same SSP for population and GDP, and a demand per capita and temperature scenario of the same SSP. For example:

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
2. **Refresh the combined demand** (training only). If the combined electricity demand of an entity is older than its cleaned data, or its *fingerprint* (the rules, reviews and data sources it was made with) has changed, the script combines it again from the cleaned data. So the hours eligible for training always follow the current reviews. See [Electricity demand](../concepts/electricity-demand.md).
3. **Load each input of each entity.** A missing file is logged and skipped.
    - The electricity demand keeps only its *eligible* hours, those that the cleaning allows for training; the log counts the hours left out. A combined file without the `Eligible` column stops the script.
    - Text columns, such as the data source of each hour, are dropped.
    - Rows with a missing value are dropped.
    - The rows are averaged into hours, each labelled by its end in UTC. Some entities have times at the half hour, from their time zone, and this aligns them.
    - Rows where a column of the input is zero or negative are dropped.
4. **Keep the years** from `start_year` to `end_year`, if given.
5. **Merge the inputs** on `Time (UTC)` and `Entity code`, keeping only the hours that every input has. The log lists, for each input, the entities that the merge left out.
6. **Add `Local holiday indicator`**: 1 for the hours that start on a public holiday in local time (see [Input features](../concepts/models.md#input-features)).
7. **Keep the years with enough hours** (training only, see [Year coverage](#year-coverage)).
8. **Compute the target** `Load (fraction of annual total)` (training only, see [The target](../concepts/models.md#the-target)).
9. **Sort** the rows by entity and time, since the LSTM needs consecutive hours, and write the files.

## Year coverage

The target divides each hour by the annual demand, estimated from the hours of the year with data. Those hours must represent the whole year: a year without its winter or its summer would have the wrong annual demand. So the training data keeps only the years of an entity that pass both rules:

| Rule | What it catches | Threshold |
|---|---|---|
| Year coverage | Years with too few hours | At least 90% of the hours of the local year |
| Lowest month coverage | Years missing most of a season | At least 50% of the hours of every month |

The log lists the years left out. The `_coverage.csv` file lists every year with its coverage and whether it was kept.

## Output files

The files go to `data/assembled/` (or the `assembled/` folder of `DEMANDCAST_DATA_FOLDER`). `<time>` is the local time of the run, `YYYYMMDD_HHMMSS`.

| File | What it holds |
|---|---|
| `assembled_data_for_<target_use>_<time>.parquet` | The assembled data |
| `assembled_data_for_<target_use>_<time>.manifest.json` | Its manifest: purpose, settings, columns, rows, entities, and a checksum of the files of each input (see [Manifests](../concepts/models.md#manifests)) |
| `assembled_data_for_training_<time>_coverage.csv` | The coverage of each year of each entity (training only) |
| `assembled_data_for_training_<time>_provenance.csv` | The data sources and definitions of the demand of each year (training only) |
| `logs/assembly_of_retrieved_data_<time>.log` | The log, in the logs folder |

The other scripts take the latest file of each purpose by the time in its name, unless you give a path. A copy whose name ends otherwise is never taken.

### Columns of the assembled data

| Column | Meaning | Unit |
|---|---|---|
| `Time (UTC)` | The end of the hour, in UTC | – |
| `Entity code` | The code of the country or subdivision | – |
| `Annual electricity demand per capita (kWh)` | The value of the local year | kWh |
| `GDP PPP per capita (2021 international $)` | The value of the local year | 2021 international $ |
| `Population` | The value of the local year | people |
| `Local hour of the day`, `Local weekend indicator`, `Local month of the year` | The calendar of the start of the hour in local time | – |
| `Local year` | The local year of the start of the hour | – |
| The seven temperature columns | See [Input features](../concepts/models.md#input-features) | K, or a rank |
| `Load (MW)` | The mean electricity demand of the hour (training only) | MW |
| `Local holiday indicator` | 1 on a public holiday, else 0 | – |
| `Load (fraction of annual total)` | The target (training only) | fraction |

The calendar columns and `Local year` are stored as decimal numbers, such as `2023.0`, because the hourly averaging turns them into floats.

### Columns of `_coverage.csv`

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the entity | – |
| `Local year` | The local year | – |
| `Hours` | The hours of the year in the merged data | hours |
| `Year coverage` | `Hours` over the hours of the year | fraction |
| `Lowest month coverage` | The lowest share of the hours of a month | fraction |
| `Kept` | Whether the year is in the dataset | – |

### Columns of `_provenance.csv`

This file records, from the combined demand at the time of the assembly, where the demand of the kept hours came from. The results of the validation and cross-validation read it, so later retrievals or reviews do not change how they describe the entities.

| Column | Meaning | Unit |
|---|---|---|
| `Entity code` | The code of the entity | – |
| `Local year` | The local year | – |
| `Source` | The data source of the hours | – |
| `Definition` | What the demand counts of the embedded generation, empty if the data source does not say | – |
| `Hours` | The number of hours with this source and definition | hours |

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `Both start_year and end_year must be provided` | Only one of them is set | Set both, or neither |
| `No objects to concatenate` | No entity has files for an input: it was not retrieved, or the scenario or climate model is wrong or incomplete | Retrieve the input, or set both the temperature scenario and its climate model |
| An entity is missing from the output | One of its inputs lacks the hours of the others, or none of its years has enough hours | Read the log: it lists the entities each merge left out and the years left out |
| `None of the codes in the file are available` | No code of `file` has the data that the use needs | Check the codes, and retrieve their electricity demand for training |
| `does not say which hours can be used for training` | An old combined file without the `Eligible` column that could not be combined again | Retrieve the electricity demand of the entity again |
