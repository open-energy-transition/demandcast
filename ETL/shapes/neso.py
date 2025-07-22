# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates the shape of Great Britain, which is served by
    NESO.
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas
from shapely import Polygon

# Load the shapefile containing the shapes of the countries from the
# Natural Earth database.
all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="50m", category="cultural", name="admin_0_countries"
)

# Define a reader for the shapefile.
reader = cartopy.io.shapereader.Reader(all_shapes)

# Read the shapefile of the United Kingdom.
uk_shape = [
    shape
    for shape in list(reader.records())
    if shape.attributes["ISO_A2"] == "GB"
][0]
uk_shape = pandas.Series({"geometry": uk_shape.geometry})
uk_shape = geopandas.GeoSeries(uk_shape)
uk_shape = geopandas.GeoDataFrame.from_features(uk_shape, crs=4326)

# Define a polygon to exclude the Northern Ireland and remote islands
# from the UK shape.
new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-7, 49),
            (-4.85, 54.45),
            (-9.8, 57.55),
            (-3.5, 60.25),
            (2, 56),
            (2.75, 51.75),
            (-2.7, 49.2),
        ]
    )
)
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the UK shape.
gb_shape = uk_shape.overlay(new_bounds, how="intersection")

# Add the name and code of the subdivision.
gb_shape["name"] = ["Great Britain"]
gb_shape["code"] = ["GB_GB"]

# Reorder the columns.
gb_shape = gb_shape[["name", "code", "geometry"]]

# Save the shape of the subdivision to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "neso")
os.makedirs(shapes_dir, exist_ok=True)
gb_shape.to_file(os.path.join(shapes_dir, "neso.shp"), driver="ESRI Shapefile")
