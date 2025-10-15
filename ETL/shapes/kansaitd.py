# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script generates the shape of the Japanese region served by
    Kansai Transmission and Distribution (KANSAITD).

    KANSAITD serves the Kansai region, which includes:
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

# Polygon mask for mainland Hyōgo (exclude Awaji Island)
hyogo = prefectures[prefectures["ADM1_PCODE"] == "JP28"]
mask_hyogo = geopandas.GeoSeries(
    Polygon(
        [
            (133.2, 34.5),
            (134.9, 34.5),
            (135.5, 35.5),
            (134.5, 36.5),
            (133.0, 36.5),
            (133.0, 35.0),
        ]
    )
)
mask_hyogo = geopandas.GeoDataFrame(geometry=mask_hyogo, crs=4326)
hyogo_cut = hyogo.overlay(mask_hyogo, how="intersection")

# Polygon mask for southern Fukui Prefecture
fukui = prefectures[prefectures["ADM1_PCODE"] == "JP18"]
mask_fukui = geopandas.GeoSeries(
    Polygon(
        [
            (135.3, 35.4),
            (136.4, 35.4),
            (136.4, 36.0),
            (135.3, 36.0),
        ]
    )
)
mask_fukui = geopandas.GeoDataFrame(geometry=mask_fukui, crs=4326)
fukui_cut = fukui.overlay(mask_fukui, how="intersection")

# Polygon mask for western Mie Prefecture
mie = prefectures[prefectures["ADM1_PCODE"] == "JP24"]
mask_mie = geopandas.GeoSeries(
    Polygon(
        [
            (135.0, 33.8),
            (136.3, 33.8),
            (136.3, 35.0),
            (135.0, 35.0),
        ]
    )
)
mask_mie = geopandas.GeoDataFrame(geometry=mask_mie, crs=4326)
mie_cut = mie.overlay(mask_mie, how="intersection")

# Merge all prefectures into one geometry
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
