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
    "BR-AC": "BRA_N",
    "BR-AP": "BRA_N",
    "BR-AM": "BRA_N",
    "BR-PA": "BRA_N",
    "BR-RO": "BRA_N",
    "BR-RR": "BRA_N",
    "BR-TO": "BRA_N",
    "BR-AL": "BRA_NE",
    "BR-BA": "BRA_NE",
    "BR-CE": "BRA_NE",
    "BR-MA": "BRA_NE",
    "BR-PB": "BRA_NE",
    "BR-PI": "BRA_NE",
    "BR-PE": "BRA_NE",
    "BR-RN": "BRA_NE",
    "BR-SE": "BRA_NE",
    "BR-ES": "BRA_SE",
    "BR-MG": "BRA_SE",
    "BR-RJ": "BRA_SE",
    "BR-SP": "BRA_SE",
    "BR-GO": "BRA_SE",
    "BR-MT": "BRA_SE",
    "BR-MS": "BRA_SE",
    "BR-DF": "BRA_SE",
    "BR-PR": "BRA_S",
    "BR-SC": "BRA_S",
    "BR-RS": "BRA_S",
}

# Define the names of the Brazilian subdivisions.
names_of_brazilian_subdivisions = {
    "BRA_N": "North",
    "BRA_NE": "North-East",
    "BRA_SE": "South-East",
    "BRA_S": "South",
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

# Add the coordinate reference system (CRS) to the shapefile.
subdivisions = subdivisions.set_crs(epsg=4326)

# Save the shapes of the subdivisions to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "ons")
os.makedirs(shapes_dir, exist_ok=True)
subdivisions.to_file(
    os.path.join(shapes_dir, "ons.shp"), driver="ESRI Shapefile"
)
