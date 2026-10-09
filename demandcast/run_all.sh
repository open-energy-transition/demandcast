#!/bin/bash

# Retrieves the electricity demand of all data sources, then the
# population, GDP and weather data.
#
# retrieve.py reads its settings from a yaml configuration file, so each
# run below writes one holding only the values it needs and passes it
# with --config. The file is removed when the script exits.

set -euo pipefail

# Write a configuration file holding the given "key: value" pairs and
# print its path. The pairs are the arguments after the file path.
write_config() {
    local config_file="$1"
    shift

    : >"$config_file"
    for pair in "$@"; do
        printf '%s\n' "$pair" >>"$config_file"
    done

    printf '%s\n' "$config_file"
}

# Run retrieve.py with the given configuration values. The first argument
# is the configuration file, the rest are "key: value" pairs.
run_retrieve() {
    local config_file="$1"
    shift

    uv run retrieve.py --config "$config_file" "$@"
}

# Create the configuration file and make sure it is removed on exit.
config_file="$(mktemp "${TMPDIR:-/tmp}/retrieve_config.XXXXXX.yaml")"
trap 'rm -f "$config_file"' EXIT

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
    run_retrieve "$config_file" \
        "variable: electricity_demand" \
        "electricity_data_source: $source"
done

# Data sources whose files are downloaded manually, then harmonized here.
manual_data_sources="epias \
eskom \
krogd \
niti \
ntdc"

for source in $manual_data_sources; do
    printf "Harmonizing data for source: %s\n" "$source"
    run_retrieve "$config_file" \
        "variable: electricity_demand" \
        "electricity_data_source: $source"
done

run_retrieve "$config_file" "variable: population"
run_retrieve "$config_file" "variable: gridded_population"
run_retrieve "$config_file" "variable: gdp_ppp_per_capita"
run_retrieve "$config_file" "variable: gridded_gdp_ppp"
run_retrieve "$config_file" "variable: gridded_weather" "weather_variable: temperature"
run_retrieve "$config_file" "variable: temperature"
