# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates the shape of the Japanese region served by
    Kansai Transmission and Distribution (KANSAITD). This includes
    the main Kansai prefectures: Osaka, Kyoto, Hyogo, Nara, Shiga,
    Wakayama, and parts of Mie Prefecture.

    Sources:
        https://en.wikipedia.org/wiki/Electricity_sector_in_Japan#/media/File:Power_Grid_of_Japan.svg
        https://en.wikipedia.org/wiki/Kansai_Electric_Power_Company
        https://en.wikipedia.org/wiki/ISO_3166-2:JP
        https://data.humdata.org/dataset/cod-xa-jpn
"""  # noqa: W505

import os
import shutil
import zipfile
from io import BytesIO

import geopandas
import pandas
import requests
from shapely import Polygon

# Define the URL of the zip file containing the shapefile of the
# prefectures.
url = (
    "https://data.humdata.org/dataset/6ba099c6-350b-4711-9a65-d85a1c5e519c/"
    "resource/f82faadf-a608-42cf-ae15-75ce672d7e69/download/"
    "jpn_adm_2019_shp.zip"
)

# Download the zip file.
response = requests.get(url)

# Define the folder where to extract the shapefile.
temporary_dir = os.path.join(os.path.dirname(__file__), "kansai_temp")
os.makedirs(temporary_dir, exist_ok=True)

# Extract the zip file.
with zipfile.ZipFile(BytesIO(response.content)) as z:
    # Extract the contents of the zip file to a temporary directory.
    z.extractall(temporary_dir)

# Read the shapefile of the prefectures.
prefectures = geopandas.read_file(
    os.path.join(temporary_dir, "jpn_admbnda_adm1_2019.shp")
)

# Change the projection of the shapefile to EPSG 4326.
prefectures = prefectures.to_crs(epsg=4326)


# Define the codes of the prefectures of interest.
codes_of_whole_prefectures = [
    "JP25",
    "JP26",
    "JP27",
    "JP28",
    "JP29",
    "JP30",
]

# Select the prefectures of interest.
whole_prefectures = prefectures[
    prefectures["ADM1_PCODE"].isin(codes_of_whole_prefectures)
]

# Merge all the prefectures into a single geometry.
whole_prefectures = whole_prefectures.dissolve(by="ADM0_EN")
whole_prefectures = whole_prefectures.reset_index()


# Define the code of the prefecture to be cut.
codes_of_prefecture_to_cut = "JP24"

# Select the prefecture to be cut.
prefecture_to_cut = prefectures[
    prefectures["ADM1_PCODE"] == codes_of_prefecture_to_cut
]

# Define a polygon to cut the prefecture.
new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (138.48, 35.7),
            (138.48, 35.22),
            (138.68, 35),
            (138.68, 34.5),
            (139.5, 34.5),
            (139.5, 35.7),
        ]
    )
)
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

# Cut the prefecture.
cut_prefecture = prefecture_to_cut.overlay(new_bounds, how="intersection")

# Merge the cut prefecture with the whole prefectures.
all_prefectures = pandas.concat([whole_prefectures, cut_prefecture])
all_prefectures = all_prefectures.dissolve(by="ADM0_EN")
all_prefectures = all_prefectures.reset_index()


# Select the columns of interest.
all_prefectures = all_prefectures[["ADM1_EN", "ADM1_PCODE", "geometry"]]

# Rename columns.
all_prefectures = all_prefectures.rename(
    columns={"ADM1_EN": "name", "ADM1_PCODE": "code"}
)

# Rename the region name and code.
all_prefectures["name"] = ["KANSAITD"]
all_prefectures["code"] = ["JP_KANSAI"]

# Save the shape of the region to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "kansaitd")
os.makedirs(shapes_dir, exist_ok=True)
all_prefectures.to_file(
    os.path.join(shapes_dir, "kansaitd.shp"), driver="ESRI Shapefile"
)

# Remove temporary folder
shutil.rmtree(temporary_dir)
