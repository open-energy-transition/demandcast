# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the subdivisions of Mexico
    according to the Mexican National Energy Control Center (CENACE)
    and saves them to a shapefile. The subdivisions are created by
    merging the states of Mexico into larger regions.

    Source: https://www.geni.org/globalenergy/library/national_energy_grid/mexico/index.shtml
    Source: https://github.com/jschleuss/mexican-states
    Source: https://acclaimenergy.com.mx/wp-content/uploads/2019/03/TMCA-Map.jpg
    Source: https://doi.org/10.1016/j.tej.2022.107142
"""  # noqa: W505

import os
import shutil
import zipfile
from io import BytesIO

import geopandas
import pandas
import requests
from shapely import Polygon

# Define the URL of the zip file containing the shapefile of the Mexican
# states.
url = (
    "https://github.com/jschleuss/mexican-states/archive/refs/heads/master.zip"
)

# Download the zip file.
response = requests.get(url)

# Define the folder where to extract the shapefile.
temporary_dir = os.path.join(os.path.dirname(__file__), "cenace_temp")
os.makedirs(temporary_dir, exist_ok=True)

# Extract the zip file.
with zipfile.ZipFile(BytesIO(response.content), "r") as archive:
    # Extract all the files in the archive.
    archive.extractall(temporary_dir)

# Read the shapefile of the Mexican states.
states = geopandas.read_file(
    os.path.join(temporary_dir, "mexican-states-master", "mexican-states.shp")
)

# Change the projection of the shapefile to EPSG 4326.
states = states.to_crs(epsg=4326)

# Keep only the columns of interest.
states = states[["name", "is_in_coun", "ISO3166-2", "geometry"]]

# Rename the columns.
states = states.rename(columns={"ISO3166-2": "code"})

########################################################################
# The following code creates the subdivisions of Mexico according to the
# Mexican National Energy Control Center (CENACE). The subdivisions are
# created by merging the states of Mexico into larger regions. This was
# a manual process and each step had to be checked visually.
########################################################################

# Add the shape of Baja California and set the code to "MEX_BCA".
subdivisions = states[states["code"] == "MX-BCN"]
subdivisions.loc[subdivisions["code"] == "MX-BCN", "code"] = "MEX_BCA"

# Add the shape of Baja California Sur and set the code to "MEX_BCS".
subdivisions = pandas.concat(
    [subdivisions, states[states["code"] == "MX-BCS"]]
)
subdivisions.loc[subdivisions["code"] == "MX-BCS", "code"] = "MEX_BCS"

# Get the shapes of Sonora and Sinaloa.
shapes_to_merge = states[states["code"].isin(["MX-SON", "MX-SIN"])]

# Merge the shapes of Sonora and Sinaloa.
merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

# Add the merged shape, Noroeste, to the subdivisions and set the name
# to Noroeste and code to "MEX_NOR".
subdivisions = pandas.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-SON", "code"] = "MEX_NOR"
subdivisions.loc[subdivisions["code"] == "MEX_NOR", "name"] = "Noroeste"

# Get the shapes of Chihuahua and Durango.
shapes_to_merge = states[states["code"].isin(["MX-CHH", "MX-DUR"])]

# Merge the shapes of Chihuahua and Durango.
merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

# Add the merged shape, Norte, to the subdivisions and set the name to
# Norte and code to "MEX_NOR".
subdivisions = pandas.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-CHH", "code"] = "MEX_NTE"
subdivisions.loc[subdivisions["code"] == "MEX_NTE", "name"] = "Norte"

# Get the shapes of Campeche, Quintana Roo and Yucatan.
shapes_to_merge = states[states["code"].isin(["MX-CAM", "MX-ROO", "MX-YUC"])]

# Merge the shapes of Campeche, Quintana Roo and Yucatan.
merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

# Define a polygon to exclude some parts of the Western part of
# Campeche.
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
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the merged shape.
merged_shape = merged_shape.overlay(new_bounds, how="difference")

# Add the merged shape, Peninsular, to the subdivisions and set the name
# to Peninsular and code to "MEX_PEN".
subdivisions = pandas.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-CAM", "code"] = "MEX_PEN"
subdivisions.loc[subdivisions["code"] == "MEX_PEN", "name"] = "Peninsular"

# Get the shapes of Coahuila, Nuevo Leon and Tamaulipas.
shapes_to_merge = states[states["code"].isin(["MX-COA", "MX-NLE", "MX-TAM"])]

# Get the shapes of Veracruz.
shape_to_cut = states[states["code"].isin(["MX-VER"])]

# Define a polygon to keep only the Northern part of Veracruz.
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
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the shape of Veracruz.
shape_to_cut = shape_to_cut.overlay(new_bounds, how="intersection")

# Add the cut shape of Veracruz to the shapes to merge.
shapes_to_merge = pandas.concat([shapes_to_merge, shape_to_cut])

# Get the shapes of San Luis Potosi.
shape_to_cut = states[states["code"].isin(["MX-SLP"])]

# Define a polygon to keep only the Eastern part of San Luis Potosi.
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
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the shape of San Luis Potosi.
shape_to_cut = shape_to_cut.overlay(new_bounds, how="intersection")

# Add the cut shape of San Luis Potosi to the shapes to merge.
shapes_to_merge = pandas.concat([shapes_to_merge, shape_to_cut])

# Merge the shapes of Coahuila, Nuevo Leon, Tamaulipas, Veracruz and San
# Luis Potosi.
merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

# Add the merged shape, Noreste, to the subdivisions and set the name to
# Noreste and code to "MEX_NES".
subdivisions = pandas.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-NLE", "code"] = "MEX_NES"
subdivisions.loc[subdivisions["code"] == "MEX_NES", "name"] = "Noreste"

# Get the shapes of Nayarit, Zacatecas, Yalisco, Aguascalientes and
# Colima.
shapes_to_merge = states[
    states["code"].isin(["MX-NAY", "MX-ZAC", "MX-JAL", "MX-AGU", "MX-COL"])
]

# Get the shapes of San Luis Potosi.
shape_to_cut = states[states["code"].isin(["MX-SLP"])]

# Using the same polygon as before, keep the Western part of San Luis
# Potosi.
shape_to_cut = shape_to_cut.overlay(new_bounds, how="difference")

# Add the cut shape of San Luis Potosi to the shapes to merge.
shapes_to_merge = pandas.concat([shapes_to_merge, shape_to_cut])

# Get the shapes of Guanajuato.
shape_to_cut = states[states["code"].isin(["MX-GUA"])]

# Define a polygon to keep only the Northwestern part of Guanajuato.
new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (-100.5, 20.8),
            (-100.0, 19.6),
            (-101.4, 19.6),
        ]
    )
)
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the shape of Guanajuato.
shape_to_cut = shape_to_cut.overlay(new_bounds, how="difference")

# Add the cut shape of Guanajuato to the shapes to merge.
shapes_to_merge = pandas.concat([shapes_to_merge, shape_to_cut])

# Get the shapes of Michoacan.
shape_to_cut = states[states["code"].isin(["MX-MIC"])]

# Define a polygon to keep only the Northwestern part of Guanajuato.
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
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the shape of Michoacan.
shape_to_cut = shape_to_cut.overlay(new_bounds, how="difference")

# Add the cut shape of Michoacan to the shapes to merge.
shapes_to_merge = pandas.concat([shapes_to_merge, shape_to_cut])

# Merge the shapes of Nayarit, Zacatecas, Jalisco, Aguascalientes,
# Colima, San Luis Potosi and Michoacan.
merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

# Add the merged shape, Occidental, to the subdivisions and set the name
# to Occidental and code to "MEX_OCC".
subdivisions = pandas.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-AGU", "code"] = "MEX_OCC"
subdivisions.loc[subdivisions["code"] == "MEX_OCC", "name"] = "Occidental"

# Get the shapes of Queretaro, Mexico, and Mexico City.
shapes_to_merge = states[states["code"].isin(["MX-QUE", "MX-MEX", "MX-CMX"])]

# Get the shapes of Guerreo.
shape_to_cut = states[states["code"].isin(["MX-GRO"])]

# Define a polygon to keep only the Southern part of Guerrero.
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
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the shape of Guerrero.
shape_to_cut = shape_to_cut.overlay(new_bounds, how="intersection")

# Add the cut shape of Guerrero to the shapes to merge.
shapes_to_merge = pandas.concat([shapes_to_merge, shape_to_cut])

# Add the shapes of Michoacan and Guanajuato.
shapes_to_merge = pandas.concat(
    [shapes_to_merge, states[states["code"].isin(["MX-MIC", "MX-GUA"])]]
)

# Merge the shapes of Queretaro, Mexico, Guerrero, Michoacan and
# Guanajuato.
merged_shape = shapes_to_merge.dissolve(by="is_in_coun")
merged_shape = merged_shape.reset_index()

# Remove the Northwestern part of the merged shape with the shape of
# Occidental region.
merged_shape = merged_shape.overlay(
    subdivisions[subdivisions["code"] == "MEX_OCC"], how="difference"
)

# Add the merged shape, Central, to the subdivisions and set the name to
# Central and code to "MEX_CEN".
subdivisions = pandas.concat([subdivisions, merged_shape])
subdivisions.loc[subdivisions["code"] == "MX-CMX", "code"] = "MEX_CEN"
subdivisions.loc[subdivisions["code"] == "MEX_CEN", "name"] = "Central"

# Merge all the states.
merged_states = states.dissolve(by="is_in_coun")
merged_states = merged_states.reset_index()

# Merge all the subdivisions already created.
merged_subdivisions = subdivisions.dissolve(by="is_in_coun")
merged_subdivisions = merged_subdivisions.reset_index()

# Remove the subdivisions from the merged states.
merged_states = merged_states.overlay(merged_subdivisions, how="difference")

# Add the merged shape, Oriental, to the subdivisions and set the name
# to Oriental and code to "MEX_ORI".
subdivisions = pandas.concat([subdivisions, merged_states])
subdivisions.loc[subdivisions["code"] == "MX-AGU", "code"] = "MEX_ORI"
subdivisions.loc[subdivisions["code"] == "MEX_ORI", "name"] = "Oriental"

########################################################################

# Keep only the columns of interest.
subdivisions = subdivisions[["name", "code", "geometry"]]
subdivisions = subdivisions.reset_index(drop=True)

# Set the precision of the geometry to a grid size of 0.005 degrees.
# This is done to remove small spikes in the shapes that cause issues
# when plotting the shapes.
subdivisions["geometry"] = subdivisions["geometry"].set_precision(0.005)

# Add the coordinate reference system (CRS) to the shapefile.
subdivisions = subdivisions.set_crs(epsg=4326)

# Save the shapes of the subdivisions to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "cenace")
os.makedirs(shapes_dir, exist_ok=True)
subdivisions.to_file(
    os.path.join(shapes_dir, "cenace.shp"), driver="ESRI Shapefile"
)

# Remove the folder with the shapefile of the Mexican states.
shutil.rmtree(temporary_dir)
