# Data Retrieval

The data retrieval modules are responsible for fetching and processing raw data from various public sources. The retrieved data includes electricity demand, population, weather, and socio-economic indicators. The data is processed to ensure consistency in time zones, units, and formats before being saved for further analysis and modeling.

## Overview

The data retrieval process is managed through the `retrieve.py` script located in the `demandcast/` directory. This script utilizes a configuration file to specify parameters for data retrieval, such as the type of data, countries or subdivisions of interest, time ranges, and scenarios for future projections.
The process consists of four main stages:

1. Retrieve raw data from online sources or APIs,
2. Convert raw data into structured, tabular (Parquet-compatible) formats,
3. Ensure time synchronization and unit consistency
4. Export cleaned data in Parquet or CSV format.

## Application Programming Interface (API) keys

Some modules require API keys to access data from external services. These keys should be stored in a `.env` file in the `demandcast/` directory. The `.env` file should not be included in the repository and should contain the following environment variables:

```plaintext
CDS_API_KEY=<your_key>             # For data retrieval from Copernicus CDS
ENTSOE_API_KEY=<your_key>          # For data retrieval from ENTSO-E
EIA_API_KEY=<your_key>             # For data retrieval from EIA
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
```

The script will store electricity demand data in `data/electricity_demand/YYYY-MM-DD/`, where `YYYY-MM-DD` is the date of retrieval.

#### Data source specific retrieval modules

Each retrieval module in the `demandcast/retrievals/electricity_demand_data_sources/` folder is designed to fetch electricity demand data from a specific data source. The main functions in each module typically include:

- **Redistribution rights (`redistribute`)**: Information about the redistribution rights of the data source.
- **Check input parameters (`_check_input_parameters`)**: Checks that the input parameters are valid.
- **Data request construction (`get_available_requests`)**: Builds all data requests based on the availability of the data source.
- **URL construction (`get_url`)**: Generates the appropriate web request URL.
- **Data download and processing (`download_and_extract_data_for_request`)**: Fetches the data using `utils.fetcher` functions and transforms it into a `pandas.Series`.

#### Names, codes, time zones, and data time ranges for countries and subdivisions

For each retrieval module in the `demandcast/retrievals/electricity_demand_data_sources/` folder, a corresponding YAML file must be created. The YAML file should contain a list of dictionaries, each representing a country or subdivision from the respective data source. The following rules apply:

- Names and codes should adhere to the ISO 3166 standard.
- For countries and standard subdivisions, use Alpha-3 codes.
- For non-standard subdivisions, use a widely accepted name and code.
- Data time range must be specified.
- For subdivisions, time zone must be specified.

#### Non-standard subdivisions

Some countries have subdivisions that are not standard ISO subdivisions. For these cases, the `demandcast/shapes/` folder contains scripts to generate the shapes of these subdivisions. The scripts are named after the data source (e.g., `eia.py`, `ons.py`) and contain functions to generate the shapes. The generated shapes are then used in the retrieval modules and for plotting.

### Annual electricity demand per capita

The module `demandcast/retrievals/annual_electricity_demand_per_capita.py` retrieves annual electricity demand per capita data from the World Bank and Ember for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios.

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

The module `demandcast/retrievals/population.py` retrieves total population count from the World Bank for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios. For subdivisions, the population data is calculated by aggregating gridded population data.

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
