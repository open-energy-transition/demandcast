# Configuration files

This page lists every configuration file of DemandCast and where its options are explained. Use it to find the file that controls a behaviour.

## How settings work

Each script reads its settings from a YAML file in `demandcast/config/`, named after the script: `retrieve.py` reads `config/retrieve_config.yaml`, and so on. To use another file, pass it with `--config` (or `-c`):

```bash
uv run retrieve.py --config config/my_retrieval.yaml
```

Keeping one file per task (for example, one for each variable you retrieve) saves you from editing the default file each time.

Before it starts, each script checks its settings and stops with a clear error if:

- an option is misspelt or does not exist;
- a required option is missing;
- a value is not allowed, such as a scenario or climate model that the data does not have (the error lists the valid values).

Each option in the default files is marked `REQUIRED` or `OPTIONAL`, with a comment that explains it. An `OPTIONAL` option left empty takes its default value.

## Settings of the scripts

| File | Read by | Options explained in |
|---|---|---|
| `retrieve_config.yaml` | `retrieve.py` | [Retrieve data](../guides/retrieve.md) |
| `assemble_config.yaml` | `assemble.py` | [Assemble a dataset](../guides/assemble.md) |
| `train_config.yaml` | `train.py` | [Train and validate](../guides/train-validate.md) |
| `validate_config.yaml` | `validate.py` | [Train and validate](../guides/train-validate.md) |
| `cross_validate_config.yaml` | `cross_validate.py` | [Cross-validate](../guides/cross-validate.md) |
| `forecast_config.yaml` | `forecast.py` | [Forecast](../guides/forecast.md) |
| `plot_config.yaml` | `plot.py` | [Plot figures](../guides/plot.md) |
| `check_config.yaml` | `check.py` (default file) | [Run checks](../guides/check.md) |
| `check_data_sources_config.yaml` | `check.py --config config/check_data_sources_config.yaml` | [Run checks](../guides/check.md) |
| `check_flags_config.yaml` | `check.py --config config/check_flags_config.yaml` | [Run checks](../guides/check.md) |
| `sync_config.yaml` | `sync.py` | [Share the data folder](../guides/sync.md) |
| `publish_config.yaml` | `publish.py` | [Publish a release](../guides/publish.md) |

## Settings of the models

The training, validation, cross-validation and forecasting scripts share these files. They are read by the model code, not passed with `--config`.

| File | What it sets | Explained in |
|---|---|---|
| `ml_config.yaml` | Settings shared by all models, such as the algorithm and the data preparation | [Train and validate](../guides/train-validate.md) |
| `xgboost_config.yaml` | The settings of the XGBoost model | [Train and validate](../guides/train-validate.md) |
| `lstm_config.yaml` | The settings of the optional LSTM model | [Train and validate](../guides/train-validate.md) |

## Lists that the code reads

These files are data, not settings. You rarely change them, except to add a country or subdivision.

| File | What it holds | Used by |
|---|---|---|
| `world_countries.yaml` | The countries of the world, with their names and ISO 3166 alpha-3 codes | The tests check the countries of each data source against it |
| `available_subdivisions.yaml` | Every subdivision a data source may have, with its code and name. Standard subdivisions use ISO 3166-2 codes; the others use a widely accepted code and have their shapes in `shapes/subdivisions/` | The tests check the subdivisions of each data source against it |
| `continents.yaml` | The continent of each country | `utils/codes.py`, for grouping results by continent |
| `related_entities.yaml` | Exceptions to the [related entities](../concepts/glossary.md#related-entities): pairs that are always related (`related`) or never related (`unrelated`), whatever their shared population | `utils/relations.py`, for the splits of training and cross-validation |
| `oet_zenodo_metadata.yaml` | The creators and contributors of a new Zenodo record | `publish.py` (its `metadata_file` option) |

Other inputs that come with the code, rather than with the data, live outside `config/`:

| Location | What it holds | Explained in |
|---|---|---|
| `retrievals/electricity_demand_data_sources/*.yaml` | One file per electricity demand data source: its entities, dates, licence and demand definition | [Data sources](data-sources.md) |
| `shapes/subdivisions/<ISO3>.yaml` | The shapes of the non-standard subdivisions of a country, defined by the standard subdivisions that make them up | [Retrieve data](../guides/retrieve.md) |
| `checks/reviewed_flags.yaml` | Your reviews of the quality flags of the electricity demand | [Electricity demand data](../concepts/electricity-demand.md) |
| `checks/data_availability_summary.csv` | Which countries and subdivisions have all the inputs the models need (written by `check.py`) | [Run checks](../guides/check.md) |
| `checks/related_entities.csv`, `checks/related_entities_codes.txt` | The shared population of overlapping entities, and the codes considered (written by `check.py`) | [Run checks](../guides/check.md) |
| `benchmark/*.yaml` | The settings of the retrieval and assembly of the benchmark data (run with `benchmark/run.py`) | [Models](../concepts/models.md) |

## A codes file

Several scripts take a `file` option: a YAML file that lists the countries and subdivisions to work on. It has the same format as the `entities` of a data source:

```yaml
entities:
  - country_name: France
    country_code: FRA
  - country_name: United States
    country_code: USA
    subdivision_name: California
    subdivision_code: CAL
```

Only the codes are read: `country_code` (ISO 3166 alpha-3) for a country, plus `subdivision_code` for a subdivision, whose full code joins the two with an underscore, such as `USA_CAL`. The names are optional but make the file easier to read. Use the codes of `world_countries.yaml` and `available_subdivisions.yaml`.

!!! warning
    The file is not checked before use: a misspelt `country_code` key stops the script with a `KeyError`.
