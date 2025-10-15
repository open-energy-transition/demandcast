# Extract Transform Load (ETL)

This module contains all scripts related to the extraction, transformation, and loading of electricity demand, weather, and population data. It is designed to provide a standardized pipeline to prepare data for downstream modeling and analysis.

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
├── download_electricity_data.py    # Main script to download electricity demand data
├── download_population_data.py     # Script to retrieve population data from SEDAC
├── download_weather_data.py        # Script to retrieve weather data from Copernicus
├── get_temperature_data.py         # Script to extract temperature time series
├── retrieval/                      # Data source-specific scripts and configuration
│   ├── entsoe.py, eia.py, ...      # Retrieval logic for each data provider
│   ├── entsoe.yaml, eia.yaml, ...  # Lists of country/subdivision information per source
│   └── copernicus.py               # Copernicus Climate Data Store (CDS) retrieval functions
├── shapes/                         # Non-standard subdivision shapes
│   └── eia.py, ons.py, ...         # Scripts that generate non-standard shapefiles
├── util/                           # Shared utilities
│   ├── directories.py              # Functions to read directories
│   ├── directories.yaml            # Keys to define the ETL folder structure
│   ├── entities.py                 # Functions to read country and subdivision information
│   ├── fetcher.py                  # Functions to fetch online content
│   ├── figures.py                  # Functions to plot basic figures
│   ├── geospatial.py               # Functions to process geospatial data
│   ├── shapes.py                   # Functions to read country and subdivision shapes
│   ├── time_series.py              # Time series processing
│   └── uploader.py                 # Functions for cloud storage uploads
└── .env                            # API keys (not included in repo)
```

## Application Programming Interface (API) keys

Some scripts require API keys to access data from external services. These keys should be stored in a `.env` file in the `ETL/` directory. The `.env` file should not be included in the repository and should contain the following environment variables:

```plaintext
CDS_API_KEY=<your_key>             # For data retrieval from Copernicus CDS
ENTSOE_API_KEY=<your_key>          # For data retrieval from ENTSO-E
EIA_API_KEY=<your_key>             # For data retrieval from EIA
ZENODO_API_KEY=<your_key>          # For data upload to Zenodo
SANDBOX_ZENODO_API_KEY=<your_key>  # For data upload to Zenodo Sandbox
```

## Electricity demand data

Scripts in this section download and process electricity demand data from multiple sources such as ENTSO-E, EIA, and CCEI. The data is processed to have all timestamps in UTC and electricity demand in MW.

### Main script

Run the main script with:

```bash
uv run download_electricity_data.py <data_source> [-c country_or_subdivision_code] [-f code_file] [-g bucket_name] [-z] [-p]
```

Arguments:

- `<data_source>`: The acronym of the data source as defined in the retrieval modules (e.g., `ENTSOE`).
- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-g, --upload_to_gcs`: (Optional) The bucket name of the Google Cloud Storage (GCS) to upload the data.
- `-z, --upload_to_zenodo`: (Optional) If set, the script will upload the data to a new or existing Zenodo record.
- `-p, --publish_to_zenodo`: (Optional) If set, the script will publish the Zenodo record after uploading.

#### Example

Download electricity data for France from ENTSO-E:

```bash
uv run download_electricity_data.py ENTSOE -c FR
```

### Retrieval scripts

Each retrieval script in the `retrieval/` folder is designed to fetch electricity demand data from a specific data source. The main functions in each script typically include:

- **Check input parameters (`_check_input_parameters`)**: Checks that the input parameters are valid.
- **Data request construction (`get_available_requests`)**: Builds all data requests based on the availability of the data source.
- **URL construction (`get_url`)**: Generates the appropriate web request URL.
- **Data download and processing (`download_and_extract_data_for_request`)**: Fetches the data using `utils.fetcher` functions and transforms it into a `pandas.Series`.

### Names, codes, time zones, and data time ranges for countries and subdivisions

For each retrieval script in the `retrieval/` folder, a corresponding YAML file must be created. The YAML file should contain a list of dictionaries, each representing a country or subdivision from the respective data source. The following rules apply:

- Names and codes should adhere to the ISO 3166 standard.
- For countries and standard subdivisions, use alpha-2 codes.
- For non-standard subdivisions, use a widely accepted name and code.
- Data time range must be specified.
- For subdivisions, time zone must be specified.

### Non-standard subdivisions

Some countries have subdivisions that are not standard ISO subdivisions. For these cases, the `shapes/` folder contains scripts to generate the shapes of these subdivisions. The scripts are named after the data source (e.g., `eia.py`, `ons.py`) and contain functions to generate the shapes. The generated shapes are then used in the retrieval scripts and for plotting.

## Population data

To download and prepare population data from the Socioeconomic Data and Applications Center (SEDAC):

```bash
uv run download_population_data.py [-c country_or_subdivision_code] [-f code_file] [-y year]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the population data to be downloaded.

The script:

- Downloads 30-second resolution data from SEDAC.
- Aggregates to 0.25° resolution to match weather data.
- Saves `.nc` files in `data/population_density/`.

## Weather data

To retrieve weather data from the Copernicus Climate Data Store (CDS), first ensure that you are registered on the website and have your API key stored in the `.env` file. Instructions for the API key can be found [here](https://cds.climate.copernicus.eu/how-to-api). Then run:

```bash
uv run download_weather_data.py [-c country_or_subdivision_code] [-f code_file] [-y year]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the weather data to be downloaded.

The script:

- Retrieves temperature data from the Copernicus Climate Data Store.
- Stores `.nc` files in `data/weather/`.

Note that the size of weather data files is on the order of 100 MB per country per year, so ensure you have sufficient storage space.

## Gross Domestic Product (GDP) data

To retrieve gridded GDP data, run:

```bash
uv run download_gdp_data.py [-c country_or_subdivision_code] [-f code_file] [-y year]
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the GDP data to be downloaded.

The script will download GDP data from Zenodo and store it in `data/gdp/`.

## Temperature time series extraction

Generate temperature time series based on population-weighted regions:

```bash
uv run ETL/get_temperature_data.py
```

Arguments:

- `-c, --code`: (Optional) The ISO Alpha-2 code (e.g., `FR`) or a combination of ISO Alpha-2 code and subdivision code (e.g., `US_CAL`).
- `-f, --file`: (Optional) The path to the YAML file containing the list of codes for the countries and subdivisions of interest.
- `-y, --year`: (Optional) The year of the weather data to use.

The script will extract time series of temperature based on the largest and three largest population density areas and output `.csv` or `.parquet` files in `data/temperature/`.

Note that the `get_temperature_data.py` script requires both weather and population data to be available in the specified directories.
