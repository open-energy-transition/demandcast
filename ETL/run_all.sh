#!/bin/bash

# Define all the data sources.
data_sources="AEMO_NEM \
AEMO_WEM \
AESO \
BCHYDRO \
CAMMESA \
CCEI \
CEN \
CENACE \
CHINA \
COES \
EIA \
EMI \
ENTSOE \
EPIAS \
ESKOM \
HYDROQUEBEC \
IESO \
KROGD \
NBPOWER \
NESO \
NGCP \
NIGERIA \
NITI \
NTDC \
ONS \
PUCSL \
SONELGAZ \
TAIPOWER \
TEPCO \
TSOC \
XM"

# Iterate over each data source and retrieve the electricity time series data.
for source in $data_sources; do
    uv run retrieve.py electricity_demand $source
done

# Retrieve the population data.
uv run retrieve.py population

# Retrieve the gridded population data.
uv run retrieve.py gridded_population

# Retrieve the GDP PPP per capita data.
uv run retrieve.py gdp_ppp_per_capita

# Retrieve the gridded GDP PPP data.
# uv run retrieve.py gridded_gdp_ppp

# Retrieve the gridded weather data.
uv run retrieve.py gridded_weather -wv temperature

# Retrieve the temperature data.
uv run retrieve.py temperature
