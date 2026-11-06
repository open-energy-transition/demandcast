"""
License: AGPL-3.0.

Description:

    This script generates the shape of Great Britain, which is served by
    NESO, as the part of the shape of the United Kingdom of Natural
    Earth at 1:50m within a polygon that leaves out Northern Ireland and
    the remote islands.

    The geometry is snapped to a grid of 0.005 degrees, which removes
    small spikes in the shape that cause issues when it is plotted.
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas as pd
from shapely import Polygon

all_shapes = cartopy.io.shapereader.natural_earth(
    resolution="50m", category="cultural", name="admin_0_countries"
)

reader = cartopy.io.shapereader.Reader(all_shapes)

# Read the shapefile of the United Kingdom.
uk_shape = next(
    shape for shape in reader.records() if shape.attributes["ISO_A2"] == "GB"
)
uk_shape = pd.Series({"geometry": uk_shape.geometry})
uk_shape = geopandas.GeoSeries(uk_shape)
uk_shape_frame = geopandas.GeoDataFrame.from_features(uk_shape, crs=4326)

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
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

gb_shape = uk_shape_frame.overlay(new_bounds_frame, how="intersection")

gb_shape["name"] = ["Great Britain"]
gb_shape["code"] = ["GBR_GB"]

gb_shape = gb_shape[["name", "code", "geometry"]]

gb_shape["geometry"] = gb_shape["geometry"].set_precision(0.005)

gb_shape = gb_shape.set_crs(epsg=4326)

shapes_dir = os.path.join(os.path.dirname(__file__), "neso")
os.makedirs(shapes_dir, exist_ok=True)
gb_shape.to_file(os.path.join(shapes_dir, "neso.shp"), driver="ESRI Shapefile")
