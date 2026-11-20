"""
License: AGPL-3.0.

Description:

    This module gives the totals of the gridded population and GDP PPP
    in the shape of a country or subdivision, interpolated between the
    years of the grids. The population of a subdivision is its share of
    the gridded population of its country times the national
    population. The indicators of the countries without national data,
    and of their subdivisions, come from the totals of their own grids
    (see retrievals/population.py and
    retrievals/gdp_ppp_per_capita.py).
"""

from collections.abc import Callable
from typing import Literal, cast

import pandas as pd
import xarray

import retrievals.gridded
import retrievals.gridded_gdp_ppp
import retrievals.gridded_population
import utils.geospatial
import utils.paths
import utils.shapes

# The retrieval of each gridded variable.
RETRIEVALS = {
    "population": retrievals.gridded_population,
    "gdp_ppp": retrievals.gridded_gdp_ppp,
}


def _aggregate_gridded_data(
    variable: str, code: str, year: int, scenario: str | None
) -> float:
    """
    Aggregate gridded data for a country or subdivision.

    Parameters
    ----------
    variable : str
        The variable to aggregate. Available options are "population"
        and "gdp_ppp".
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the data to be retrieved.
    scenario : str | None
        The scenario of the data to be retrieved.

    Returns
    -------
    float
        The total value of the variable for the country or subdivision.
    """
    return utils.geospatial.get_total_in_shape(
        open_gridded_data(variable, code, year, scenario),
        utils.shapes.get_entity_shape(code, make_plot=False),
    )


def _aggregate_at_native_resolution(
    _variable: str, code: str, year: int, scenario: str | None
) -> float:
    """
    Sum the population of a global grid in a shape at its resolution.

    Parameters
    ----------
    _variable : str
        The variable, "population", the only one summed so.
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the data.
    scenario : str | None
        The scenario of the data, none for a historical year.

    Returns
    -------
    float
        The population of the cells of the global grid whose centers are
        in the shape of the country or subdivision.
    """
    return retrievals.gridded_population.get_total_in_shape(
        code, year, scenario
    )


def _get_aggregation(
    variable: str, at_native_resolution: bool
) -> Callable[[str, str, int, str | None], float]:
    """
    Get the function that sums a gridded variable in a shape.

    Parameters
    ----------
    variable : str
        The variable, "population" or "gdp_ppp".
    at_native_resolution : bool
        Whether the population is summed at the resolution of the global
        grids.

    Returns
    -------
    Callable[[str, str, int, str | None], float]
        The function that sums the variable of a code, year and
        scenario.

    Raises
    ------
    ValueError
        If the variable is not "population" or "gdp_ppp", or is not
        "population" at the native resolution.
    """
    if variable not in ["population", "gdp_ppp"]:
        raise ValueError(
            "The variable must be either 'population' or 'gdp_ppp'."
        )
    if not at_native_resolution:
        return _aggregate_gridded_data
    if variable != "population":
        raise ValueError(
            "Only the population is summed at the native resolution."
        )
    return _aggregate_at_native_resolution


def open_gridded_data(
    variable: str, code: str, year: int, scenario: str | None = None
) -> xarray.DataArray:
    """
    Read the gridded data of a country or subdivision.

    The gridded data in the bounds of the code is extracted first if it
    is not there yet, or not in the bounds of the current shape of the
    code (see retrievals.gridded.is_current).

    Parameters
    ----------
    variable : str
        The variable. Available options are "population" and "gdp_ppp".
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the data.
    scenario : str | None, optional
        The scenario of the data, none for the historical data.

    Returns
    -------
    xarray.DataArray
        The gridded data, loaded in memory.
    """
    gridded_data_path = utils.paths.get_gridded_file(
        cast(Literal["population", "gdp_ppp"], variable), code, year, scenario
    )

    if not retrievals.gridded.is_current(gridded_data_path, code):
        RETRIEVALS[variable].run_data_retrieval(
            code=code,
            file=None,
            year=year,
            start_year=None,
            end_year=None,
            scenario=scenario,
        )

    with xarray.open_dataarray(gridded_data_path) as gridded_data:
        return gridded_data.load()


def _select_years_of_gridded_data(
    available_years_of_gridded_data: list[int],
    selected_years: list[int],
) -> list[int]:
    """
    Select the years of gridded data.

    The selected years cover the years of interest: they go from the
    latest available year not after the first year of interest to the
    earliest available year not before the last one.

    Parameters
    ----------
    available_years_of_gridded_data : list[int]
        The available years of gridded data.
    selected_years : list[int]
        The years of interest.

    Returns
    -------
    list[int]
        The selected years of gridded data.
    """
    first_selected_year_of_gridded_data = max(
        year
        for year in available_years_of_gridded_data
        if year <= min(selected_years)
    )

    last_selected_year_of_gridded_data = min(
        year
        for year in available_years_of_gridded_data
        if year >= max(selected_years)
    )

    return [
        year
        for year in available_years_of_gridded_data
        if first_selected_year_of_gridded_data
        <= year
        <= last_selected_year_of_gridded_data
    ]


def get_total_value_from_gridded_data(
    variable: str,
    code: str,
    selected_years: list[int],
    available_years_of_gridded_data: list[int],
    last_available_historical_years_of_gridded_data: int | None = None,
    scenario: str | None = None,
    at_native_resolution: bool = False,
) -> pd.Series:
    """
    Get the total value of a variable from gridded data.

    Parameters
    ----------
    variable : str
        The variable to retrieve. It can be either "population" or
        "gdp_ppp".
    code : str
        The code of the country or subdivision of interest.
    selected_years : list[int]
        The years of interest.
    available_years_of_gridded_data : list[int]
        The available years of gridded data.
    last_available_historical_years_of_gridded_data :
        int | None, optional
        The last available year of historical gridded data without
        scenario.
    scenario : str | None, optional
        The scenario of interest for future projections.
    at_native_resolution : bool, optional
        Whether the population is summed over the cells of the global
        grids, at their resolution, whose centers are in the shape (see
        retrievals.gridded_population.get_total_in_shape), instead of
        over the cells of the grid of the code, each weighted by its
        fraction in the shape.

    Returns
    -------
    pandas.Series
        The total value of the variable for the selected years.

    Raises
    ------
    ValueError
        If the variable is not "population" or "gdp_ppp", or is not
        "population" at the native resolution.
        If only one of scenario or
        last_available_historical_years_of_gridded_data is provided.
        If last_available_historical_years_of_gridded_data is not
        before the minimum available year of gridded data.

    Notes
    -----
    The gridded data of the years of the grids that cover the selected
    years is retrieved if it is missing, summed within the shape of the
    country or subdivision, and interpolated to each year. For a
    scenario, the last historical year of the grids, without scenario,
    is added before the years of the scenario.
    """
    aggregate = _get_aggregation(variable, at_native_resolution)

    if scenario is None and last_available_historical_years_of_gridded_data:
        raise ValueError(
            "If last_available_historical_years_of_gridded_data is "
            "provided, scenario must also be provided."
        )

    if scenario and not last_available_historical_years_of_gridded_data:
        raise ValueError(
            "If scenario is provided, "
            "last_available_historical_years_of_gridded_data must also be "
            "provided."
        )

    if last_available_historical_years_of_gridded_data and (
        last_available_historical_years_of_gridded_data
        >= min(available_years_of_gridded_data)
    ):
        raise ValueError(
            "last_available_historical_years_of_gridded_data must be less "
            "than the minimum available (future) year of gridded data."
        )

    available_years_of_gridded_data = sorted(available_years_of_gridded_data)
    if last_available_historical_years_of_gridded_data:
        available_years_of_gridded_data.insert(
            0, last_available_historical_years_of_gridded_data
        )

    selected_years_of_gridded_data = _select_years_of_gridded_data(
        available_years_of_gridded_data,
        selected_years,
    )

    total_value_list = []

    for year in selected_years_of_gridded_data:
        if (
            last_available_historical_years_of_gridded_data
            and year == last_available_historical_years_of_gridded_data
        ):
            total_value_list.append(aggregate(variable, code, year, None))
        else:
            total_value_list.append(aggregate(variable, code, year, scenario))

    total_values = pd.Series(
        data=total_value_list,
        index=selected_years_of_gridded_data,
    )

    total_values.index.name = "Year"
    if variable == "population":
        total_values.name = "Population"
    elif variable == "gdp_ppp":
        total_values.name = "GDP PPP"

    return total_values.reindex(
        list(
            range(
                total_values.index.min(),
                total_values.index.max() + 1,
            )
        )
    ).interpolate()
