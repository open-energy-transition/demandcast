#!/bin/bash

# Define the name of the scripts that generate the shapefiles. occto.py
# reads the shapes of kansaitd.py and tepco.py, so it comes after them.
scripts="cammesa \
cenace \
eia \
kansaitd \
neso \
niti \
ons \
soni \
tepco \
occto"

# Iterate over each script and run it.
for script in $scripts; do
    uv run "$script.py"
done
