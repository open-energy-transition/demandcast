# Data Retrieval

The data retrieval modules are responsible for fetching and processing raw data from various public sources. The retrieved data includes electricity demand, population, weather, and socio-economic indicators. The data is processed to ensure consistency in time zones, units, and formats before being saved for further analysis and modeling.

## Overview

The data retrieval process is managed through the `retrieve.py` script located in the `demandcast/` directory. This script utilizes a configuration file to specify parameters for data retrieval, such as the type of data, countries or subdivisions of interest, time ranges, and scenarios for future projections.
For the electricity demand, the data goes through four stages, each in its own folder of `data/electricity_demand/` (see [Electricity demand](#electricity-demand)):

1. `raw/`: the responses of the data sources, as they are downloaded, with every version kept;
2. `processed/`: the demand of each data source and country or subdivision, in MW at the ends of the intervals in UTC;
3. `cleaned/`: the processed demand without the values that cannot be demand, resampled to hours, with flags of the changes that need a review;
4. `combined/`: the cleaned demand of all the data sources of a country or subdivision, joined into one hourly series, which `assemble.py` reads.

The other variables are processed to the same time zone, units and formats, and saved in Parquet files.

## Application Programming Interface (API) keys

Some modules require API keys to access data from external services. These keys should be stored in a `.env` file in the `demandcast/` directory. The `.env` file should not be included in the repository and should contain the following environment variables:

```plaintext
CDS_API_KEY=<your_key>             # For data retrieval from Copernicus CDS
ENTSOE_API_KEY=<your_key>          # For data retrieval from ENTSO-E
EIA_API_KEY=<your_key>             # For data retrieval from EIA
EPIAS_USERNAME=<your_username>     # For data retrieval from EPIAS, with a free account
EPIAS_PASSWORD=<your_password>     # For data retrieval from EPIAS
ISONE_USERNAME=<your_username>     # For data retrieval from ISO New England, with a free ISO Express account
ISONE_PASSWORD=<your_password>     # For data retrieval from ISO New England
ZENODO_API_KEY=<your_key>          # For data upload to Zenodo
SANDBOX_ZENODO_API_KEY=<your_key>  # For data upload to Zenodo Sandbox
```

## Retrieving data

The script `retrieve.py` is used to download and process various types of data, including electricity demand, population, weather, and GDP data. The script accepts only the path to a configuration file:

```bash
cd demandcast
uv run retrieve.py [--config path/to/config.yaml]
```

If no config file is specified, the script uses the default `demandcast/config/retrieve_config.yaml` file. All retrieval parameters are configured in the YAML configuration file. The only required parameter is `variable`, which specifies the type of data to retrieve. Below is the description of each retrieval module and its configuration parameters.

### Electricity demand

The module `demandcast/retrievals/electricity_demand.py` downloads and processes historical electricity demand data from multiple sources such as ENTSO-E, EIA, and CCEI. The data is processed to have all timestamps in UTC and electricity demand in MW.

To run the electricity demand data retrieval:

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: electricity_demand

electricity_data_source:           # Acronym of data source (entsoe, eia, ccei, etc.) from which to retrieve data

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes for which to retrieve data

offline:                           # If true, process the raw data already downloaded again, without downloading it
```

The script stores the electricity demand data in `data/electricity_demand/`:

- `raw/<data source>/`: the responses of the website of the data source, as they are downloaded. The content of each response is kept once, under its checksum, in `files/`, and `manifest.json` lists the requests of each country or subdivision with the versions of their responses: each set of responses that a request gets, with the dates of the first and last retrievals that downloaded it. API keys and passwords are hidden, and the responses to the requests that send them in their body, such as login tickets, are not kept. The files downloaded manually that a data source reads, such as those of Eskom, NITI Aayog and NTDC, are kept in the same way, so that `offline: true` processes the files of each version even after they change or are removed. If a request fails, the responses of the requests before it are still kept, so a long retrieval that stops does not lose them, and they can be processed with `offline: true`. If the data of a request cannot be extracted from its responses, such as after a change of their format, they are kept too, with the error, so that they can be processed once the code of the data source is fixed.
- `processed/`: the demand in MW, at the ends of the intervals of the data source in UTC, without missing or zero values or duplicated times, at the resolution of the data source, in one file per country or subdivision and data source, named `<code>_<data source>.parquet`. The versions of each request are combined: the newest gives the values, and the older ones fill the times that it does not have any more, so data that a data source removes is kept. The column `Retrieved` gives the date when the version of each value was first retrieved.
- `cleaned/`: the processed demand cleaned and resampled to hourly values, which the combination reads. Each value is the average demand of its interval, and counts in each hour, at its end, for the part of its interval within the hour, so that the energy is kept. The cleaning screens the values at the resolution of the data source with statistical rules of what errors usually look like, which never bridge a gap in the data: future times, values of zero or less, values above 3 times the median of the 30 days around them (such as errors of units), the same value for 6 hours or more (stuck readings or filled data), local days, taken from the starts or from the ends of the intervals, that repeat an earlier day at the same times, to 0.01 MW (copied data), spikes, runs of values that leave the level around them by more than 20% (50% from a resolution of 30 minutes) and come back to it within 30 minutes, and drops, runs of 14 days or more below half the level of the same days of the neighbouring years, over gaps of up to 3 days without data (a part of the system left out). An hour is kept only if its values cover at least half of it. The removed values are listed by rule and period in `<code>_<data source>_removed.parquet`. The rules and their reasons are in `demandcast/cleaning/electricity_demand.py`. The changes of the cleaned demand that need a review, without removing any value, are flagged in `<code>_<data source>_flags.parquet`: a midday dip, when the demand around solar noon falls compared with the morning and afternoon below the median of the same quarter of earlier years, the sign of a demand that leaves out rooftop solar and other embedded generation, while DemandCast models the gross demand; a midday rise, when it rises suddenly above them, such as when a system operator starts to add the embedded generation; a time lag, when the daily profile of a quarter in local time is shifted by whole hours from that of the same quarter of the other years; a daylight saving error, when the daily profile in local time shifts across a change of the clocks; an annual total, when the demand of a year of a country is more than a third away from its annual demand per capita times its population; and an annual change, when the demand of a year and its ratio to its annual demand per capita times its population both change by more than 10% (20% for a subdivision) from the year before. The annual flags need the annual demand per capita and the population to be retrieved first. The flags and their reasons are in `demandcast/cleaning/flags.py`.
- `combined/`: the cleaned demand of all the data sources of each country or subdivision, joined into one hourly series, `<code>.parquet`, with the data source of each hour in the column `Source`, which `assemble.py` reads. The data sources are ranked: those whose data covers the whole area of the shape of the code first, the data of the system operators before the data that a source republishes, the gross demand before the demand whose embedded generation is unknown and the net demand (on average over the hours of each source, from the `definition` of the YAML files and the seasons whose midday dip is reviewed as net demand), and the longer data first. The ranking is of whole sources, so that the series does not switch between sources at each change of their definitions; the hours of the seasons whose flags are reviewed as errors of the source or of its reading are taken out of their source and fill, after all the sources, only the hours that no source gives. The best source gives all its hours. Each of the others fills only the hours outside them and their gaps of at least a day, and only if it gives the same quantity: over its common hours with the hours already combined, the median of its ratio to them must be within 2% of 1, and 90% of the ratios within 5% of 1. With less than 7 days of common hours, as for a source that starts after the other ends, the ratios cannot be checked, and the source fills as unverified. For example, the CCEI extends the data of Hydro-Québec into 2026, while the demand of the EIA for New England, which leaves out the solar behind the meters, does not fill the gross demand of ISO New England. `<code>_sources.parquet` lists the data sources with their rank, their common hours and ratios, the hours that they give and the decision, and `<code>_flags.parquet` the flags of the combined demand. The combination runs after the cleaning of each country or subdivision; `cleaning.combining.combine_all_data()` combines all of them again. The rules and their reasons are in `demandcast/cleaning/combining.py`.

The files that some data sources need to be downloaded manually go in `data/electricity_demand/raw/manual_downloads/`.

With `offline: true`, the script processes the raw data of the data source again, without downloading it, for example after a change of the code that processes it.

#### Gross demand

DemandCast models the gross electricity demand: the electricity consumed, whatever generation supplies it. The demand that the system operators publish is often the demand on their networks, which leaves out the part that rooftop solar and other generation embedded in the distribution networks supply. As this generation grows, the demand at midday falls more and more, and a model trained on it would learn a profile that depends on the solar installed, not on the consumers. Energy system models that represent this generation explicitly would also count it twice. See [issue #280](https://github.com/open-energy-transition/demandcast/issues/280).

DemandCast therefore:

- records what the demand of each data source counts, period by period, in the `definition` of its YAML file (see below);
- adds the embedded generation where the data source, or its system operator, publishes an estimate of it: the embedded wind and solar of NESO, the licence-exempt generation of EPIAS until 2020, the rooftop solar of AEMO in the NEM and the WEM, and the solar behind the meters of ISO New England, whose `definition` then says `added`;
- flags a midday dip in the cleaned demand, which the reviews of the flags find to be net demand where the data source leaves out this generation;
- ranks the gross demand first when it combines the data sources of a country or subdivision.

The annual electricity demand per capita, which scales the forecasts, comes from Ember first, whose demand is the electricity supplied, with the generation of the consumers (see [Annual electricity demand per capita](#annual-electricity-demand-per-capita)).

#### Data source specific retrieval modules

Each retrieval module in the `demandcast/retrievals/electricity_demand_data_sources/` folder is designed to fetch electricity demand data from a specific data source. The main functions in each module typically include:

- **Data request construction (`get_available_requests`)**: Builds the requests of a country or subdivision from its code and the dates of its data in the YAML file, which the retrieval code passes, in chronological order. A source that downloads all its data at once returns a single request, `None`.
- **URL construction (`get_url`)**: An optional helper that builds the URL of a request, with the parameters that fit the source.
- **Data download and processing (`download_and_extract_data_for_request`)**: Fetches the data of a request, which the retrieval code passes with the code, using the helpers of `utils.fetcher` such as `fetch_dataframe` and `read_manual_files`, and transforms it into a `pandas.Series` of the demand in MW, with time-zone-aware times that mark the end of each interval. `utils.time_series.localize_interval_starts` moves the starts of intervals in local time to their ends.

The periods of the requests come from `utils.time_series.split_period`, and API keys from `utils.config.read_api_key`.

#### Names, codes, time zones, and data time ranges for countries and subdivisions

For each retrieval module in the `demandcast/retrievals/electricity_demand_data_sources/` folder, a corresponding YAML file must be created. It gives the `licence` of the data (`redistribute`, whether the data can be published on Zenodo, whose dataset of actual data has the CC BY-NC 4.0 licence, `terms`, a summary of the licence, and `url`, its link), its `definition`, and its `entities`, a list of dictionaries, each representing a country or subdivision from the respective data source. The following rules apply:

The `definition` says what the demand of the data source counts, since DemandCast models the gross demand, with the demand that the generation embedded in the distribution networks supplies. It is a list of periods, in the order of their `start_date`, the first one from the start of the data, each with the `quantity` that the source gives, and whether the `embedded_generation` (such as rooftop solar), the `network_losses`, the `storage_charging` and the `power_plant_use` are `included` by the source, `added` by DemandCast from an estimate, `excluded`, or `unknown`, with a `note` on the reasons. For example, the total demand of AEMO for the NEM leaves out the rooftop solar until 2016, and has AEMO's estimate of it added from 2017. `utils.entities.get_definition(data_source, date)` gives the period of a date.

A data source that republishes the data of the system operators, such as the EIA, the CCEI and ENTSO-E, has `compiled: true`, and a country or subdivision whose data covers only part of the area of its shape has `same_area: false`, such as CAISO for California, whose shape is the region of the EIA. The combination uses them to rank the data sources of a code.

- Names and codes should adhere to the ISO 3166 standard.
- For countries and standard subdivisions, use Alpha-3 codes.
- For non-standard subdivisions, use a widely accepted name and code.
- Data time range must be specified.
- For subdivisions, time zone must be specified.

#### Non-standard subdivisions

Some countries have subdivisions that are not standard ISO subdivisions. For these cases, the `demandcast/shapes/` folder contains scripts to generate the shapes of these subdivisions. The scripts are named after the data source (e.g., `eia.py`, `ons.py`) and contain functions to generate the shapes. The generated shapes are then used in the retrieval modules and for plotting.

#### Live check of the data sources

The websites of the data sources change their addresses, formats and access rules, and some stop publishing. The tests cannot notice it, because they read synthetic files. The live check downloads one request per data source over the network and checks the result. To run it, in the `demandcast` folder:

```bash
uv run check.py --config config/check_data_sources_config.yaml
```

For each data source that is downloaded automatically, the check downloads the latest request of the first country or subdivision of its YAML file. A data source fails if the download or the parsing fails, or if:

- the values are not numbers, or some are negative;
- the times have no time zone, or are mostly more than one hour apart;
- the latest value is more than `maximum_age_days` old (60 by default), for a data source whose `end_date` is `today`;
- there are data after the `end_date` of the YAML file, which is then out of date.

The data sources read from manually downloaded files are skipped, ENTSO-E and EIA need their API keys, and EPIAS and ISO New England their accounts. The results are saved to `checks/data_sources_report.md` and `checks/data_sources_report.json`. In the configuration file, `data_sources` limits the check to some data sources, `maximum_age_days_by_source` gives more days to the data sources that publish later, and `time_limit_minutes` is the time after which the data sources that have not answered fail.

#### Report of the flags

The cleaning flags the changes of the cleaned demand that need a review, in `<code>_<data source>_flags.parquet` next to the cleaned data. The report gathers the flags of all the countries, subdivisions and data sources, in the `demandcast` folder:

```bash
uv run check.py --config config/check_flags_config.yaml
```

It compares them with the reviews in `checks/reviewed_flags.yaml`, which give a data source, a code, a flag, the periods that they review (all of them if not given), a verdict (`source_error`, `reading_error`, `definition_change`, `net_demand`, `real_event` or `false_positive`) and a note. The report, `checks/flags_report.md` and `checks/flags_report.csv`, lists the flags not reviewed, those reviewed with their verdicts, and the reviews that match no flag any more, such as those of errors that have been fixed. After a retrieval, the flags not reviewed are the ones to look at, and their reviews are added to the file.

The flags of the combined demand have the data source `combined`, and their own section in the report. A combined flag takes the review with the data source `combined`, if there is one, and otherwise, if its main source, the data source of most of the hours of the flagged period, has the same flag in the same period, the review of that flag: a flag that comes from the data of a source is reviewed once. Only the flags that come from the combination, which the main source does not have, such as a step where a data source fills the hours after another, need a review of their own.

The report also counts the checks that each data source has failed in a row, from the report of the previous check in the same folder. On GitHub, the `Live check` workflow runs the check every Monday, with the API keys of the `live-checks` environment, and writes the report to the summary of its run. It keeps one issue open, labelled `live-check`, with the data sources that fail two checks in a row, since a website can be out of reach for a while, and closes it when no data source does.

### Annual electricity demand per capita

The module `demandcast/retrievals/annual_electricity_demand_per_capita.py` retrieves annual electricity demand per capita data from Ember and the World Bank for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios.

The demand of Ember is the electricity generated and imported, less the exports: the electricity supplied, with the losses of the networks and with the generation that is not on the networks of the system operators, such as rooftop solar and the plants of industries for their own use. The electric power consumption of the World Bank is the consumption of the consumers, without the losses of the networks and the own use of the power plants, about 12% lower in the median country. The hourly demand of the system operators includes the losses of their networks but not the generation off them: its yearly demand is 0.94 times that of Ember and 1.05 times that of the World Bank in the median national series, and gets closer to Ember as embedded generation is added for the gross demand. Ember gives the historical values, and the World Bank fills the countries and years that Ember does not have (before 2000, and about 46 countries), times the ratio of Ember to the World Bank of the country in the years that both have, or the median of these ratios. The future scenarios apply the growth rates of the final energy of electricity per capita of the IAMC database to the last historical value, which assumes that the share of the losses stays the same.

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: annual_electricity_demand_per_capita

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # SSP scenario (e.g., SSP2-Baseline) for which to retrieve projected data
```

The script will store annual electricity demand per capita data in `data/annual_electricity_demand_per_capita/`.


### Population

The module `demandcast/retrievals/population.py` retrieves total population count from the World Bank for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios. For subdivisions, the population data is calculated by aggregating gridded population data. The gridded data of the past (Gridded Population of the World, version 4.11) ends in 2020, so a subdivision grows after 2020 as its country does in the data of the World Bank, until the last year of the country.

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: population

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes  for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # SSP scenario (e.g., SSP2) for which to retrieve projected data
```

The script will store population data in `data/population/`.

### Gridded population

The module `demandcast/retrievals/gridded_population.py` retrieves gridded population density data from the Socioeconomic Data and Applications Center (SEDAC) for the historical period and gridded population count from a Figshare repository for future scenarios. From the global gridded population at 30-arcsecond resolution, the module calculates when necessary the population count from the density, aggregates to 0.25° resolution to match the weather data, and extracts subsets of gridded population count for the countries and subdivisions of interest.

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: gridded_population

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes  for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # SSP scenario (e.g., SSP2) for which to retrieve projected data
```

The script will store gridded population data in `data/gridded_population/`.

### Gross Domestic Product (GDP), Purchasing Power Parity (PPP) per capita

The module `demandcast/retrievals/gdp_ppp_per_capita.py` retrieves country-level GDP, PPP per capita data from the World Bank and the International Monetary Fund (IMF) for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios.

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: gdp_ppp_per_capita

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes  for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # SSP scenario (e.g., SSP2) for which to retrieve projected data
```

The script will store GDP, PPP per capita data in `data/gdp_ppp_per_capita/`.

### Gridded GDP PPP

The module `demandcast/retrievals/gridded_gdp_ppp.py` retrieves gridded GDP, PPP data from a Zenodo repository for both the historical period and future scenarios. From the global gridded GDP, PPP at 0.25° resolution, the module extracts subsets of gridded GDP, PPP for the countries and subdivisions of interest.

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: gridded_gdp_ppp

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes  for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # SSP scenario (e.g., SSP2) for which to retrieve projected data
```

### Gridded weather

The module `demandcast/retrievals/gridded_weather.py` retrieves gridded weather data from the Copernicus Climate Data Store (CDS). The weather data is stored in NetCDF format for each country and subdivision of interest.

To retrieve weather data from the Copernicus Climate Data Store (CDS), first ensure that you are registered on the website and have your API key stored in the `.env` file. Instructions for the API key can be found [here](https://cds.climate.copernicus.eu/how-to-api). Then run:

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: gridded_weather

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes  for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # Climate model scenario (e.g., SSP2-4.5) for which to retrieve projected data

weather_variable: temperature      # Weather variable (currently only temperature supported)

climate_model:                     # Climate model (e.g., CESM2)
```

The script will store weather data in `data/gridded_weather/`. Note that the size of weather data files is on the order of 100 MB per country per year, so ensure you have sufficient storage space.

### Temperature

The module `demandcast/retrievals/temperature.py` extracts temperature time series from the gridded weather data based on population count. It uses both the gridded weather data and the gridded population data to identify the most populated areas and extract temperature time series for those areas.

```bash
cd demandcast
uv run retrieve.py
```

**Configuration variables** (`retrieve_config.yaml`):

```yaml
variable: temperature

code:                              # ISO Alpha-3 code (e.g., FRA) or subdivision (e.g., USA_CAL) for which to retrieve data

file:                              # Path to YAML file with list of codes  for which to retrieve data

year:                              # Specific year to retrieve

start_year:                        # Start year of a range

end_year:                          # End year of a range (inclusive)

scenario:                          # Climate model scenario (e.g., SSP2-4.5) for which to retrieve projected data

weather_variable: temperature      # Weather variable (currently only temperature supported)

climate_model:                     # Climate model (e.g., CESM2)
```

The script will store temperature data in `data/temperature/`.
