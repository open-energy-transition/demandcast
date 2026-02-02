#!/bin/bash

# Define all the data sources for which the retrieval process is automated.
automated_data_sources="adme \
aemo_nem \
aemo_wem \
aeso \
bchydro \
caiso \
cammesa \
ccei \
cen \
cenace \
cnd \
coes \
egat \
eia \
ema \
emi \
entsoe \
grupoice \
hydroquebec \
ieso \
kansaitd \
nbpower \
nea \
neso \
ngcp \
oluwole_et_al
ons \
pgcb \
pucsl \
sonelgaz \
taipower \
tepco \
tsoc \
wu_et_al \
xm"

# Iterate over each data source and retrieve the electricity time series data.
for source in $automated_data_sources; do
    printf "Retrieving data for source: %s\n" "$source"
    uv run retrieve.py electricity_demand -d $source
done

# Define all the data sources for which the retrieval process is maually handled.
manual_data_sources="epias \
eskom \
krogd \
niti \
ntdc"

# Iterate over each data source and harmonize the electricity time series data.
for source in $manual_data_sources; do
    printf "Harmonizing data for source: %s\n" "$source"
    uv run retrieve.py electricity_demand -d $source
done

# Retrieve the population data.
uv run retrieve.py population

# Retrieve the gridded population data.
uv run retrieve.py gridded_population

# Retrieve the GDP PPP per capita data.
uv run retrieve.py gdp_ppp_per_capita

# Retrieve the gridded GDP PPP data.
uv run retrieve.py gridded_gdp_ppp

# Retrieve the gridded weather data.
uv run retrieve.py gridded_weather -wv temperature

# Retrieve the temperature data.
uv run retrieve.py temperature
