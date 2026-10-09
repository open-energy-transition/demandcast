#!/bin/bash

# Retrieves the electricity demand of all data sources, then the
# population, GDP and weather data.
#
# retrieve.py reads its settings from a yaml configuration file, which
# holds the values of a whole run. Each run below passes its own values
# with --set, which replace the ones of the file, so no file is written
# and removed around the runs.

set -euo pipefail

# Run retrieve.py with the given "key=value" pairs, which are applied
# over the values of the configuration file.
run_retrieve() {
    uv run retrieve.py "$@"
}

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
    run_retrieve \
        --set variable=electricity_demand \
        --set electricity_data_source="$source"
done

# Data sources whose files are downloaded manually, then harmonized here.
manual_data_sources="epias \
eskom \
krogd \
niti \
ntdc"

for source in $manual_data_sources; do
    printf "Harmonizing data for source: %s\n" "$source"
    run_retrieve \
        --set variable=electricity_demand \
        --set electricity_data_source="$source"
done

run_retrieve --set variable=population
run_retrieve --set variable=gridded_population
run_retrieve --set variable=gdp_ppp_per_capita
run_retrieve --set variable=gridded_gdp_ppp
run_retrieve \
        --set variable=gridded_weather \
        --set weather_variable=temperature
run_retrieve --set variable=temperature
