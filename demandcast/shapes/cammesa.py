"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the Argentine provinces with
    electricity demand data from CAMMESA. The shapefile of Natural Earth
    at 1:50m has no Argentine provinces, so they are read from the one
    at 1:10m.

    Source: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas as pd

# The provinces of the data of CAMMESA, by ISO 3166-2 code. Buenos
# Aires, its autonomous city and Tierra del Fuego are left out: CAMMESA
# splits Greater Buenos Aires from the rest of the province, and Tierra
# del Fuego is not connected to the national system.
codes_of_provinces = [
    "AR-A",
    "AR-D",
    "AR-E",
    "AR-F",
    "AR-G",
    "AR-H",
    "AR-J",
    "AR-K",
    "AR-L",
    "AR-M",
    "AR-N",
    "AR-P",
    "AR-Q",
    "AR-R",
    "AR-S",
    "AR-T",
    "AR-U",
    "AR-W",
    "AR-X",
    "AR-Y",
    "AR-Z",
]

# Load the shapefile of the provinces of Natural Earth at 1:10m.
all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="10m", category="cultural", name="admin_1_states_provinces"
)
reader = cartopy.io.shapereader.Reader(all_shapes)

# Read the shapes of the provinces, with the codes of DemandCast, such
# as ARG_X for Córdoba (AR-X).
provinces = pd.DataFrame(
    [
        {
            "name": shape.attributes["name"],
            "code": "ARG_" + shape.attributes["iso_3166_2"].split("-")[1],
            "geometry": shape.geometry,
        }
        for shape in reader.records()
        if shape.attributes["iso_3166_2"] in codes_of_provinces
    ]
)
if sorted(provinces["code"]) != sorted(
    "ARG_" + code.split("-")[1] for code in codes_of_provinces
):
    raise ValueError("Some provinces are missing from Natural Earth.")
provinces = geopandas.GeoDataFrame(
    provinces, geometry="geometry", crs="EPSG:4326"
)

# Set the precision of the geometry to a grid size of 0.005 degrees.
# This is done to remove small spikes in the shapes that cause issues
# when plotting the shapes.
provinces["geometry"] = provinces["geometry"].set_precision(0.005)

# Save the shapes of the provinces to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "cammesa")
os.makedirs(shapes_dir, exist_ok=True)
provinces.to_file(
    os.path.join(shapes_dir, "cammesa.shp"), driver="ESRI Shapefile"
)
