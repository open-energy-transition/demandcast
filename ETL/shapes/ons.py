# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the four major subsystems of the
    Brazilian electricity sector.

    Source: https://pt.wikipedia.org/wiki/Sistema_Interligado_Nacional
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas

# Define the codes of the Brazilian states and their corresponding
# subdivisions.
codes_of_brazilian_subdivisions = {
    "BR-AC": "BR_N",
    "BR-AP": "BR_N",
    "BR-AM": "BR_N",
    "BR-PA": "BR_N",
    "BR-RO": "BR_N",
    "BR-RR": "BR_N",
    "BR-TO": "BR_N",
    "BR-AL": "BR_NE",
    "BR-BA": "BR_NE",
    "BR-CE": "BR_NE",
    "BR-MA": "BR_NE",
    "BR-PB": "BR_NE",
    "BR-PI": "BR_NE",
    "BR-PE": "BR_NE",
    "BR-RN": "BR_NE",
    "BR-SE": "BR_NE",
    "BR-ES": "BR_SE",
    "BR-MG": "BR_SE",
    "BR-RJ": "BR_SE",
    "BR-SP": "BR_SE",
    "BR-GO": "BR_SE",
    "BR-MT": "BR_SE",
    "BR-MS": "BR_SE",
    "BR-DF": "BR_SE",
    "BR-PR": "BR_S",
    "BR-SC": "BR_S",
    "BR-RS": "BR_S",
}

# Define the names of the Brazilian subdivisions.
names_of_brazilian_subdivisions = {
    "BR_N": "North",
    "BR_NE": "North-East",
    "BR_SE": "South-East",
    "BR_S": "South",
}

# Load the shapefile containing the subdivision shapes from the Natural
# Earth database.
all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="50m", category="cultural", name="admin_1_states_provinces"
)

# Define a reader for the shapefile.
reader = cartopy.io.shapereader.Reader(all_shapes)

# Read the shapefiles of all Brazilian states.
state_shapes = [
    shape
    for shape in list(reader.records())
    if shape.attributes["iso_a2"] == "BR"
]

# Create a DataFrame from the shapes of the states.
states = pandas.DataFrame(columns=["name", "code", "parent", "geometry"])
for state_shape in state_shapes:
    state = pandas.Series(
        {
            "name": state_shape.attributes["name"],
            "code": state_shape.attributes["iso_3166_2"],
            "parent": codes_of_brazilian_subdivisions[
                state_shape.attributes["iso_3166_2"]
            ],
            "geometry": state_shape.geometry,
        }
    )
    states = pandas.concat([states, state.to_frame().T], ignore_index=True)

# Add the coordinate reference system to the GeoDataFrame.
states = geopandas.GeoDataFrame(states, geometry="geometry", crs="EPSG:4326")

# Merge the states belonging to the same subdivision.
subdivisions = states.dissolve(by="parent")

# Reset the index of the GeoDataFrame.
subdivisions = subdivisions.reset_index()

# Drop the columns that are not needed.
subdivisions = subdivisions[["name", "parent", "geometry"]]

# Rename the columns of the GeoDataFrame.
subdivisions = subdivisions.rename(columns={"parent": "code"})

# Add the names of the subdivisions to the GeoDataFrame.
for subdivision_code in subdivisions["code"]:
    subdivisions.loc[subdivisions["code"] == subdivision_code, "name"] = (
        names_of_brazilian_subdivisions[subdivision_code]
    )

# Set the precision of the geometry to a grid size of 0.005 degrees.
# This is done to remove small spikes in the shapes that cause issues
# when plotting the shapes.
subdivisions["geometry"] = subdivisions["geometry"].set_precision(0.005)

# Save the shapes of the subdivisions to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "ons")
os.makedirs(shapes_dir, exist_ok=True)
subdivisions.to_file(
    os.path.join(shapes_dir, "ons.shp"), driver="ESRI Shapefile"
)
