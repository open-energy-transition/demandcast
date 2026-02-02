#!/bin/bash

# Define the name of the scripts that generate the shapefiles.
scripts="cenace \
eia \
kansaitd \
neso \
ons \
tepco"

# Iterate over each script and run it.
for script in $scripts; do
    uv run $script.py
done
