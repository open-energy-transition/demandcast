# Extract Transform Load (ETL)

ETL contains all scripts related to the extraction, transformation, and loading of electricity demand, population, weather, and GDP data. It is designed to provide a standardized pipeline to prepare data for downstream modeling and analysis.

## Overview

The ETL process consists of four main stages:

<h3>1. Fetch the data</h3>

Retrieve raw data from online sources or APIs.

<h3>2. Transform into tabular format</h3>

Convert raw data into structured, tabular (Parquet-compatible) formats.

<h3>3. Data cleaning</h3>

Ensure time synchronization and unit consistency.

<h3>4. Save processed data</h3>

Export cleaned data to local or cloud storage in Parquet or CSV format.

## Structure

```bash
ETL/
├── figures/                        # Modules to plot figures and resulting figures
├── retrieval/                      # Modules to retrieve data from various sources
├── shapes/                         # Scripts to generate shapes for non-standard subdivisions and resulting shapefiles
├── tests/                          # Unit tests for the ETL utilities and retrieval scripts
├── utils/                          # Shared utilities for data fetching, processing, and uploading
├── .dockerignore                   # Files and directories to ignore in Docker build context
├── .env                            # API keys (not included in repo)
├── .python-version                 # Python version for the environment
├── Dockerfile                      # Dockerfile to create an image for the ETL module
├── README.md                       # Overview of the ETL module
├── plot.py                         # Script to generate plots for the data
├── pyproject.toml                  # Project configuration and dependencies
├── retrieve.py                     # Main script to download and process data
├── run_all.sh                      # Shell script to run all ETL processes sequentially
└── uv.lock                         # Locked dependencies for the project
```

## Application Programming Interface (API) keys

Some modules require API keys to access data from external services. These keys should be stored in a `.env` file in the `ETL/` directory. The `.env` file should not be included in the repository and should contain the following environment variables:

```plaintext
CDS_API_KEY=<your_key>             # For data retrieval from Copernicus CDS
ENTSOE_API_KEY=<your_key>          # For data retrieval from ENTSO-E
EIA_API_KEY=<your_key>             # For data retrieval from EIA
ZENODO_API_KEY=<your_key>          # For data upload to Zenodo
SANDBOX_ZENODO_API_KEY=<your_key>  # For data upload to Zenodo Sandbox
```

## Main script for downloading and processing data

The main script `retrieve.py` is used to download and process various types of data, including electricity demand, population, weather, and GDP data. The script can be run with the following command:

```bash
uv run retrieve.py <data_type> [arguments]
```

### Electricity demand

The module `retrievals/electricity_demand.py` downloads and process historical electricity demand data from multiple sources such as ENTSO-E, EIA, and CCEI. The data is processed to have all timestamps in UTC and electricity demand in MW.

To run the electricity demand data retrieval, use the following command:

```bash
uv run retrieve.py electricity_demand [-d data_source>] [-c country_or_subdivision_code] [-f path_to_file_with_codes] [-g bucket_name] [-z] [-p]
```

Arguments:

- `-d data_source`: (Required) The acronym of the data source as defined in the retrieval modules (e.g., `entsoe`).
- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-ug, --upload_to_gcs`: (Optional) The bucket name of the Google Cloud Storage (GCS) to upload the data.
- `-uz, --upload_to_zenodo`: (Optional) If set, the script will upload the data to a new or existing Zenodo record.
- `-pz, --publish_to_zenodo`: (Optional) If set, the script will publish the Zenodo record after uploading.
- `-mo, --made_by_oet`: (Required if uploading to Zenodo) If set, the script will indicate that the data on the Zenodo record was retrieved and uploaded by Open Energy Transition.

For exampl, you can download electricity data for France from ENTSO-E using:

```bash
uv run retrieve.py electricity_demand entsoe -c FR
```

#### Data source specific retrieval modules

Each retrieval module in the `retrieval/electricity_demand_data_sources/` folder is designed to fetch electricity demand data from a specific data source. The main functions in each module typically include:

- **Redistribution rights (`redistribute`)**: Information about the redistribution rights of the data source.
- **Check input parameters (`_check_input_parameters`)**: Checks that the input parameters are valid.
- **Data request construction (`get_available_requests`)**: Builds all data requests based on the availability of the data source.
- **URL construction (`get_url`)**: Generates the appropriate web request URL.
- **Data download and processing (`download_and_extract_data_for_request`)**: Fetches the data using `utils.fetcher` functions and transforms it into a `pandas.Series`.

#### Names, codes, time zones, and data time ranges for countries and subdivisions

For each retrieval module in the `retrieval/electricity_demand_data_sources/` folder, a corresponding YAML file must be created. The YAML file should contain a list of dictionaries, each representing a country or subdivision from the respective data source. The following rules apply:

- Names and codes should adhere to the ISO 3166 standard.
- For countries and standard subdivisions, use alpha-2 codes.
- For non-standard subdivisions, use a widely accepted name and code.
- Data time range must be specified.
- For subdivisions, time zone must be specified.

#### Non-standard subdivisions

Some countries have subdivisions that are not standard ISO subdivisions. For these cases, the `shapes/` folder contains scripts to generate the shapes of these subdivisions. The scripts are named after the data source (e.g., `eia.py`, `ons.py`) and contain functions to generate the shapes. The generated shapes are then used in the retrieval modules and for plotting.

### Annual electricity demand per capita

The module `retrievals/annual_electricity_demand_per_capita.py` retrieves annual electricity demand per capita data from the World Bank and Ember for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios. The annual electricity demand per capita data is saved into CSV and Parquet files.

```bash
uv run retrieve.py annual_electricity_demand_per_capita [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the annual electricity demand data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the annual electricity demand data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the annual electricity demand data to be downloaded (inclusive).
- `-s, --scenario`: (Optional) The scenario of the annual electricity demand data to be downloaded (e.g., `SSP2-26`).

The script will store annual electricity demand per capita data in `data/annual_electricity_demand_per_capita/`.


### Population

The module `retrievals/population.py` retrieves total poulation count from the World Bank for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios. For subdivisions, the population data is calculated by aggregating gridded population data. The population data is saved into CSV and Parquet files.

```bash
uv run retrieve.py population [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the population data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the population data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the population data to be downloaded (inclusive).
- `-s, --scenario`: (Optional) The scenario of the population data to be downloaded (e.g., `SSP2`).

The script will store population data in `data/population/`.

### Gridded population

The module `retrievals/gridded_population.py` retrieves gridded population density data from the Socioeconomic Data and Applications Center (SEDAC) for the historical period and gridded population count from a Figshare repository for future scenarios. Form the global gridded population at 30-arcsecond resolution, the module calculates when necessary the population count from the density, aggregates to 0.25° resolution to match the weather data, and extracts subsets of gridded population count for the countries and subdivisions of interest.

```bash
uv run retrieve.py gridded_population [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the population density data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the population density data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the population density data to be downloaded (inclusive).
- `-s, --scenario`: (Optional) The scenario of the population density data to be downloaded (e.g., `SSP2`).

The script will store gridded population data in `data/gridded_population/`.

### Gross Domestic Product (GDP), Purchasing Power Parity (PPP) per capita

The module `retrievals/gdp_ppp_per_capita.py` retrieves country-level GDP, PPP per capita data from the World Bank and the International Monetary Fund (IMF) for the historical period and from the Integrated Assessment Modeling Consortium (IAMC) database for different future scenarios. The GDP, PPP per capita data is saved into CSV and Parquet files.

```bash
uv run retrieve.py gdp_ppp_per_capita [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the GDP, PPP per capita data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the GDP, PPP per capita data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the GDP, PPP per capita data to be downloaded (inclusive).
- `-s, --scenario`: (Optional) The scenario of the GDP, PPP per capita data to be downloaded (e.g., `SSP2`).

The script will store GDP, PPP per capita data in `data/gdp_ppp_per_capita/`.

### Gridded GDP PPP

The module `retrievals/gridded_gdp_ppp.py` retrieves gridded GDP, PPP data from a Zenodo repository for both the historical period and future scenarios. From the global gridded GDP, PPP at 0.25° resolution, the module extracts subsets of gridded GDP, PPP for the countries and subdivisions of interest.

```bash
uv run retrieve.py gridded_gdp_ppp [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the GDP, PPP data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the GDP, PPP data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the GDP, PPP data to be downloaded (inclusive).
- `-s, --scenario`: (Optional) The scenario of the GDP, PPP data to be downloaded (e.g., `SSP2`).

### Gridded weather

The module `retrievals/gridded_weather.py` retrieves gridded weather data from the Copernicus Climate Data Store (CDS). The weather data is stored in NetCDF format for each country and subdivision of interest.

To retrieve weather data from the Copernicus Climate Data Store (CDS), first ensure that you are registered on the website and have your API key stored in the `.env` file. Instructions for the API key can be found [here](https://cds.climate.copernicus.eu/how-to-api). Then run:

```bash
uv run retrieve.py gridded_weather [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-v variable] [-m model] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the weather data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the weather data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the weather data to be downloaded (inclusive).
- `-v, --variable`: (Optional) The weather variable to be downloaded (only `temperature` is currently supported).
- `-m, --model`: (Optional) The climate model to be used for future scenarios (e.g., `CESM2`).
- `-s, --scenario`: (Optional) The scenario of the weather data to be downloaded (e.g., `SSP2-4.5`).

The script will store weather data in `data/weather/`. Note that the size of weather data files is on the order of 100 MB per country per year, so ensure you have sufficient storage space.

### Temperature

The module `retrievals/temperature.py` extracts temperature time series from the gridded weather data based on population count. It uses both the gridded weather data and the gridded population data to identify the most populated areas and extract temperature time series for those areas. The temperature time series is saved into CSV and Parquet files.

```bash
uv run retrieve.py temperature [-c country_or_subdivision_code] [-f code_file] [-y year] [-sy start_year] [-ey end_year] [-s model] [-s scenario]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the temperature data to be downloaded.
- `-sy, --start_year`: (Optional) The start year of the temperature data to be downloaded.
- `-ey, --end_year`: (Optional) The end year of the temperature data to be downloaded (inclusive).
- `-m, --model`: (Optional) The climate model used for the weather data (e.g., `CESM2`).
- `-s, --scenario`: (Optional) The scenario of the weather data used to extract temperature (e.g., `SSP2-4.5`).

The script will store temperature data in `data/temperature/`.

## Main script for plotting data

The script `plot.py` generates plots that visualize on a map the countries and subdivisions for which data has been retrieved, as well as the availability of electricity demand data clustered by GDP, PPP per capita and annual electricity demand per capita. To plot the these figures, run:

```bash
uv run plot.py map_of_covered_countries
uv run plot.py data_availability
```
