"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the four major subsystems of the
    Brazilian electricity sector, by merging the shapes of the Brazilian
    states of Natural Earth at 1:50m.

    The geometries are snapped to a grid of 0.005 degrees, which removes
    small spikes in the shapes that cause issues when they are plotted.

    Source: https://pt.wikipedia.org/wiki/Sistema_Interligado_Nacional
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas as pd

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

all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="50m", category="cultural", name="admin_1_states_provinces"
)

reader = cartopy.io.shapereader.Reader(all_shapes)

state_shapes = [
    shape
    for shape in list(reader.records())
    if shape.attributes["iso_a2"] == "BR"
]

# Create a DataFrame from the shapes of the states.
states = pd.DataFrame(columns=["name", "code", "parent", "geometry"])
for state_shape in state_shapes:
    state = pd.Series(
        {
            "name": state_shape.attributes["name"],
            "code": state_shape.attributes["iso_3166_2"],
            "parent": codes_of_brazilian_subdivisions[
                state_shape.attributes["iso_3166_2"]
            ],
            "geometry": state_shape.geometry,
        }
    )
    states = pd.concat([states, state.to_frame().T], ignore_index=True)

states = geopandas.GeoDataFrame(states, geometry="geometry", crs="EPSG:4326")

subdivisions = states.dissolve(by="parent")

subdivisions = subdivisions.reset_index()

subdivisions = subdivisions[["name", "parent", "geometry"]]

subdivisions = subdivisions.rename(columns={"parent": "code"})

for subdivision_code in subdivisions["code"]:
    subdivisions.loc[subdivisions["code"] == subdivision_code, "name"] = (
        names_of_brazilian_subdivisions[subdivision_code]
    )

subdivisions["geometry"] = subdivisions["geometry"].set_precision(0.005)

subdivisions = subdivisions.set_crs(epsg=4326)

shapes_dir = os.path.join(os.path.dirname(__file__), "ons")
os.makedirs(shapes_dir, exist_ok=True)
subdivisions.to_file(
    os.path.join(shapes_dir, "ons.shp"), driver="ESRI Shapefile"
)
