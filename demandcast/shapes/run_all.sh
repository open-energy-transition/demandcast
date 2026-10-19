#!/bin/bash

# Define the name of the scripts that generate the shapefiles.
scripts="cammesa \
cenace \
eia \
kansaitd \
neso \
niti \
ons \
soni \
tepco"

# Iterate over each script and run it.
for script in $scripts; do
    uv run "$script.py"
done
