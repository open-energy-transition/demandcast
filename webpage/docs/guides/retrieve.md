# Retrieve data

`retrieve.py` downloads one kind of data for the countries and subdivisions you choose, and saves it in the [data folder](../reference/data-folder.md).

## Run a retrieval

Each run retrieves one **variable** (one kind of data). Set the options in `config/retrieve_config.yaml`, or in another YAML file passed with `--config`:

```bash
cd demandcast
uv run retrieve.py
uv run retrieve.py --config config/my_retrieval.yaml
```

A misspelt option, an unknown data source or scenario, or a missing required option stops the script before it starts, with the valid values.

A minimal file that retrieves the electricity demand of France from ENTSO-E:

```yaml
variable: electricity_demand
electricity_data_source: entsoe
code: FRA_CONTINENTAL
```

## Variables

Each variable is saved in the folder of the same name under the data folder, such as `population/`.

| `variable` | What it retrieves |
|---|---|
| `electricity_demand` | Hourly or sub-hourly demand of one data source, then cleaned and combined with the other sources of each code (see [below](#electricity-demand)) |
| `annual_electricity_demand_per_capita` | Yearly demand per person: Ember and World Bank history, IIASA projections |
| `population` | Population: World Bank history, IIASA projections |
| `gridded_population` | Population on a 0.25° grid |
| `gdp_ppp_per_capita` | [GDP PPP](../concepts/glossary.md#gdp-ppp) per person |
| `gridded_gdp_ppp` | GDP PPP on a 0.25° grid |
| `gridded_weather` | [ERA5](../concepts/glossary.md#era5) reanalysis or climate model projections on a grid |
| `temperature` | Hourly temperature of the most populous grid cells |

[Weather and socio-economic inputs](../concepts/inputs.md) explains the sources, units and processing of all variables but the electricity demand.

## Options

"Default" is the value of a missing or empty option. The shipped `config/retrieve_config.yaml` sets `variable: electricity_demand`, `electricity_data_source: entsoe` and `weather_variable: temperature`.

| Option | Default | Applies to | What it does |
|---|---|---|---|
| `variable` | required | all | The variable to retrieve, from the table above. |
| `electricity_data_source` | required for `electricity_demand` | `electricity_demand` | The data source: the name of its YAML file, such as `entsoe` (case-sensitive). See [Data sources](../reference/data-sources.md). |
| `code` | none | all | One country or subdivision, such as `FRA` or `USA_CAL`. Wins over `file`. |
| `file` | none | all | A [codes file](../reference/configuration.md#a-codes-file) listing several countries and subdivisions. A relative path starts from the folder you run the script in. |
| `year` | none | all but `electricity_demand` | One year. Not with `start_year` or `end_year`. |
| `start_year`, `end_year` | none | all but `electricity_demand` | First and last years of a range, both included. Set both. |
| `scenario` | all scenarios | all but `electricity_demand` | One scenario, in any case. An error with `electricity_demand`. |
| `weather_variable` | required for `gridded_weather` | `gridded_weather` | Only `temperature` exists. |
| `climate_model` | all models | `gridded_weather`, `temperature` | One climate model for the future years, in any case, such as `CESM2`. |
| `reanalysis_source` | `points` | `gridded_weather`, `temperature` | Where past weather comes from: `points` (ERA5 time series of single points, a few MB; `temperature` only, and `cds` for `gridded_weather`), `cds` (ERA5 grids of the CDS, queued, about 5 GB a year for all codes) or `arco` (ARCO-ERA5 on Google Cloud, no account). See [Inputs](../concepts/inputs.md#where-the-past-weather-comes-from). Climate projections always come from the CDS. |
| `offline` | `false` | `electricity_demand` | Process the saved raw data again, without the network (see [below](#process-again-without-downloading-offline)). |
| `latest_requests` | none (all) | `electricity_demand` | A number of 1 or more: download only that many latest requests of each code, plus those never downloaded (see [below](#download-only-the-latest-requests-latest_requests)). |

!!! warning
    An option that does not apply to the variable is ignored without a warning, such as `year` with `electricity_demand`. Only `scenario` with `electricity_demand` stops with an error.

## Choose countries and subdivisions

Each country or subdivision is an [entity](../concepts/glossary.md#entity), named by its [code](../concepts/glossary.md#code): `FRA` for a country, `USA_CAL` for a subdivision. The script picks the codes in this order:

1. `code`: this code only. If it does not have the data, the script stops and lists the valid codes.
2. `file`: the codes of the file. Codes without the data are logged as errors and skipped; if none is left, the script stops.
3. Neither: all the codes that have the data.

"Have the data" depends on the variable:

- `electricity_demand`: the codes in the YAML file of the data source.
- Other variables: the codes with historical data in `checks/data_availability_summary.csv` (see [How the other scripts use it](check.md#how-the-other-scripts-use-it)).

The YAML files of the data sources and `config/available_subdivisions.yaml` are valid codes files too.

Codes with history but no IIASA projections, such as Kosovo (`XKX`), get only their past years: they train the models but are not forecast for future scenarios.

## Years, scenarios and climate models

These options apply to all variables but `electricity_demand`, whose dates come from the YAML file of its data source.

- Without a year option, the script retrieves every available year, past and future up to 2100.
- `year` must be available, or the run fails.
- `start_year` and `end_year` keep the available years between them. A bound outside them only logs a warning.

| Variable | Past years | Future years | `scenario` values |
|---|---|---|---|
| `population`, `gdp_ppp_per_capita` | Years of the World Bank (and IMF) data, carried forward to last year | Up to 2100 | [SSP](../concepts/glossary.md#ssp): `SSP1` to `SSP5` |
| `annual_electricity_demand_per_capita` | Years of the Ember or World Bank data, up to the last year with data | The next year to 2100 | [IAMC](../concepts/glossary.md#iamc-scenario), such as `SSP2-45` or `SSP2-Baseline` |
| `gridded_population` | 2000 to 2020, every 5 years | 2025 to 2100, every 5 years | SSP |
| `gridded_gdp_ppp` | 2000 to 2020 | 2025 to 2100, every 5 years | SSP |
| `gridded_weather`, `temperature` | 1990 to last year (ERA5) | This year to 2100 | CMIP6, such as `SSP2-4.5` |

A past year has no scenario. A future year is retrieved for each scenario, or only for `scenario`. For the weather, it is retrieved for each climate model and each of its scenarios, or only for `climate_model`. [Scenarios, climate models and years](../concepts/inputs.md#scenarios-climate-models-and-years) lists the models and their scenarios.

!!! warning
    Without `climate_model`, `scenario` must exist for every model: only `SSP1-2.6`, `SSP2-4.5` and `SSP5-8.5` do. `SSP3-7.0` alone fails, because `HadGEM3-GC31-LL` lacks it: set `climate_model` too.

!!! tip
    Always set the years for `gridded_weather` and `temperature`. Otherwise the script retrieves 1990 to 2100 for every model and scenario.

## API keys and accounts

Set keys and accounts in `demandcast/.env`, as [Install](../getting-started/install.md#3-add-your-api-keys) explains. A retrieval needs:

- `CDS_API_KEY`: `gridded_weather` and `temperature`, except past years with `reanalysis_source: arco`;
- `EMBER_API_KEY`: `annual_electricity_demand_per_capita`;
- `ENTSOE_API_KEY`, `EIA_API_KEY`, `EPIAS_USERNAME` and `EPIAS_PASSWORD`, `ISONE_USERNAME` and `ISONE_PASSWORD`: the data sources `entsoe`, `eia`, `epias` and `isone`.

The values of every environment variable whose name ends in `_API_KEY` or `_PASSWORD` are replaced by `***` in errors, logs and saved raw data.

!!! note
    `offline: true` still needs the key or account of `entsoe`, `eia`, `epias` and `isone`: their code reads it before asking for the saved responses.

## Electricity demand

For each code of the data source, a retrieval of `electricity_demand`:

1. splits the dates of the code into **requests**, such as one year or one month each. The dates come from the YAML file of the source; an end date of `today` means five days ago;
2. downloads each request and saves the raw responses (see [Raw data and versions](#raw-data-and-versions));
3. processes all saved versions into MW in `processed/`, keeping only the dates of the code in the YAML file;
4. cleans and flags the processed data in `cleaned/`, and combines all the sources of the code into one hourly series in `combined/`.

[Electricity demand data](../concepts/electricity-demand.md) explains the stages, their files and columns, the cleaning and the combination.

!!! tip
    Retrieve `annual_electricity_demand_per_capita` and `population` for a code before its electricity demand. Without them, the cleaning skips the flags of years whose total looks wrong. You can add them later with `offline: true`.

### Raw data and versions

DemandCast keeps every response that a data source sends. You can then process the data again without the network, and data that a source later changes or deletes is not lost.

- `raw/<data source>/files/<checksum>` holds the content of each response, saved once under its SHA-256 checksum.
- `raw/<data source>/manifest.json` lists the `requests` of each code. Each request has `versions`: one set of responses, with `first_retrieved` and `last_retrieved` (UTC), the `responses` (method, URL, body checksum, status, headers and file of each) and an `error` if its data could not be read.

A request that returns the same responses as its latest version only updates `last_retrieved`; different responses make a new version. [Processed data](../concepts/electricity-demand.md#processed-data) explains how versions and overlapping requests are merged. An older version whose values a new download repeats, unchanged, is deleted with its files, so the request of the current period does not keep a copy at every retrieval.

API keys and passwords are hidden in the manifest. Responses to requests that send a password in their body, such as the login of EPIAS, are not saved.

### Process again without downloading (`offline`)

With `offline: true`, the script reads the saved versions of each code instead of downloading, then saves, cleans, flags and combines as usual. Use it after changing the module of a data source, its YAML file or the cleaning. A code without raw data logs a warning and is skipped. `offline` wins over `latest_requests`.

### Download only the latest requests (`latest_requests`)

Without `latest_requests`, every request is downloaded again, which picks up corrections to old data. With `latest_requests: N`, the script downloads:

- the last `N` requests of each code, whose data can still change; and
- every earlier request without a version, such as a new year or a request that returned no data last time.

The other requests are processed from the raw data.

### Files downloaded by hand

Some sources have no download that can be automated. Download their files from the website into `electricity_demand/raw/manual_downloads/`. Each source reads the files whose names start with its prefix ([Data sources](../reference/data-sources.md) gives them). If no file matches, the error says where to download from and how to name the file.

Keep earlier downloads next to later ones. Each hour takes the value of the file whose data ends last, so revised values win, and earlier files keep the hours that later ones lack. The raw data saves a copy of each file read, so `offline: true` works after you delete or replace them.

### What happens when a request fails

- Temporary errors (timeouts, lost connections, HTTP 408, 425, 429 and 5xx) are tried up to 5 times, 5 seconds apart.
- If the last of several requests of a code is not found (HTTP 404 or 410), it is skipped with a warning: the file of the latest period may not be published yet. Any other request not found is an error.
- A request that returns no data gets no version, so the next retrieval with `latest_requests` downloads it again.
- When a request fails, the responses of the requests before it stay in the raw data.
- If responses arrived but their data cannot be read, such as after a format change, they are saved with the error. Once the module is fixed, `offline: true` processes them.

## When a code fails

For every variable, a retrieval of several codes goes on after a code fails. The log gives its error, with keys and passwords hidden and without the traceback. At the end, the script stops with an error listing the failed codes. Retrieve one of them alone, with `code`, to see the full traceback.

A retrieval of a single code stops at its first error. An error before the loop over the codes, such as a failed download of a global dataset, stops the whole run.

## Logs

Each run writes `logs/retrieval_of_<variable>_<time>.log`, or `logs/retrieval_of_electricity_demand_from_<data source>_<time>.log`, in the data folder. It starts with the validated options. The terminal shows only the progress bars and the final error (see [Logs](../reference/data-folder.md#logs)).

## Non-standard subdivisions

Most subdivisions are standard ISO 3166-2 subdivisions, such as US states, with shapes from [Natural Earth](https://www.naturalearthdata.com/). Some data measures another area, such as a grid region: `FRA_CONTINENTAL` is France without Corsica. These are [non-standard subdivisions](../concepts/glossary.md#non-standard-subdivision), defined by the standard subdivisions that make them up.

- `demandcast/shapes/subdivisions/<ISO3>.yaml` defines those of one country. Each has a `name` and its `standard_subdivisions` (ISO 3166-2 codes of Natural Earth at 1:10m). Optional `cuts` remove parts as WKT polygons, such as isolated systems the grid does not reach. Examples: `AUS_QLD1` (Queensland without its north-west and Cape York), `BRA_N` (six states of Brazil, without most of Amazonas), `JPN_Kantō` (Kantō and Yamanashi, with Shizuoka east of the Fuji River).
- `demandcast/shapes/eia.py` writes the EIA regions to `USA.yaml` and keeps the file's other subdivisions. Each US county goes to the region with the most retail sales in it, from EIA-861. Where that region leads by less than 15% of the sales, and in Texas, the county follows the zones of Electricity Maps. For each new year of EIA-861, change `EIA861_YEAR` in the script and run `uv run shapes/eia.py`.
- When the measured area changes, such as when isolated systems join a grid, each period is a separate subdivision named after its first year and drawn as the area was then. The North subsystem of Brazil is `BRA_N-2000`, `BRA_N-2013`, `BRA_N-2015` and, from 2025, `BRA_N`. Periods start on 1 January.

When a shape changes, the next retrieval cuts the grids of that code again (see [Countries, subdivisions and shapes](../concepts/inputs.md#countries-subdivisions-and-shapes)).

## Recommended order

To retrieve everything for a new set of codes:

1. `population` and `annual_electricity_demand_per_capita`, so the cleaning can check the annual demand.
2. `electricity_demand`, once per data source of your codes.
3. `gdp_ppp_per_capita`, `gridded_population` and `gridded_gdp_ppp`.
4. `temperature`, which also retrieves the gridded population and weather it needs.

Then [assemble the data](assemble.md).
