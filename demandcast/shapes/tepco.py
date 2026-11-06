"""
License: AGPL-3.0.

Description:

    This script generates the shape of the Japanese region served by
    the Tokyo Electric Power Company (TEPCO). TEPCO serves the Kantō
    region, Yamanashi Prefecture, and the eastern portion of Shizuoka
    Prefecture.

    The geometry is snapped to a grid of 0.005 degrees, which removes
    small spikes in the shape that cause issues when it is plotted.

    Source: https://en.wikipedia.org/wiki/Electricity_sector_in_Japan#/media/File:Power_Grid_of_Japan.svg
    Source: https://en.wikipedia.org/wiki/Tokyo_Electric_Power_Company
    Source: https://en.wikipedia.org/wiki/ISO_3166-2:JP
    Source: https://data.humdata.org/dataset/cod-xa-jpn
"""

import os
import shutil
import zipfile
from io import BytesIO

import geopandas
import pandas as pd
import requests
from shapely import Polygon

# Define the URL of the zip file containing the shapefile of the
# prefectures.
url = (
    "https://data.humdata.org/dataset/6ba099c6-350b-4711-9a65-d85a1c5e519c/"
    "resource/f82faadf-a608-42cf-ae15-75ce672d7e69/download/"
    "jpn_adm_2019_shp.zip"
)

response = requests.get(url, timeout=60)

temporary_dir = os.path.join(os.path.dirname(__file__), "tepco_temp")
os.makedirs(temporary_dir, exist_ok=True)

with zipfile.ZipFile(BytesIO(response.content)) as z:
    z.extractall(temporary_dir)

prefectures = geopandas.read_file(
    os.path.join(temporary_dir, "jpn_admbnda_adm1_2019.shp")
)

prefectures = prefectures.to_crs(epsg=4326)

# Define the codes of the prefectures of interest.
codes_of_whole_prefectures = [
    "JP08",
    "JP09",
    "JP10",
    "JP11",
    "JP12",
    "JP13",
    "JP14",
    "JP19",
]

whole_prefectures = prefectures[
    prefectures["ADM1_PCODE"].isin(codes_of_whole_prefectures)
]

whole_prefectures = whole_prefectures.dissolve(by="ADM0_EN")
whole_prefectures = whole_prefectures.reset_index()

# Define the code of the prefecture to be cut.
codes_of_prefecture_to_cut = "JP22"

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
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

cut_prefecture = prefecture_to_cut.overlay(
    new_bounds_frame, how="intersection"
)

all_prefectures = pd.concat([whole_prefectures, cut_prefecture])
all_prefectures = all_prefectures.dissolve(by="ADM0_EN")
all_prefectures = all_prefectures.reset_index()

# Define a polygon to cut remote islands.
new_bounds = geopandas.GeoSeries(
    Polygon(
        [
            (138.9, 34.4),
            (139.4, 35),
            (140, 34),
            (140.75, 34.5),
            (143, 38),
            (135, 38),
        ]
    )
)
new_bounds_frame = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

all_prefectures = all_prefectures.overlay(new_bounds_frame, how="intersection")

all_prefectures = all_prefectures[["ADM1_EN", "ADM1_PCODE", "geometry"]]

all_prefectures = all_prefectures.rename(
    columns={"ADM1_EN": "name", "ADM1_PCODE": "code"}
)

all_prefectures["name"] = ["Kantō"]
all_prefectures["code"] = ["JPN_Kantō"]

all_prefectures["geometry"] = all_prefectures["geometry"].set_precision(0.005)

all_prefectures = all_prefectures.set_crs(epsg=4326)

shapes_dir = os.path.join(os.path.dirname(__file__), "tepco")
os.makedirs(shapes_dir, exist_ok=True)
all_prefectures.to_file(
    os.path.join(shapes_dir, "tepco.shp"), driver="ESRI Shapefile"
)

shutil.rmtree(temporary_dir)
