# Retrieve data

`retrieve.py` downloads one kind of data for the countries and subdivisions you choose, and saves it under the data folder. Use this page to run a retrieval, pick its options, set up your API keys, and understand what lands on disk.

## Run a retrieval

Each run retrieves one **variable** (one kind of data). Set the options in `config/retrieve_config.yaml`, or in another YAML file that you pass with `--config`:

```bash
cd demandcast
uv run retrieve.py
uv run retrieve.py --config config/my_retrieval.yaml
```

The script checks the options before it starts. A misspelt option, a data source or scenario that does not exist, or a missing required option stops it with an error that lists the valid values.

A minimal file that retrieves the electricity demand of France from ENTSO-E:

```yaml
variable: electricity_demand
electricity_data_source: entsoe
code: FRA_CONTINENTAL
```

## Variables

| `variable` | What it retrieves | Saved in (under the data folder) |
|---|---|---|
| `electricity_demand` | Hourly or sub-hourly demand of one data source, then cleaned and combined with the other sources | `electricity_demand/` (see [below](#electricity-demand)) |
| `annual_electricity_demand_per_capita` | Yearly demand per person: Ember and World Bank history, IIASA projections | `annual_electricity_demand_per_capita/` |
| `population` | Population: World Bank history, IIASA projections | `population/` |
| `gridded_population` | Population on a 0.25° grid | `gridded_population/` |
| `gdp_ppp_per_capita` | GDP at purchasing power parity per person | `gdp_ppp_per_capita/` |
| `gridded_gdp_ppp` | GDP PPP on a 0.25° grid | `gridded_gdp_ppp/` |
| `gridded_weather` | ERA5 reanalysis or climate model projections on a grid | `gridded_weather/` |
| `temperature` | Hourly temperature of the most populous grid cells | `temperature/` |

The data folder is `demandcast/data/`, unless the environment variable `DEMANDCAST_DATA_FOLDER` names another folder (see [the data folder](../reference/data-folder.md)). The sources, units and processing of the variables other than electricity demand are explained in [Weather and socio-economic inputs](../concepts/inputs.md).

## Options

Every option of `retrieve.py`. "Default" is the value used when the option is missing or empty. The shipped `config/retrieve_config.yaml` sets `variable: electricity_demand`, `electricity_data_source: entsoe` and `weather_variable: temperature`.

| Option | Required? | Default | Applies to | What it does |
|---|---|---|---|---|
| `variable` | Yes | – | all | The variable to retrieve, from the table above. |
| `electricity_data_source` | For `electricity_demand` | none | `electricity_demand` | The data source: the name of its YAML file, such as `entsoe` or `eia` (case-sensitive). See [Data sources](../reference/data-sources.md). |
| `code` | No | none | all | One country or subdivision, such as `FRA` or `USA_CAL`. Wins over `file`. |
| `file` | No | none | all | Path to a YAML file listing several countries and subdivisions (see [Codes file](#codes-file)). Relative paths start from the folder you run the script in. |
| `year` | No | none | all but `electricity_demand` | One year. Cannot be combined with `start_year` or `end_year`. |
| `start_year` | No | none | all but `electricity_demand` | First year of a range. Needs `end_year`. |
| `end_year` | No | none | all but `electricity_demand` | Last year of a range, included. Needs `start_year`. |
| `scenario` | No | all scenarios | all but `electricity_demand` | One scenario of the projections, in any case (see [Years, scenarios and climate models](#years-scenarios-and-climate-models)). An error for `electricity_demand`. |
| `weather_variable` | For `gridded_weather` | none | `gridded_weather` | The weather variable. Only `temperature` exists. |
| `climate_model` | No | all models | `gridded_weather`, `temperature` | One climate model for the future years, in any case, such as `CESM2`. |
| `reanalysis_source` | No | `points` | `gridded_weather`, `temperature` | Where the past weather (ERA5) comes from: `points`, `cds` or `arco` (see below). |
| `offline` | No | `false` | `electricity_demand` | If `true`, process the raw data already downloaded again, without the network. |
| `latest_requests` | No | none (all) | `electricity_demand` | If set to a number of 1 or more, download only that many of the latest requests of each code, plus the requests never downloaded. |

!!! warning
    An option that does not apply to the variable is ignored without a warning, for example `year` with `electricity_demand` or `climate_model` with `population`. Only `scenario` with `electricity_demand` stops with an error.

`reanalysis_source` values:

| Value | Source | Notes |
|---|---|---|
| `points` | The ERA5 hourly time series of single points on the Copernicus Climate Data Store (CDS) | Only for `temperature`. A few MB for all years. With `gridded_weather`, `points` means `cds`. |
| `cds` | The ERA5 grids of the CDS | Requests wait in a queue, from minutes to hours. About 5 GB a year for all codes. |
| `arco` | ARCO-ERA5 on Google Cloud | No account and no queue. Same values as the CDS. |

The projections of the climate models always come from the CDS.

## Choose countries and subdivisions

Each country or subdivision is an **entity**, named by its **code** (see the [glossary](../concepts/glossary.md#entity)): the ISO alpha-3 code of a country, such as `FRA`, or the country code and a subdivision code joined by an underscore, such as `USA_CAL`.

The script picks the codes in this order:

1. `code`: only this code. If it does not have the data, the script stops and lists the valid codes.
2. `file`: the codes of the file. Codes without the data are logged as errors and skipped. If none is left, the script stops.
3. Neither: all the codes that have the data.

"Have the data" depends on the variable:

- `electricity_demand`: the codes in the YAML file of the data source.
- All other variables: the codes with historical population, electricity demand per capita and GDP PPP per capita in `checks/data_availability_summary.csv`. A code with only the electricity demand per capita also counts if its area is over 500 km², because its population and GDP PPP per capita are then estimated from the gridded data. `check.py` writes this file (see [Run the checks](check.md)).

Some codes, such as Kosovo (`XKX`), have historical data but no IIASA projections. Their population, GDP PPP per capita and electricity demand per capita get only the historical years: they are used for training, but not forecast for future scenarios.

### Codes file

A codes file is a YAML file with a list of `entities`. The script reads only `country_code`, and `subdivision_code` for a subdivision; other keys, such as `country_name`, are allowed and help readers.

```yaml
entities:
  - country_name: France
    country_code: FRA
  - country_name: Germany
    country_code: DEU
  - country_name: United States
    country_code: USA
    subdivision_code: CAL
```

The YAML files of the data sources and `config/available_subdivisions.yaml` use the same format, so you can pass them as `file` too.

## Years, scenarios and climate models

These options apply to all variables except `electricity_demand`, whose dates come from the YAML file of its data source.

- With no year option, the script retrieves every available year, past and future up to 2100.
- `year` must be an available year, or the run fails.
- `start_year` and `end_year` keep the available years between them. A bound outside the available years only logs a warning.

The available years and scenarios differ by variable:

| Variable | Past years | Future years | `scenario` values |
|---|---|---|---|
| `population`, `gdp_ppp_per_capita` | The years of the World Bank (and IMF) data, extended to last year | Up to 2100 | SSP: `SSP1` to `SSP5` |
| `annual_electricity_demand_per_capita` | The years of the Ember or World Bank data, up to the last year with data (not extended) | From the year after the last year with data, up to 2100 | IAMC, such as `SSP2-45` or `SSP2-Baseline` |
| `gridded_population` | 2000 to 2020, every 5 years | 2025 to 2100, every 5 years | SSP |
| `gridded_gdp_ppp` | 2000 to 2020 | 2025 to 2100, every 5 years | SSP |
| `gridded_weather`, `temperature` | 1990 to last year (ERA5) | This year to 2100 (climate models) | CMIP6, such as `SSP2-4.5` |

A past year has no scenario. A future year is retrieved for each scenario, or only for `scenario` if you set it. For the weather, it is retrieved for each climate model and each of its scenarios, or only for `climate_model`. The models are `CAMS-CSM1-0`, `CESM2`, `CNRM-ESM2-1`, `EC-Earth3-Veg-LR`, `HadGEM3-GC31-LL`, `MIROC-ES2L` and `MPI-ESM1-2-LR`; [Weather and socio-economic inputs](../concepts/inputs.md) lists their scenarios.

!!! warning
    Without `climate_model`, a `scenario` must exist for every model. Only `SSP1-2.6`, `SSP2-4.5` and `SSP5-8.5` do. `SSP3-7.0` alone, for example, fails because `HadGEM3-GC31-LL` does not have it: set `climate_model` too.

!!! tip
    Always set the years for `gridded_weather` and `temperature`. Without them, the script retrieves every year from 1990 to 2100 for every model and scenario.

## API keys and accounts

Some sources need a key or an account. Put them in `demandcast/.env`, one `NAME=value` per line, and never commit this file. A variable already set in your shell wins over the file.

| Variable | Needed for | How to get it |
|---|---|---|
| `CDS_API_KEY` | `gridded_weather` and `temperature` with `points` or `cds`, and all climate projections | Free account on the [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/how-to-api) |
| `EMBER_API_KEY` | `annual_electricity_demand_per_capita` | Free key from Ember |
| `ENTSOE_API_KEY` | `electricity_data_source: entsoe` | Free account on the ENTSO-E Transparency Platform |
| `EIA_API_KEY` | `electricity_data_source: eia` | Free key from the US EIA |
| `EPIAS_USERNAME`, `EPIAS_PASSWORD` | `electricity_data_source: epias` | Free account of the EPIAS transparency platform |
| `ISONE_USERNAME`, `ISONE_PASSWORD` | `electricity_data_source: isone` | Free ISO Express account of ISO New England |

`ZENODO_API_KEY` and `SANDBOX_ZENODO_API_KEY` are for `publish.py` only (see [Publish](publish.md)). The values of every variable whose name ends in `_API_KEY` or `_PASSWORD` are replaced by `***` in the download errors, in the errors of failed codes and in the saved raw data.

!!! note
    `offline: true` still needs the key or account of ENTSO-E, the EIA, EPIAS or ISO New England to be set, because their code reads it before it asks for the saved responses.

## Electricity demand

A retrieval of `electricity_demand` runs these steps for each code of the data source:

1. Split the dates of the code into **requests**, such as one year or one month each. The dates come from the YAML file of the source; an end date of `today` means five days ago.
2. Download each request and save the raw responses (see [Raw data and versions](#raw-data-and-versions)).
3. Process all saved versions into MW at the ends of the intervals in UTC, and keep only the dates of the code in the YAML file.
4. Clean the processed data, flag the changes that need a review, and combine all the sources of the code into one hourly series.

Each stage has its own folder in `electricity_demand/`:

| Folder | What it holds |
|---|---|
| `raw/<data source>/` | The responses of the website, as downloaded: `manifest.json` and `files/` |
| `raw/manual_downloads/` | The files that you download by hand |
| `processed/` | `<code>_<data source>.parquet`: the demand in MW (`Load (MW)`) at the ends of the intervals in UTC (`Time (UTC)`), at the resolution of the source, without missing or zero values or repeated times; `Retrieved` gives when the version of each value was first downloaded |
| `cleaned/` | The hourly cleaned demand of each code and source, its removed values and its flags |
| `combined/` | `<code>.parquet`: one hourly series per code from all its sources, which `assemble.py` reads |

[Electricity demand](../concepts/electricity-demand.md) explains the cleaning, the flags and the combination, with the files and columns of `cleaned/` and `combined/`.

!!! tip
    Retrieve `annual_electricity_demand_per_capita` and `population` for a code before its electricity demand. The cleaning uses them to flag years whose total demand looks wrong; without them, it skips this check. You can add it later with `offline: true`.

### Raw data and versions

DemandCast keeps every response that a data source sends, so you can process the data again without the network, and data that a source later changes or deletes is not lost.

- `raw/<data source>/files/<checksum>` holds the content of each response, saved once under its SHA-256 checksum.
- `raw/<data source>/manifest.json` lists, for each code, its `requests`. Each request has its `versions`: a version is one set of responses, with `first_retrieved` and `last_retrieved` (UTC times of the first and last retrievals that got it), its `responses` (method, URL and body checksum, status, headers and the file of each), and an `error` if its data could not be read.

When a request returns the same responses as its latest version, only `last_retrieved` changes. Different responses make a new version. When the data is processed:

- the newest version of each request gives the values, and older versions fill the times that it no longer has;
- where requests overlap, the newest version of any of them wins;
- an older version whose values the new download has too, unchanged, is deleted with its files, so a request of the current period does not keep a copy at every retrieval.

API keys and passwords are hidden in the manifest. The responses of requests that send a password in their body, such as the login of EPIAS, are not saved.

### Process again without downloading (`offline`)

With `offline: true`, the script reads the saved versions of each code instead of downloading them, then saves, cleans, flags and combines as usual. Use it after a change to the code of a data source, its YAML file or the cleaning. A code without raw data logs a warning and is skipped. `offline` wins over `latest_requests`.

### Download only the latest requests (`latest_requests`)

Without `latest_requests`, every request is downloaded again, which also picks up the corrections that a source makes to old data. With `latest_requests: N`, the script downloads:

- the last `N` requests of each code, whose data can still change; and
- every earlier request that has no version yet, such as a new year or a request that returned no data last time.

The other requests are processed from the raw data.

### Files downloaded by hand

Some sources have no download that can be automated: you download their files from the website and put them in `electricity_demand/raw/manual_downloads/`. Each source reads the files whose names start with its prefix; [Data sources](../reference/data-sources.md) gives the prefixes. If no file matches, the error tells you where to download from and how to name the file.

Keep earlier downloads next to later ones. Where several files have the same hour, the hour takes the value of the file whose data ends last (the latest download), so revised values win. Earlier files keep the hours that later ones no longer have. The raw data also saves a copy of each file it reads, so `offline: true` still works after you delete or replace them.

### What happens when a request fails

- Temporary errors (timeouts, lost connections, HTTP 408, 425, 429 and 5xx) are retried, by default 5 times, 5 seconds apart.
- If the last request of a code is not found (HTTP 404 or 410), it is skipped with a warning, because the file of the latest period may not be published yet. An earlier request, or the only one, that is not found is an error.
- A request that returns no data gets no version, so the next retrieval with `latest_requests` downloads it again.
- When a request fails, the responses of the requests before it stay in the raw data, so a long retrieval does not lose them.
- If the responses arrived but their data cannot be read, such as after a change of the file format, they are saved with the error. Once the code of the source is fixed, `offline: true` processes them.

## When a code fails

For all variables, a retrieval of several codes goes on after a code that fails. The log gives the error of that code, with keys and passwords hidden and without its traceback. At the end, the script stops with an error that lists the failed codes. Retrieve one of them alone, with `code`, to see the full traceback.

A retrieval of a single code stops at its first error. An error before the loop over the codes, such as a failed download of a global dataset, stops the whole run.

## Logs

Each run writes a new log file in `logs/` under the data folder, named `retrieval_of_<variable>_<YYYYMMDD_HHMMSS>.log`, or `retrieval_of_electricity_demand_from_<data source>_<YYYYMMDD_HHMMSS>.log`, in local time. It starts with the validated options and holds every message of level INFO and above. The messages go only to this file: the terminal shows the progress bars and the final error, if any.

## Non-standard subdivisions

Most subdivisions are standard ISO 3166-2 subdivisions, such as US states, whose shapes come from [Natural Earth](https://www.naturalearthdata.com/). Some data measures another area, such as a grid region or a mainland system: for example `FRA_CONTINENTAL`, France without Corsica. These are **non-standard subdivisions, defined by the standard subdivisions that make them up**.

- `demandcast/shapes/subdivisions/<ISO3>.yaml` defines those of one country. Each has a `name` and its `standard_subdivisions` (ISO 3166-2 codes of Natural Earth at 1:10m). Optional `cuts` remove parts of some of them, as WKT polygons, such as isolated systems that the grid does not reach. Examples: `AUS_QLD1` (Queensland without its north-west and Cape York), `BRA_N` (six states of Brazil, without most of Amazonas), `JPN_Kantō` (Kantō and Yamanashi, with Shizuoka east of the Fuji River).
- `demandcast/shapes/eia.py` writes the regions of the EIA to `USA.yaml`, keeping the other subdivisions of the file. Each US county goes to the region with the most retail sales in it, from EIA-861. Where that region leads by less than 15% of the sales, and in Texas, the county follows the zones of Electricity Maps. Run it again for each new year of EIA-861, after changing `EIA861_YEAR` in the script: `uv run shapes/eia.py`.
- When the area that a source measures changes, such as when isolated systems join a grid, each period is a separate subdivision named after its first year, drawn as the area was then. For example, the North subsystem of Brazil is `BRA_N-2000`, `BRA_N-2013`, `BRA_N-2015` and, from 2025, `BRA_N`. The periods start on 1 January.

Each grid of population, GDP PPP and weather covers the bounds of the shape of its code, and its NetCDF file records them. If a shape changes and its bounds move, such as after a new run of `eia.py` or a new version of Natural Earth, the next retrieval extracts the grids of that code again, and downloads again the weather downloaded for that code alone.

## Recommended order

To retrieve everything for a new set of codes:

1. `population` and `annual_electricity_demand_per_capita`, so the cleaning can check the annual demand.
2. `electricity_demand`, once per data source of your codes.
3. `gdp_ppp_per_capita`, `gridded_population` and `gridded_gdp_ppp`.
4. `temperature` (it also retrieves the gridded population it needs).

Then [assemble the data](assemble.md).
