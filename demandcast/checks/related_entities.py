"""
License: AGPL-3.0.

Description:

    This module computes which countries and subdivisions with
    electricity demand data share people: for each pair of entities of
    the same country whose shapes overlap, the share of the people of
    each one that live in the area that they share, from the gridded
    population of the year POPULATION_YEAR, each grid cell weighted by
    its fraction in the shapes. The people of an entity and those of
    the area that it shares are counted on the same grid, that of the
    entity, which covers the shared area, or that of its country for a
    subdivision without gridded data of its own, such as one smaller
    than 500 km² (see utils/availability.py).

    The shares are saved to related_entities.csv in the folder of the
    checks, one row per pair, with whether the pair is related (see
    utils/relations.py). Pairs whose shared area is under
    MINIMUM_SHARED_AREA of the area of the smaller entity, such as
    neighbours whose shapes touch, are left out.
"""

import itertools
import logging
import os

import geopandas
import pandas as pd
import xarray

import retrievals.gridded_totals
import utils.availability
import utils.data_sources
import utils.geospatial
import utils.relations
import utils.shapes

# The year of the gridded population.
POPULATION_YEAR = 2020

# The share of the area of the smaller entity from which a shared area
# counts.
MINIMUM_SHARED_AREA = 0.001

# The equal-area projection in which the areas are compared.
EQUAL_AREA_CRS = "EPSG:6933"


def _get_shares(
    code: str,
    other: str,
    shapes: dict[str, geopandas.GeoDataFrame],
    grids: dict[str, xarray.DataArray],
    grid_codes: dict[str, str],
) -> tuple[float, float] | None:
    """
    Get the shares of the people of two entities in their shared area.

    Parameters
    ----------
    code : str
        The code of an entity.
    other : str
        The code of the other entity.
    shapes : dict[str, geopandas.GeoDataFrame]
        The shape of each entity, in longitude and latitude.
    grids : dict[str, xarray.DataArray]
        The gridded population read so far, by the code of its grid, to
        which those of the two entities are added.
    grid_codes : dict[str, str]
        The code of the grid of each entity: its own, or its country's.

    Returns
    -------
    tuple[float, float] | None
        The share of the people of each entity in the shared area, or
        None if the shared area is too small to count.
    """
    shared = geopandas.overlay(
        shapes[code], shapes[other], how="intersection", keep_geom_type=True
    )
    if shared.empty:
        return None
    areas = [
        shapes[entity].to_crs(EQUAL_AREA_CRS).area.sum()
        for entity in (code, other)
    ]
    shared_area = shared.to_crs(EQUAL_AREA_CRS).area.sum()
    if shared_area < MINIMUM_SHARED_AREA * min(areas):
        return None

    shares = []
    for entity in (code, other):
        grid_code = grid_codes[entity]
        if grid_code not in grids:
            grids[grid_code] = retrievals.gridded_totals.open_gridded_data(
                "population", grid_code, POPULATION_YEAR
            )
        people = utils.geospatial.get_total_in_shape(
            grids[grid_code], shapes[entity]
        )
        people_in_shared_area = utils.geospatial.get_total_in_shape(
            grids[grid_code], shared
        )
        shares.append(people_in_shared_area / people if people > 0 else 0.0)
    return shares[0], shares[1]


def get_shares(codes: list[str]) -> pd.DataFrame:
    """
    Get the shares of the people of the pairs of entities that overlap.

    Parameters
    ----------
    codes : list[str]
        The codes of the countries and subdivisions.

    Returns
    -------
    pandas.DataFrame
        For each pair of entities of the same country that overlap, the
        codes of the entity and of the related one, the share of the
        people of each in the shared area, and whether they are related.
    """
    by_country: dict[str, list[str]] = {}
    for code in sorted(codes):
        by_country.setdefault(code.split("_")[0], []).append(code)

    with_gridded_data = set(
        utils.availability.read_codes_with_historical_data()
    )
    grid_codes = {
        code: code if code in with_gridded_data else code.split("_")[0]
        for code in codes
    }

    rows = []
    for country_codes in by_country.values():
        if len(country_codes) < 2:
            continue
        shapes = {
            code: utils.shapes.get_entity_shape(code, make_plot=False)
            for code in country_codes
        }
        grids: dict[str, xarray.DataArray] = {}
        for code, other in itertools.combinations(country_codes, 2):
            shares = _get_shares(code, other, shapes, grids, grid_codes)
            if shares is None:
                continue
            logging.info(
                f"{code} and {other} share {shares[0]:.1%} and "
                f"{shares[1]:.1%} of their people."
            )
            rows.append(
                {
                    "Entity code": code,
                    "Other code": other,
                    "Share of entity": round(shares[0], 4),
                    "Share of other": round(shares[1], 4),
                    "Related": utils.relations.is_related(*shares),
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "Entity code",
            "Other code",
            "Share of entity",
            "Share of other",
            "Related",
        ],
    )


def run_check() -> None:
    """
    Compute the shares of the entities with data and save them.

    The entities are the countries and subdivisions in the yaml files of
    the data sources.
    """
    shares = get_shares(
        utils.data_sources.read_all_codes_with_electricity_demand_data()
    )
    file_path = utils.relations.get_shares_file()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    shares.to_csv(file_path, index=False)
    logging.info(
        f"{int(shares['Related'].sum())} pairs of related entities, of "
        f"{len(shares)} that overlap, saved to {file_path}."
    )
