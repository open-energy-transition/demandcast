"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the Indian subdivisions with
    electricity demand data from NITI Aayog that are not states or union
    territories. The Damodar Valley Corporation (DVC) supplies parts of
    Jharkhand and West Bengal, so its demand is added to theirs, in the
    shape of the two states. The demand of Jammu and Kashmir includes
    Ladakh, which the data does not list, so it is in the shape of the
    two union territories. The other subdivisions have the standard
    shapes of Natural Earth at 1:50m, which are also used here.

    Source: https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-1-states-provinces/
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas as pd

# The merged subdivisions, by their code and name, with the ISO 3166-2
# codes of the states and union territories in them.
merged_subdivisions = {
    ("IND_JHWB", "Jharkhand and West Bengal"): ["IN-JH", "IN-WB"],
    ("IND_JKLA", "Jammu and Kashmir and Ladakh"): ["IN-JK", "IN-LA"],
}

# Load the shapefile of the states and provinces of Natural Earth at
# 1:50m, as the standard shapes.
all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="50m", category="cultural", name="admin_1_states_provinces"
)

shapes = []
for (code, name), iso_codes in merged_subdivisions.items():
    parts = geopandas.GeoDataFrame(
        [
            {"name": name, "code": code, "geometry": shape.geometry}
            for shape in cartopy.io.shapereader.Reader(all_shapes).records()
            if shape.attributes["iso_3166_2"] in iso_codes
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )
    if len(parts) != len(iso_codes):
        raise ValueError(
            f"Some parts of {name} are missing from Natural Earth."
        )
    shapes.append(parts.dissolve(by="code").reset_index())
subdivisions = pd.concat(shapes)[["name", "code", "geometry"]]

# Set the precision of the geometry to a grid size of 0.005 degrees.
# This is done to remove small spikes in the shapes that cause issues
# when plotting the shapes.
subdivisions["geometry"] = subdivisions["geometry"].set_precision(0.005)

# Save the shapes of the subdivisions to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "niti")
os.makedirs(shapes_dir, exist_ok=True)
subdivisions.to_file(
    os.path.join(shapes_dir, "niti.shp"), driver="ESRI Shapefile"
)
