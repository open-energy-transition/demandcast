#!/bin/bash

# Retrieves the electricity demand of all data sources, then the
# population, GDP and weather data. Outdated: retrieve.py now reads its
# settings from config/retrieve_config.yaml (issue #184).

# Data sources whose files are downloaded automatically.
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

for source in $automated_data_sources; do
    printf "Retrieving data for source: %s\n" "$source"
    uv run retrieve.py electricity_demand -d "$source"
done

# Data sources whose files are downloaded manually, then harmonized here.
manual_data_sources="epias \
eskom \
krogd \
niti \
ntdc"

for source in $manual_data_sources; do
    printf "Harmonizing data for source: %s\n" "$source"
    uv run retrieve.py electricity_demand -d "$source"
done

uv run retrieve.py population
uv run retrieve.py gridded_population
uv run retrieve.py gdp_ppp_per_capita
uv run retrieve.py gridded_gdp_ppp
uv run retrieve.py gridded_weather -wv temperature
uv run retrieve.py temperature
