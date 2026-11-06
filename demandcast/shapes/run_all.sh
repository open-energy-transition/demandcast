#!/bin/bash

# Runs the scripts of this folder, which generate the shapefiles of the
# subdivisions that are not standard, read by utils/shapes.py. It is run
# from this folder.

# occto.py reads the shapes of kansaitd.py and tepco.py, so it comes
# after them.
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

for script in $scripts; do
    uv run "$script.py"
done
