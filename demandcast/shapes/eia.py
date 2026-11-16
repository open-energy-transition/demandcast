"""
License: AGPL-3.0.

Description:

    This script defines the regions of the hourly electricity data of
    the US Energy Information Administration (EIA-930) as composites of
    the states of Natural Earth, cut along the counties that the
    balancing authorities of each region serve, and writes them to
    composites.yaml, replacing the earlier ones.

    Each county of the lower 48 states goes to the region whose
    balancing authorities sell the most electricity in it, by the
    service territories and the retail sales of the utilities in
    EIA-861: the sales of a utility in a state are spread over its
    counties there by population. Where the region with the most sales
    leads the next by less than MARGIN of them, and in Texas, whose
    largest distribution companies EIA-861 does not list by county, the
    county goes instead to the region of most of its area in the zones
    of Electricity Maps, the balancing authorities named by their
    region of EIA-930.

    Source: https://www.eia.gov/electricity/data/eia861/
    Source: https://www.eia.gov/electricity/gridmonitor/about
    Source: https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html
    Source: https://www.census.gov/programs-surveys/popest.html
    Source: https://github.com/electricitymaps/electricitymaps-contrib
"""

import collections
import io
import os
import re
import tempfile
import unicodedata
import zipfile
from typing import Any

import cartopy.io.shapereader
import geopandas
import numpy as np
import pandas as pd
import requests
import shapely
import yaml

EIA861_YEAR = 2025
EIA861_URL = (
    f"https://www.eia.gov/electricity/data/eia861/zip/f861{EIA861_YEAR}.zip"
)
EIA930_URL = (
    "https://www.eia.gov/electricity/930-content/EIA930_Reference_Tables.xlsx"
)
COUNTIES_URL = (
    "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
)
POPULATION_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/"
    "counties/totals/co-est2024-alldata.csv"
)
ZONES_URL = (
    "https://raw.githubusercontent.com/electricitymaps/"
    "electricitymaps-contrib/3baa27a61b8ac50ebdcdf6bc248242f57ee16cac/"
    "geo/world.geojson"
)
COMPOSITES_FILE = os.path.join(os.path.dirname(__file__), "composites.yaml")
# The least share of the sales of a county by which the region with the
# most of them must lead the next, for the county to follow EIA-861.
MARGIN = 0.15
# The states whose counties follow the zones of Electricity Maps.
ZONE_STATES = ("TX",)
OUTSIDE_LOWER_48 = ("AK", "HI", "PR", "VI", "GU", "AS", "MP")
EQUAL_AREA = "ESRI:102003"


def _download(url: str) -> bytes:
    """
    Download a file.

    Parameters
    ----------
    url : str
        The URL of the file.

    Returns
    -------
    bytes
        The content of the file.
    """
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    return response.content


def _normalize(name: str) -> str:
    """
    Normalize the name of a county, to match EIA-861 to the Census.

    Parameters
    ----------
    name : str
        The name of the county.

    Returns
    -------
    str
        The name in capitals, without accents, punctuation, spaces and
        words such as "County" or "Parish".
    """
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode().upper()
    name = re.sub(r"[.'\-]", " ", name)
    name = re.sub(
        r"\b(COUNTY|PARISH|BOROUGH|CENSUS AREA|MUNICIPALITY)\b", "", name
    )
    name = re.sub(r"\bSAINT\b", "ST", name)
    return "".join(name.split())


def _slug(name: str) -> str:
    """
    Make the name of a cut from a name.

    Parameters
    ----------
    name : str
        The name, such as "New Mexico" or "Mid-Atlantic".

    Returns
    -------
    str
        The name in lower case, without accents, with underscores
        between its words.
    """
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode().lower()
    return "_".join(re.findall(r"[a-z]+", name))


def read_counties() -> geopandas.GeoDataFrame:
    """
    Read the counties of the lower 48 states, with their population.

    Returns
    -------
    geopandas.GeoDataFrame
        The counties, with their state ("state"), the key that matches
        EIA-861 ("key") and their population in 2024 ("population").
    """
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "counties.zip")
        with open(path, "wb") as file:
            file.write(_download(COUNTIES_URL))
        counties = geopandas.read_file(f"zip://{path}")
    population = pd.read_csv(
        io.BytesIO(_download(POPULATION_URL)), encoding="latin-1", dtype=str
    )
    population = population[population["SUMLEV"] == "050"]
    population_of = pd.Series(
        pd.to_numeric(population["POPESTIMATE2024"]).to_numpy(),
        index=population["STATE"] + population["COUNTY"],
    )
    counties = counties[~counties["STUSPS"].isin(OUTSIDE_LOWER_48)].copy()
    counties["population"] = counties["GEOID"].map(population_of).fillna(1)
    counties["state"] = counties["STUSPS"]
    names = counties["NAME"].map(_normalize)
    # Independent cities, which EIA-861 names "<name> City".
    names = names.where(counties["LSAD"] != "25", names + "CITY")
    counties["key"] = counties["state"] + "|" + names
    return counties.reset_index(drop=True)


def sales_by_region(
    counties: geopandas.GeoDataFrame,
) -> list[collections.Counter]:
    """
    Spread the retail sales of the utilities over the counties.

    Parameters
    ----------
    counties : geopandas.GeoDataFrame
        The counties, from `read_counties`.

    Returns
    -------
    list[collections.Counter]
        For each county, its sales in MWh by region of EIA-930.
    """
    reference = pd.read_excel(
        io.BytesIO(_download(EIA930_URL)), sheet_name="BAs"
    )
    region_of = dict(
        zip(
            reference["BA Code"],
            reference["Region/Country Code"],
            strict=True,
        )
    )
    archive = zipfile.ZipFile(io.BytesIO(_download(EIA861_URL)))
    territories = pd.read_excel(
        archive.open(f"Service_Territory_{EIA861_YEAR}.xlsx"),
        sheet_name="Counties_States",
    )
    territories["key"] = (
        territories["State"] + "|" + territories["County"].map(_normalize)
    )
    sales = pd.read_excel(
        archive.open(f"Sales_Ult_Cust_{EIA861_YEAR}.xlsx"),
        sheet_name="States",
        header=2,
    )
    # Full service, delivery only and bundled sales, which the energy
    # only sales of retailers would count again.
    sales = sales[sales["Part"].isin(["A", "C", "D"])].copy()
    sales["mwh"] = pd.to_numeric(sales["Megawatthours.4"], errors="coerce")
    sales = (
        sales.groupby(["Utility Number", "State", "BA Code"])["mwh"]
        .sum()
        .reset_index()
    )
    population = dict(
        zip(counties["key"], counties["population"], strict=True)
    )
    served = territories.groupby(["Utility Number", "State"])["key"].apply(
        list
    )
    by_key: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for (utility, state), group in sales.groupby(["Utility Number", "State"]):
        keys = [k for k in served.get((utility, state), []) if k in population]
        total = sum(population[k] for k in keys)
        for authority, mwh in zip(group["BA Code"], group["mwh"], strict=True):
            if authority not in region_of or not total:
                continue
            for key in keys:
                by_key[key][region_of[authority]] += (
                    mwh * population[key] / total
                )
    return [by_key[key] for key in counties["key"]]


def zone_regions(counties: geopandas.GeoDataFrame) -> pd.Series:
    """
    Find the region of most of the area of each county in the zones.

    Parameters
    ----------
    counties : geopandas.GeoDataFrame
        The counties, from `read_counties`.

    Returns
    -------
    pandas.Series
        The region of EIA-930 of each county, from the zones of the
        balancing authorities of Electricity Maps.
    """
    zones = geopandas.read_file(io.BytesIO(_download(ZONES_URL)))
    zones = zones[zones["zoneName"].str.match(r"^US-[A-Z]+-")].copy()
    zones["region"] = zones["zoneName"].str.split("-").str[1]
    zones = zones.dissolve(by="region").reset_index().to_crs(EQUAL_AREA)
    shapes = counties[["geometry"]].to_crs(EQUAL_AREA)
    shapes["county"] = shapes.index
    pieces = geopandas.overlay(shapes, zones[["region", "geometry"]])
    pieces["area"] = pieces.area
    largest = pieces.sort_values("area").groupby("county").last()
    return largest["region"].reindex(counties.index)


def assign_regions(counties: geopandas.GeoDataFrame) -> pd.Series:
    """
    Assign each county to a region of EIA-930.

    Parameters
    ----------
    counties : geopandas.GeoDataFrame
        The counties, from `read_counties`.

    Returns
    -------
    pandas.Series
        The region of each county.

    Notes
    -----
    The few counties without sales nor zone take the region of the
    nearest county of their state.
    """
    sales = sales_by_region(counties)
    zones = zone_regions(counties)
    states = counties["state"].to_numpy()
    regions: list[Any] = []
    for county, by_region in enumerate(sales):
        ranked = by_region.most_common(2)
        total = sum(by_region.values())
        second = ranked[1][1] if len(ranked) > 1 else 0
        lead = (ranked[0][1] - second) / total if total else 0
        zone = zones.get(county)
        if states[county] in ZONE_STATES or lead < MARGIN:
            regions.append(zone if isinstance(zone, str) else None)
        else:
            regions.append(ranked[0][0])
        if regions[-1] is None and ranked:
            regions[-1] = ranked[0][0]
    result = pd.Series(regions, index=counties.index, dtype=object)
    points = counties.to_crs(EQUAL_AREA).representative_point()
    xy = shapely.get_coordinates(points.to_numpy())
    for empty in np.flatnonzero(result.isna().to_numpy()):
        pool = np.flatnonzero(
            result.notna().to_numpy() & (states == states[empty])
        )
        distance = np.hypot(*(xy[pool] - xy[empty]).T)
        result.iloc[int(empty)] = result.iloc[int(pool[distance.argmin()])]
    return result


def cut_of(outside: Any, inside: Any) -> str:
    """
    Make the WKT of the cut of a state, rounded to 0.1 degrees.

    Parameters
    ----------
    outside : shapely.Geometry
        The counties of the state outside the region.
    inside : shapely.Geometry
        The counties of the state in the region.

    Returns
    -------
    str
        The polygon or multipolygon of the counties outside, widened
        out of the state but not into the counties inside.
    """
    cut = shapely.buffer(outside, 0.3).difference(inside)
    cut = shapely.simplify(cut, 0.05, preserve_topology=True)
    cut = shapely.set_precision(cut, 0.1).buffer(0)
    parts = [p for p in shapely.get_parts(cut) if p.area > 0.005]
    cut = parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)
    return str(shapely.to_wkt(cut, rounding_precision=1, trim=True))


def build(
    counties: geopandas.GeoDataFrame, regions: pd.Series
) -> dict[str, dict]:
    """
    Build the composites of the regions.

    Parameters
    ----------
    counties : geopandas.GeoDataFrame
        The counties, from `read_counties`.
    regions : pandas.Series
        The region of each county, from `assign_regions`.

    Returns
    -------
    dict[str, dict]
        The cuts and the composites of the regions, as in
        composites.yaml.
    """
    reference = pd.read_excel(
        io.BytesIO(_download(EIA930_URL)), sheet_name="Regions"
    )
    name_of = dict(
        zip(
            reference["Region/Country Code"],
            reference["Region/Country Name"],
            strict=True,
        )
    )
    states = geopandas.read_file(
        cartopy.io.shapereader.natural_earth(
            resolution="10m",
            category="cultural",
            name="admin_1_states_provinces",
        )
    )
    states = states[states["iso_a2"] == "US"]
    state_name = dict(
        zip(states["iso_3166_2"].str[3:], states["name"], strict=True)
    )
    cuts: dict[str, dict] = {}
    composites: dict[str, dict] = {}
    for region in sorted(set(regions)):
        in_region = regions == region
        codes = sorted(set(counties.loc[in_region, "state"]))
        composite: dict[str, Any] = {
            "name": name_of[region],
            "regions": [f"US-{code}" for code in codes],
        }
        for code in codes:
            state = counties["state"] == code
            if not (state & ~in_region).any():
                continue
            key = f"{_slug(state_name[code])}_outside_{_slug(name_of[region])}"
            cuts[key] = {
                "description": f"The counties of {state_name[code]}, United "
                f"States, outside the {name_of[region]} region of EIA-930.",
                "polygon": cut_of(
                    shapely.union_all(counties.geometry[state & ~in_region]),
                    shapely.union_all(counties.geometry[state & in_region]),
                ),
            }
            composite.setdefault("cuts", {})[f"US-{code}"] = key
        composites[f"USA_{region}"] = composite
    return {"cuts": cuts, "composites": composites}


def _wrap(text: str, indent: str) -> list[str]:
    """
    Wrap a text at its spaces into lines of at most 79 characters.

    Parameters
    ----------
    text : str
        The text.
    indent : str
        The indentation of each line.

    Returns
    -------
    list[str]
        The lines.
    """
    lines, line = [], ""
    for word in text.split(" "):
        longer = f"{line} {word}" if line else word
        if line and len(indent) + len(longer) > 79:
            lines.append(indent + line)
            line = word
        else:
            line = longer
    return [*lines, indent + line]


def _quote(text: str) -> str:
    """
    Quote a text for YAML if it needs it.

    Parameters
    ----------
    text : str
        The text.

    Returns
    -------
    str
        The text, in double quotes if it has a colon, a hash or quotes.
    """
    if re.search(r"[:#'\"]", text):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def write(new: dict[str, dict]) -> None:
    """
    Write the composites of the regions into composites.yaml.

    Parameters
    ----------
    new : dict[str, dict]
        The cuts and the composites of the regions, from `build`.

    Notes
    -----
    The composites of the regions replace the earlier ones, and the
    cuts that no composite uses any more are dropped.
    """
    with open(COMPOSITES_FILE, encoding="utf-8") as file:
        text = file.read()
    header = []
    for line in text.splitlines():
        if not line.startswith("#"):
            break
        header.append(line)
    data = yaml.safe_load(text)
    data["composites"].update(new["composites"])
    data["cuts"].update(new["cuts"])
    used = {
        cut
        for composite in data["composites"].values()
        for cut in composite.get("cuts", {}).values()
    }
    lines = [*header, "", "cuts:"]
    for key in sorted(used):
        cut = data["cuts"][key]
        description = _wrap(
            f"description: {_quote(cut['description'])}", "    "
        )
        lines += [f"  {key}:", description[0]]
        lines += ["  " + line for line in description[1:]]
        lines += ["    polygon: >-", *_wrap(cut["polygon"], "      ")]
    lines += ["", "composites:"]
    for code in sorted(data["composites"]):
        composite = data["composites"][code]
        regions = composite["regions"]
        if isinstance(regions, str):
            regions = regions.split()
        lines += [f"  {code}:", f"    name: {_quote(composite['name'])}"]
        if len(f"    regions: {' '.join(regions)}") <= 79:
            lines.append(f"    regions: {' '.join(regions)}")
        else:
            lines += ["    regions: >-", *_wrap(" ".join(regions), "      ")]
        if composite.get("cuts"):
            lines.append("    cuts:")
            lines += [
                f"      {region}: {cut}"
                for region, cut in composite["cuts"].items()
            ]
    with open(COMPOSITES_FILE, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def main() -> None:
    """Write the regions of EIA-930 to composites.yaml."""
    counties = read_counties()
    regions = assign_regions(counties)
    write(build(counties, regions))


if __name__ == "__main__":
    main()
