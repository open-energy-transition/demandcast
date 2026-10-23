"""
License: AGPL-3.0.

Description:

    This script generates the shapes of the ten areas of Japan of the
    Organization for Cross-regional Coordination of Transmission
    Operators (OCCTO), each served by one general transmission
    operator, from the shapes of the prefectures.

    The areas of Tokyo (Kantō) and Kansai are those of the shapes of
    TEPCO and Kansai TD (see tepco.py and kansaitd.py), so that the
    shapes of their data sources are the same. Chūbu is Nagano, Gifu,
    Shizuoka, Aichi and Mie, without the parts of Shizuoka and Mie in
    the areas of Tokyo and Kansai, and Hokuriku is Toyama, Ishikawa and
    Fukui, without the south of Fukui in Kansai. The other areas are
    whole prefectures: Tōhoku with Niigata. The small parts of Gifu in
    Hokuriku and of other prefectures served across their borders are
    left in their prefecture.

    Source: https://en.wikipedia.org/wiki/Electricity_sector_in_Japan#/media/File:Power_Grid_of_Japan.svg
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

# Define the URL of the zip file containing the shapefile of the
# prefectures.
url = (
    "https://data.humdata.org/dataset/6ba099c6-350b-4711-9a65-d85a1c5e519c/"
    "resource/f82faadf-a608-42cf-ae15-75ce672d7e69/download/"
    "jpn_adm_2019_shp.zip"
)

# The prefectures of each area, by their ISO 3166-2 codes, without the
# areas of Tokyo and Kansai, which are those of their data sources.
PREFECTURES_OF_AREAS = {
    "Hokkaidō": ["JP01"],
    "Tōhoku": ["JP02", "JP03", "JP04", "JP05", "JP06", "JP07", "JP15"],
    "Chūbu": ["JP20", "JP21", "JP22", "JP23", "JP24"],
    "Hokuriku": ["JP16", "JP17", "JP18"],
    "Chūgoku": ["JP31", "JP32", "JP33", "JP34", "JP35"],
    "Shikoku": ["JP36", "JP37", "JP38", "JP39"],
    "Kyūshū": ["JP40", "JP41", "JP42", "JP43", "JP44", "JP45", "JP46"],
    "Okinawa": ["JP47"],
}

# The shapes of the areas of Tokyo and Kansai.
shapes_folder = os.path.dirname(__file__)
kanto = geopandas.read_file(os.path.join(shapes_folder, "tepco", "tepco.shp"))
kansai = geopandas.read_file(
    os.path.join(shapes_folder, "kansaitd", "kansaitd.shp")
)

# Download the zip file.
response = requests.get(url, timeout=60)

# Define the folder where to extract the shapefile.
temporary_dir = os.path.join(shapes_folder, "occto_temp")
os.makedirs(temporary_dir, exist_ok=True)

# Extract the zip file.
with zipfile.ZipFile(BytesIO(response.content)) as z:
    z.extractall(temporary_dir)

# Read the shapefile of the prefectures.
prefectures = geopandas.read_file(
    os.path.join(temporary_dir, "jpn_admbnda_adm1_2019.shp")
).to_crs(epsg=4326)

# Merge the prefectures of each area, without the parts in the areas of
# Tokyo and Kansai.
neighbours = pd.concat([kanto, kansai]).union_all()
rows = []
for name, codes in PREFECTURES_OF_AREAS.items():
    geometry = prefectures[prefectures["ADM1_PCODE"].isin(codes)].union_all()
    rows.append(
        {
            "name": name,
            "code": f"JPN_{name}",
            "geometry": geometry.difference(neighbours),
        }
    )
rows.append(
    {"name": "Kantō", "code": "JPN_Kantō", "geometry": kanto.union_all()}
)
rows.append(
    {"name": "Kansai", "code": "JPN_Kansai", "geometry": kansai.union_all()}
)
areas = geopandas.GeoDataFrame(rows, crs=4326)

# Set the precision of the geometry to a grid size of 0.005 degrees.
# This is done to remove small spikes in the shapes that cause issues
# when plotting the shapes.
areas["geometry"] = areas["geometry"].set_precision(0.005)

# Save the shapes of the areas to a shapefile.
shapes_dir = os.path.join(shapes_folder, "occto")
os.makedirs(shapes_dir, exist_ok=True)
areas.to_file(os.path.join(shapes_dir, "occto.shp"), driver="ESRI Shapefile")

# Remove the temporary folder.
shutil.rmtree(temporary_dir)
