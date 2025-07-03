# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script retrieves the shapes of the US balancing authorities
    from the website of the US Energy Information Administration (EIA).
    It then merges the balancing authorities belonging to the same
    region and saves the shapefile. Balancing authorities are electric
    entities and do not have well-defined geographical boundaries. As a
    result, the balancing authority shapefiles sometimes overlap each
    other. The script fixes some of these overlaps by cutting the
    overlapping regions.

    Source: https://atlas.eia.gov/datasets/eia::balancing-authorities/about
    Source: https://www.eia.gov/electricity/gridmonitor/expanded-view/electric_overview/US48/US48/ElectricStatusMap-1
"""  # noqa: W505

import os

import geopandas
from shapely import Polygon

# Define the URL of the shapefile of the balancing authorities.
url = (
    "https://hub.arcgis.com/api/v3/datasets/"
    "09550598922b429ca9f06b9a067257bd_255/downloads/"
    "data?format=shp&spatialRefId=3857&where=1%3D1"
)

# Read the shapefile of the balancing authorities as a GeoDataFrame.
balancing_authorities = geopandas.read_file(url)

# Change the projection of the shapefile to EPSG 4326.
balancing_authorities = balancing_authorities.to_crs(epsg=4326)

# Merge the balancing authorities belonging to the same region.
regions = balancing_authorities.dissolve(by="EIAregion")

# Define the codes of the regions.
region_codes = {
    "California": "US_CAL",
    "Carolinas": "US_CAR",
    "Central": "US_CENT",
    "Florida": "US_FLA",
    "Mid-Atlantic": "US_MIDA",
    "Midwest": "US_MIDW",
    "New England": "US_NE",
    "New York": "US_NY",
    "Northwest": "US_NW",
    "Southeast": "US_SE",
    "Southwest": "US_SW",
    "Tennessee": "US_TEN",
    "Texas": "US_TEX",
}

# Add the codes to the regions shapefile.
for region_name in regions.index:
    regions.loc[region_name, "EIAcode"] = region_codes[region_name]

# Select the columns of interest.
regions = regions[["EIAcode", "geometry"]]

# Reset the index.
regions = regions.reset_index()

# Rename the columns.
regions = regions.rename(columns={"EIAregion": "name", "EIAcode": "code"})

########################################################################
# The following code fixes the overlaps between the regions. The regions
# are not well defined and sometimes overlap each other. This was a
# manual process and each step had to be checked visually.
########################################################################

# Using the California region, cut the Northwest.
regions.loc[regions["name"] == "Northwest", "geometry"] = regions.loc[
    regions["name"] == "Northwest", "geometry"
].difference(
    regions.loc[regions["name"] == "California", "geometry"], align=False
)

# Using the California region, cut the Southwest.
regions.loc[regions["name"] == "Southwest", "geometry"] = regions.loc[
    regions["name"] == "Southwest", "geometry"
].difference(
    regions.loc[regions["name"] == "California", "geometry"], align=False
)

# Remove the Northern portion of the Southwest region.
new_bounds = geopandas.GeoSeries(
    Polygon([(-120, 25), (-90, 25), (-90, 40), (-120, 40)])
)
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)
regions.loc[regions["name"] == "Southwest", "geometry"] = regions.loc[
    regions["name"] == "Southwest", "geometry"
].intersection(new_bounds.geometry, align=False)

# Using the Southwest region, cut the Northwest region.
regions.loc[regions["name"] == "Northwest", "geometry"] = regions.loc[
    regions["name"] == "Northwest", "geometry"
].difference(
    regions.loc[regions["name"] == "Southwest", "geometry"], align=False
)

# Using the Texas region, cut the Southwest region.
regions.loc[regions["name"] == "Southwest", "geometry"] = regions.loc[
    regions["name"] == "Southwest", "geometry"
].difference(regions.loc[regions["name"] == "Texas", "geometry"], align=False)

# Using the Texas region, cut the Central region.
regions.loc[regions["name"] == "Central", "geometry"] = regions.loc[
    regions["name"] == "Central", "geometry"
].difference(regions.loc[regions["name"] == "Texas", "geometry"], align=False)

# Using the Southwest region, cut the Central region.
regions.loc[regions["name"] == "Central", "geometry"] = regions.loc[
    regions["name"] == "Central", "geometry"
].difference(
    regions.loc[regions["name"] == "Southwest", "geometry"], align=False
)

# Fill a little gap in the Northwest region.
new_bounds = geopandas.GeoSeries(
    Polygon([(-105, 45), (-100, 45), (-100, 48), (-105, 48)])
)
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)
regions.loc[regions["name"] == "Northwest", "geometry"] = regions.loc[
    regions["name"] == "Northwest", "geometry"
].union(new_bounds.geometry, align=False)

# Using the Central region, cut the Northwest region.
regions.loc[regions["name"] == "Northwest", "geometry"] = regions.loc[
    regions["name"] == "Northwest", "geometry"
].difference(
    regions.loc[regions["name"] == "Central", "geometry"], align=False
)

# Remove the Northwestern portion of the Midwest region.
new_bounds = geopandas.GeoSeries(
    Polygon([(-100, 25), (-80, 25), (-80, 50), (-100, 50)])
)
new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)
regions.loc[regions["name"] == "Midwest", "geometry"] = regions.loc[
    regions["name"] == "Midwest", "geometry"
].intersection(new_bounds.geometry, align=False)

# Using the Texas region, cut the Midwest region.
regions.loc[regions["name"] == "Midwest", "geometry"] = regions.loc[
    regions["name"] == "Midwest", "geometry"
].difference(regions.loc[regions["name"] == "Texas", "geometry"], align=False)

# Using the Central region, cut the Midwest region.
regions.loc[regions["name"] == "Midwest", "geometry"] = regions.loc[
    regions["name"] == "Midwest", "geometry"
].difference(
    regions.loc[regions["name"] == "Central", "geometry"], align=False
)

# Using the Southeast region, cut the Midwest region.
regions.loc[regions["name"] == "Midwest", "geometry"] = regions.loc[
    regions["name"] == "Midwest", "geometry"
].difference(
    regions.loc[regions["name"] == "Southeast", "geometry"], align=False
)

# Using the Tennessee region, cut the Midwest region.
regions.loc[regions["name"] == "Midwest", "geometry"] = regions.loc[
    regions["name"] == "Midwest", "geometry"
].difference(
    regions.loc[regions["name"] == "Tennessee", "geometry"], align=False
)

# Using the Tennessee region, cut the Southeast region.
regions.loc[regions["name"] == "Southeast", "geometry"] = regions.loc[
    regions["name"] == "Southeast", "geometry"
].difference(
    regions.loc[regions["name"] == "Tennessee", "geometry"], align=False
)

# Using the Mid-Atlantic region, cut the Midwest region.
regions.loc[regions["name"] == "Midwest", "geometry"] = regions.loc[
    regions["name"] == "Midwest", "geometry"
].difference(
    regions.loc[regions["name"] == "Mid-Atlantic", "geometry"], align=False
)

# Using the Mid-Atlantic region, cut the Tennessee region.
regions.loc[regions["name"] == "Tennessee", "geometry"] = regions.loc[
    regions["name"] == "Tennessee", "geometry"
].difference(
    regions.loc[regions["name"] == "Mid-Atlantic", "geometry"], align=False
)

# Using the Southeast region, cut the Florida region.
regions.loc[regions["name"] == "Florida", "geometry"] = regions.loc[
    regions["name"] == "Florida", "geometry"
].difference(
    regions.loc[regions["name"] == "Southeast", "geometry"], align=False
)

# Using the Mid-Atlantic region, cut the Carolinas region.
regions.loc[regions["name"] == "Carolinas", "geometry"] = regions.loc[
    regions["name"] == "Carolinas", "geometry"
].difference(
    regions.loc[regions["name"] == "Mid-Atlantic", "geometry"], align=False
)

# Using the Tennessee region, cut the Carolinas region.
regions.loc[regions["name"] == "Carolinas", "geometry"] = regions.loc[
    regions["name"] == "Carolinas", "geometry"
].difference(
    regions.loc[regions["name"] == "Tennessee", "geometry"], align=False
)

# Using the Southeast region, cut the Carolinas region.
regions.loc[regions["name"] == "Carolinas", "geometry"] = regions.loc[
    regions["name"] == "Carolinas", "geometry"
].difference(
    regions.loc[regions["name"] == "Southeast", "geometry"], align=False
)

# Using the New York region, cut the Mid-Atlantic region.
regions.loc[regions["name"] == "Mid-Atlantic", "geometry"] = regions.loc[
    regions["name"] == "Mid-Atlantic", "geometry"
].difference(
    regions.loc[regions["name"] == "New York", "geometry"], align=False
)

# Using the New York region, cut the New England region.
regions.loc[regions["name"] == "New England", "geometry"] = regions.loc[
    regions["name"] == "New England", "geometry"
].difference(
    regions.loc[regions["name"] == "New York", "geometry"], align=False
)

########################################################################

# Save the shapes of the regions to a shapefile.
shapes_dir = os.path.join(os.path.dirname(__file__), "eia")
os.makedirs(shapes_dir, exist_ok=True)
regions.to_file(os.path.join(shapes_dir, "eia.shp"), driver="ESRI Shapefile")
