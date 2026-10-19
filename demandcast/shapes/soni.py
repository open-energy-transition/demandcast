"""
License: AGPL-3.0.

Description:

    This script generates the shape of Northern Ireland, an area of
    ENTSO-E served by SONI, as the part of the shape of the United
    Kingdom of Natural Earth at 1:50m on the island of Ireland. The
    shape of Great Britain, the other area of the United Kingdom, is
    that of NESO (see neso.py).
"""

import os

import cartopy.io.shapereader
import geopandas
from shapely import MultiPolygon, box

# Load the shapefile containing the shapes of the countries from the
# Natural Earth database.
all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="50m", category="cultural", name="admin_0_countries"
)

# Read the shape of the United Kingdom.
reader = cartopy.io.shapereader.Reader(all_shapes)
uk_shape = next(
    shape for shape in reader.records() if shape.attributes["ISO_A2"] == "GB"
)

# Keep the polygons of the United Kingdom that lie in a box around
# Northern Ireland, which leaves out Great Britain, whose tip of Kintyre
# crosses the box.
bounds = box(-8.3, 53.9, -5.3, 55.45)
ni_polygons = [
    polygon for polygon in uk_shape.geometry.geoms if polygon.within(bounds)
]
ni_shape = geopandas.GeoDataFrame(
    geometry=[MultiPolygon(ni_polygons)], crs=4326
)

# Add the name and code of the subdivision.
ni_shape["name"] = ["Northern Ireland"]
ni_shape["code"] = ["GBR_NIR"]
ni_shape = ni_shape[["name", "code", "geometry"]]

# Set the precision of the geometry to a grid size of 0.005 degrees.
# This is done to remove small spikes in the shapes that cause issues
# when plotting the shapes.
ni_shape["geometry"] = ni_shape["geometry"].set_precision(0.005)

# Save the shape to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "soni")
os.makedirs(shapes_dir, exist_ok=True)
ni_shape.to_file(
    os.path.join(shapes_dir, "soni.shp"), driver="ESRI Shapefile"
)
