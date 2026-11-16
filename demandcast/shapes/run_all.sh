#!/bin/bash

# Runs the scripts of this folder, which generate the shapefiles of the
# subdivisions that are not standard, read by utils/shapes.py, and the
# regions of the EIA in composites/USA.yaml. It is run from this folder.

# occto.py reads the shapes of kansaitd.py and tepco.py, so it comes
# after them.
scripts="cammesa \
eia \
kansaitd \
neso \
niti \
soni \
tepco \
occto"

for script in $scripts; do
    uv run "$script.py"
done
