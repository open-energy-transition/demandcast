# Extended Getting Started Guide

This guide provides a comprehensive introduction to setting up and using DemandCast. It covers installation, configuration, basic usage, and answers to frequently asked questions.

## 1. Installation and Setup

To install DemandCast, follow these steps:

### 1.1 Clone the repository

```bash
git clone https://github.com/open-energy-transition/demandcast.git
cd demandcast
```

### 1.2 Set up your environment

This project uses [`uv`](https://github.com/astral-sh/uv) as a package manager to install the required dependencies and create an environment stored in `.venv`.

`uv` can be used within the provided Dockerfile or installed standalone (see [installing uv](https://docs.astral.sh/uv/getting-started/installation/)).

The `ETL` folder and each subfolder in the `models` directory—each representing a separate model—contain their own `pyproject.toml` files that define the dependencies for that module.

To set up the environment, run:
```bash
cd ETL # or cd models/model_name
uv sync
```

Alternatively, you may use a package manager of your choice (e.g., `conda`) to install the dependencies listed in the respective `pyproject.toml`. If you choose this approach, please adjust the commands below to align with the conventions of your selected package manager.

### 1.3 Configure environment variables

Some modules require API keys to access data from external services. These keys should be stored in a `.env` file in the `ETL/` directory. The `.env` file should not be included in the repository and should contain the following environment variables:

```plaintext
CDS_API_KEY=<your_key>             # For data retrieval from Copernicus CDS
ENTSOE_API_KEY=<your_key>          # For data retrieval from ENTSO-E
EIA_API_KEY=<your_key>             # For data retrieval from EIA
ZENODO_API_KEY=<your_key>          # For data upload to Zenodo
SANDBOX_ZENODO_API_KEY=<your_key>  # For data upload to Zenodo Sandbox
```

Replace `<your_key>` with your actual API keys. You can obtain these keys by registering on the respective service websites.

## 2. Retrieving Data

The following commands will execute the `ETL/retrieve.py` script to retrieve different types of data. The type of data to be retrieved is specified as a command-line argument. The retrieved data will be saved in the `data/<variable>/` directory in CSV and Parquet formats. Additional arguments can be provided as needed. Please refer to the documentation of the ETL retrieval modules for more details.

### 2.1 Retrieve Electricity Demand

The following command retrieves electricity demand from all available data sources:

```bash
cd ETL
uv run retrieve.py electricity_demand
```

If you want to retrieve data for a particular country or subdivision from a specific data source, you can supply the entity code and data source as additional arguments. For example, to retrieve electricity demand for Germany (DEU) from the ENTSO-E:

```bash
cd ETL
uv run retrieve.py electricity_demand --data_source entsoe --code DEU
```

### 2.2 Retrieve Annual Electricity Demand per Capita

The following command retrieves annual electricity demand per capita for all available entities and for both historical and projected data:

```bash
cd ETL
uv run retrieve.py annual_electricity_demand_per_capita
```

If you want to retrieve data for a particular country or subdivision and year, you can supply the entity code and year as additional arguments. For example, to retrieve annual electricity demand per capita for France (FRA) in 2020:

```bash
cd ETL
uv run retrieve.py annual_electricity_demand_per_capita --code FRA --year 2020
```

Similarly, for projected data, you can specify the year and scenario. For example, to retrieve projected annual electricity demand per capita for the United Kingdom (GBR) in 2030 under the 'SSP2-Baseline' scenario:

```bash
cd ETL
uv run retrieve.py annual_electricity_demand_per_capita --code GBR --year 2030 --scenario SSP2-Baseline
```

### 2.3 Retrieve GDP PPP per Capita

The following command retrieves GDP PPP per capita for all available entities and for both historical and projected data:

```bash
cd ETL
uv run retrieve.py gdp_ppp_per_capita
```

If you want to retrieve data for a particular country or subdivision and year, you can supply the entity code and year as additional arguments. For example, to retrieve GDP PPP per capita for Japan (JPN) in 2019:

```bash
cd ETL
uv run retrieve.py gdp_ppp_per_capita --code JPN --year 2019
```

Similarly, for projected data, you can specify the year and scenario. For example, to retrieve projected GDP PPP per capita for Canada (CAN) in 2040 under the 'SSP1' scenario:

```bash
cd ETL
uv run retrieve.py gdp_ppp_per_capita --code CAN --year 2040 --scenario SSP1
```

### 2.4 Retrieve Population

The following command retrieves population data for all available entities and for both historical and projected data:

```bash
cd ETL
uv run retrieve.py population
```

If you want to retrieve data for a particular country or subdivision and year, you can supply the entity code and year as additional arguments. For example, to retrieve population data for India (IND) in 2015:

```bash
cd ETL
uv run retrieve.py population --code IND --year 2015
```

Similarly, for projected data, you can specify the year and scenario. For example, to retrieve projected population data for Brazil (BRA) in 2050 under the 'SSP3' scenario:

```bash
cd ETL
uv run retrieve.py population --code BRA --year 2050 --scenario SSP3
```

### 2.5 Retrieve Temperature

The following command retrieves temperature data for all available entities and for both historical and projected data:

```bash
cd ETL
uv run retrieve.py temperature
```

If you want to retrieve data for a particular country or subdivision and year, you can supply the entity code and year as additional arguments. For example, to retrieve temperature data for Niger (NER) in 2010:

```bash
cd ETL
uv run retrieve.py temperature --code NER --year 2010
```

Similarly, for projected data, you can specify the year, model, and scenario. For example, to retrieve projected temperature data for Australia (AUS) in 2045 using the 'CESM2' model under 'SSP4-6.0' scenario:

```bash
cd ETL
uv run retrieve.py temperature --code AUS --year 2045 --climate_model CESM2 --scenario SSP4-6.0
```
