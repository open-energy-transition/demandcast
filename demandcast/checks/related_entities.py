"""
License: AGPL-3.0.

Description:

    This module computes which countries and subdivisions with
    electricity demand data share people: for each pair of entities of
    the same country whose shapes overlap, the share of the people of
    each one that live in the area that they share, from the gridded
    population of the year POPULATION_YEAR, summed over the cells of 30
    arc seconds whose centers are in the shapes (see
    retrievals.gridded_population.get_total_in_geometry).

    The shares are saved to related_entities.csv in the folder of the
    checks, one row per pair, with whether the pair is related (see
    utils/relations.py). Pairs whose shared area is under
    MINIMUM_SHARED_AREA of the area of the smaller entity, such as
    neighbours whose shapes touch, are left out. The codes of all the
    entities considered are saved to related_entities_codes.txt, next
    to it, so that a code added to a data source later is noticed.
"""

import itertools
import logging
import os
import pathlib

import geopandas
import pandas as pd

import retrievals.gridded_population
import utils.data_sources
import utils.files
import utils.relations
import utils.shapes

# The year of the gridded population.
POPULATION_YEAR = 2020

# The share of the area of the smaller entity from which a shared area
# counts.
MINIMUM_SHARED_AREA = 0.001

# The equal-area projection in which the areas are compared.
EQUAL_AREA_CRS = "EPSG:6933"


def _count_people(shape: geopandas.GeoDataFrame) -> float:
    """
    Count the people in a shape in the year POPULATION_YEAR.

    Parameters
    ----------
    shape : geopandas.GeoDataFrame
        The shape, in longitude and latitude.

    Returns
    -------
    float
        The population of the cells of the global grid whose centers are
        in the shape.
    """
    return retrievals.gridded_population.get_total_in_geometry(
        shape.union_all(), POPULATION_YEAR, None
    )


def _get_shares(
    code: str,
    other: str,
    shapes: dict[str, geopandas.GeoDataFrame],
    people: dict[str, float],
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
    people : dict[str, float]
        The people of each entity counted so far, to which those of the
        two entities are added.

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

    people_in_shared_area = _count_people(shared)
    shares = []
    for entity in (code, other):
        if entity not in people:
            people[entity] = _count_people(shapes[entity])
        shares.append(
            people_in_shared_area / people[entity]
            if people[entity] > 0
            else 0.0
        )
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
    rows = []
    for country_codes in by_country.values():
        if len(country_codes) < 2:
            continue
        shapes = {
            code: utils.shapes.get_entity_shape(code, make_plot=False)
            for code in country_codes
        }
        people: dict[str, float] = {}
        for code, other in itertools.combinations(country_codes, 2):
            shares = _get_shares(code, other, shapes, people)
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
    the data sources. Their codes are saved too, one per line, so that
    a test can tell when a data source has a code that was not checked.
    """
    codes = sorted(utils.data_sources.read_all_codes())
    shares = get_shares(codes)
    file_path = utils.relations.get_shares_file()
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with utils.files.writing(file_path) as temporary_path:
        shares.to_csv(temporary_path, index=False)
    codes_path = utils.relations.get_codes_file()
    with utils.files.writing(codes_path) as temporary_path:
        pathlib.Path(temporary_path).write_text(
            "".join(f"{code}\n" for code in codes), encoding="utf-8"
        )
    logging.info(
        f"{int(shares['Related'].sum())} pairs of related entities, of "
        f"{len(shares)} that overlap, saved to {file_path}."
    )
