#!/bin/bash

# Define all the data sources.
data_sources="aemo_nem \
aemo_wem \
aeso \
bchydro \
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
epias \
eskom \
hydroquebec \
ieso \
krogd \
nbpower \
neso \
ngcp \
niti \
ntdc \
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
for source in $data_sources; do
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
