# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates the shape of the Japanese region served by
    Kansai Transmission and Distribution (KansaiTD).

    KansaiTD serves the Kansai region, which includes:
        - Entire prefectures: Shiga, Kyoto, Osaka, Nara, Wakayama
        - Most of Hyōgo Prefecture (excluding Awaji Island)
        - Southern portion of Fukui Prefecture
        - Western portion of Mie Prefecture

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
temporary_dir = os.path.join(os.path.dirname(__file__), "kansaitd_temp")
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

# Define the codes of the prefectures fully included.
codes_of_whole_prefectures = [
    "JP25",
    "JP26",
    "JP27",
    "JP29",
    "JP30",
]

# Select the prefectures of interest.
whole_prefectures = prefectures[
    prefectures["ADM1_PCODE"].isin(codes_of_whole_prefectures)
]

## Merge all the prefectures into a single geometry.
whole_prefectures = whole_prefectures.dissolve(by="ADM0_EN")
whole_prefectures = whole_prefectures.reset_index()

# Select the shape of the Hyogo Prefecture.
hyogo = prefectures[prefectures["ADM1_PCODE"] == "JP28"]

# Define a mask polygon to exclude Awaji Island from Hyogo Prefecture.
mask_hyogo = geopandas.GeoSeries(
    Polygon(
        [
            (134.05, 34.72),
            (134.35, 34.66),
            (134.61, 34.75),
            (134.88, 34.63),
            (135.78, 34.53),
            (135.90, 35.83),
            (133.78, 35.89),
        ]
    )
)
mask_hyogo = geopandas.GeoDataFrame(geometry=mask_hyogo, crs=4326)

# Cut Hyogo Prefecture with the mask polygon.
hyogo_cut = hyogo.overlay(mask_hyogo, how="intersection")

# Select the shape of the Fukui Prefecture.
fukui = prefectures[prefectures["ADM1_PCODE"] == "JP18"]

# Define a mask polygon for southern Fukui Prefecture.
mask_fukui = geopandas.GeoSeries(
    Polygon(
        [
            (135.40, 35.21),
            (136.19, 35.44),
            (135.69, 35.91),
            (135.14, 35.78),
        ]
    )
)
mask_fukui = geopandas.GeoDataFrame(geometry=mask_fukui, crs=4326)

# Cut Fukui Prefecture with the mask polygon.
fukui_cut = fukui.overlay(mask_fukui, how="intersection")

# Select the shape of the Mie Prefecture.
mie = prefectures[prefectures["ADM1_PCODE"] == "JP24"]

# Define a mask polygon for western Mie Prefecture.
mask_mie = geopandas.GeoSeries(
    Polygon(
        [
            (136.03, 33.54),
            (136.37, 33.85),
            (135.88, 34.17),
            (135.58, 33.79),
        ]
    )
)
mask_mie = geopandas.GeoDataFrame(geometry=mask_mie, crs=4326)

# Cut Mie Prefecture with the mask polygon.
mie_cut = mie.overlay(mask_mie, how="intersection")

# Merge all prefectures into one geometry.
all_prefectures = pandas.concat(
    [whole_prefectures, hyogo_cut, fukui_cut, mie_cut]
)
all_prefectures = all_prefectures.dissolve(by="ADM0_EN").reset_index()

# Select the columns of interest.
all_prefectures = all_prefectures[["ADM1_EN", "ADM1_PCODE", "geometry"]]

# Rename columns.
all_prefectures = all_prefectures.rename(
    columns={"ADM1_EN": "name", "ADM1_PCODE": "code"}
)

# Rename the region name and code.
all_prefectures["name"] = ["Kansai"]
all_prefectures["code"] = ["JPN_Kansai"]

# Save the shape of the region to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "kansaitd")
os.makedirs(shapes_dir, exist_ok=True)
all_prefectures.to_file(
    os.path.join(shapes_dir, "kansaitd.shp"), driver="ESRI Shapefile"
)

# Remove temporary folder.
shutil.rmtree(temporary_dir)
