"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the subdivisions of Mexico
    according to the Mexican National Energy Control Center (CENACE)
    and saves them to a shapefile. The subdivisions are created by
    merging the states of Mexico into larger regions.

    The states split between two regions are cut with polygons drawn by
    hand, and each step is checked visually against the maps of the
    sources.

    The geometries are snapped to a grid of 0.005 degrees, which removes
    small spikes in the shapes that cause issues when they are plotted.

    Source: https://www.geni.org/globalenergy/library/national_energy_grid/mexico/index.shtml
    Source: https://github.com/jschleuss/mexican-states
    Source: https://acclaimenergy.com.mx/wp-content/uploads/2019/03/TMCA-Map.jpg
    Source: https://doi.org/10.1016/j.tej.2022.107142
"""

import os
import shutil
import zipfile
from io import BytesIO

import geopandas
import pandas as pd
import requests
from shapely import Polygon

# Define the URL of the zip file containing the shapefile of the Mexican
# states.
url = (
    "https://github.com/jschleuss/mexican-states/archive/refs/heads/master.zip"
)

response = requests.get(url, timeout=60)

temporary_dir = os.path.join(os.path.dirname(__file__), "cenace_temp")
os.makedirs(temporary_dir, exist_ok=True)

with zipfile.ZipFile(BytesIO(response.content), "r") as archive:
    archive.extractall(temporary_dir)

states = geopandas.read_file(
    os.path.join(temporary_dir, "mexican-states-master", "mexican-states.shp")
)

states = states.to_crs(epsg=4326)

states = states[["name", "is_in_coun", "ISO3166-2", "geometry"]]

states = states.rename(columns={"ISO3166-2": "code"})

# Baja California (MEX_BCA) and Baja California Sur (MEX_BCS).
subdivisions = states[states["code"] == "MX-BCN"]
subdivisions.loc[subdivisions["code"] == "MX-BCN", "code"] = "MEX_BCA"

subdivisions = pd.concat([subdivisions, states[states["code"] == "MX-BCS"]])
subdivisions.loc[subdivisions["code"] == "MX-BCS", "code"] = "MEX_BCS"

# Noroeste (MEX_NOR): Sonora and Sinaloa.
shapes_to_merge = states[states["code"].isin(["MX-SON", "MX-SIN"])]

merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

subdivisions = pd.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-SON", "code"] = "MEX_NOR"
subdivisions.loc[subdivisions["code"] == "MEX_NOR", "name"] = "Noroeste"

# Norte (MEX_NTE): Chihuahua and Durango.
shapes_to_merge = states[states["code"].isin(["MX-CHH", "MX-DUR"])]

merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

subdivisions = pd.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-CHH", "code"] = "MEX_NTE"
subdivisions.loc[subdivisions["code"] == "MEX_NTE", "name"] = "Norte"

# Peninsular (MEX_PEN): Campeche, Quintana Roo and Yucatan, without the
# western part of Campeche.
shapes_to_merge = states[states["code"].isin(["MX-CAM", "MX-ROO", "MX-YUC"])]

merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-91.5, 18.0),
            (-91.9, 19.0),
            (-93.0, 19.0),
            (-93.0, 16.0),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

merged_shape = merged_shape.overlay(new_bounds_frame, how="difference")

subdivisions = pd.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-CAM", "code"] = "MEX_PEN"
subdivisions.loc[subdivisions["code"] == "MEX_PEN", "name"] = "Peninsular"

# Noreste (MEX_NES): Coahuila, Nuevo Leon, Tamaulipas, the northern part
# of Veracruz and the eastern part of San Luis Potosi.
shapes_to_merge = states[states["code"].isin(["MX-COA", "MX-NLE", "MX-TAM"])]

shape_to_cut = states[states["code"].isin(["MX-VER"])]

new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-99.0, 21.5),
            (-97.0, 21.5),
            (-97.0, 23.0),
            (-99.0, 23.0),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

shape_to_cut = shape_to_cut.overlay(new_bounds_frame, how="intersection")

shapes_to_merge = pd.concat([shapes_to_merge, shape_to_cut])

shape_to_cut = states[states["code"].isin(["MX-SLP"])]

new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-99.4, 21.0),
            (-97.0, 21.0),
            (-97.0, 23.0),
            (-99.4, 23.0),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

shape_to_cut = shape_to_cut.overlay(new_bounds_frame, how="intersection")

shapes_to_merge = pd.concat([shapes_to_merge, shape_to_cut])

merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

subdivisions = pd.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-NLE", "code"] = "MEX_NES"
subdivisions.loc[subdivisions["code"] == "MEX_NES", "name"] = "Noreste"

# Occidental (MEX_OCC): Nayarit, Zacatecas, Jalisco, Aguascalientes,
# Colima, and parts of San Luis Potosi, Guanajuato and Michoacan.
shapes_to_merge = states[
    states["code"].isin(["MX-NAY", "MX-ZAC", "MX-JAL", "MX-AGU", "MX-COL"])
]

shape_to_cut = states[states["code"].isin(["MX-SLP"])]

# The polygon of the eastern part of San Luis Potosi, above, leaves its
# western part.
shape_to_cut = shape_to_cut.overlay(new_bounds_frame, how="difference")

shapes_to_merge = pd.concat([shapes_to_merge, shape_to_cut])

shape_to_cut = states[states["code"].isin(["MX-GUA"])]

# Keep only the northwestern part of Guanajuato.
new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-100.5, 20.8),
            (-100.0, 19.6),
            (-101.4, 19.6),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

shape_to_cut = shape_to_cut.overlay(new_bounds_frame, how="difference")

shapes_to_merge = pd.concat([shapes_to_merge, shape_to_cut])

shape_to_cut = states[states["code"].isin(["MX-MIC"])]

# Keep only the western part of Michoacan.
new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-100.5, 20.8),
            (-101.4, 19.6),
            (-101.7, 18.1),
            (-99.0, 18.1),
            (-99.0, 20.0),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

shape_to_cut = shape_to_cut.overlay(new_bounds_frame, how="difference")

shapes_to_merge = pd.concat([shapes_to_merge, shape_to_cut])

merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

subdivisions = pd.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-AGU", "code"] = "MEX_OCC"
subdivisions.loc[subdivisions["code"] == "MEX_OCC", "name"] = "Occidental"

# Central (MEX_CEN): Queretaro, Mexico, Mexico City, the western part
# of Guerrero, and the parts of Michoacan and Guanajuato outside
# Occidental.
shapes_to_merge = states[states["code"].isin(["MX-QUE", "MX-MEX", "MX-CMX"])]

shape_to_cut = states[states["code"].isin(["MX-GRO"])]

new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-100.625, 18.395),
            (-101.7, 17.2),
            (-102.9, 17.9),
            (-101.5, 19),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

shape_to_cut = shape_to_cut.overlay(new_bounds_frame, how="intersection")

shapes_to_merge = pd.concat([shapes_to_merge, shape_to_cut])

shapes_to_merge = pd.concat(
    [shapes_to_merge, states[states["code"].isin(["MX-MIC", "MX-GUA"])]]
)

merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

merged_shape = merged_shape.overlay(
    subdivisions[subdivisions["code"] == "MEX_OCC"], how="difference"
)

subdivisions = pd.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-CMX", "code"] = "MEX_CEN"
subdivisions.loc[subdivisions["code"] == "MEX_CEN", "name"] = "Central"

# Oriental (MEX_ORI): the rest of Mexico.
merged_states = states.dissolve(by="is_in_coun")
merged_states = merged_states.reset_index()

merged_subdivisions = subdivisions.dissolve(by="is_in_coun")
merged_subdivisions = merged_subdivisions.reset_index()

merged_states = merged_states.overlay(merged_subdivisions, how="difference")

subdivisions = pd.concat([subdivisions, merged_states])
subdivisions.loc[subdivisions["code"] == "MX-AGU", "code"] = "MEX_ORI"
subdivisions.loc[subdivisions["code"] == "MEX_ORI", "name"] = "Oriental"

subdivisions = subdivisions[["name", "code", "geometry"]]
subdivisions = subdivisions.reset_index(drop=True)

subdivisions["geometry"] = subdivisions["geometry"].set_precision(0.005)

subdivisions = subdivisions.set_crs(epsg=4326)

shapes_dir = os.path.join(os.path.dirname(__file__), "cenace")
os.makedirs(shapes_dir, exist_ok=True)
subdivisions.to_file(
    os.path.join(shapes_dir, "cenace.shp"), driver="ESRI Shapefile"
)

shutil.rmtree(temporary_dir)
