"""
License: AGPL-3.0.

Description:

    This module gives the totals of the gridded population and GDP PPP
    of a country or subdivision, for the indicators of subdivisions
    that have no national data (see retrievals/population.py and
    retrievals/gdp_ppp_per_capita.py).

    The gridded data of the years of the grids that cover the selected
    years is retrieved if it is missing, summed within the shape of the
    country or subdivision, and interpolated to each year.
"""

import os
from typing import Literal, cast

import pandas as pd
import utils.geospatial
import utils.paths
import utils.shapes
import xarray

import retrievals.gridded_gdp_ppp
import retrievals.gridded_population

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
    scenario : str
        The scenario of the data to be retrieved.

    Returns
    -------
    float
        The total value of the variable for the country or subdivision.
    """
    # Define the path to the gridded data.
    gridded_data_path = utils.paths.get_gridded_file(
        cast(Literal["population", "gdp_ppp"], variable), code, year, scenario
    )

    if not os.path.exists(gridded_data_path):
        # Run the retrieval of the gridded data.
        RETRIEVALS[variable].run_data_retrieval(
            code=code,
            file=None,
            year=year,
            start_year=None,
            end_year=None,
            scenario=scenario,
        )

    # Sum the grid cells within the shape of the country or
    # subdivision.
    with xarray.open_dataarray(gridded_data_path) as gridded_data:
        return utils.geospatial.get_total_in_shape(
            gridded_data,
            utils.shapes.get_entity_shape(code, make_plot=False),
        )


def _select_years_of_gridded_data(
    available_years_of_gridded_data: list[int],
    selected_years: list[int],
) -> list[int]:
    """
    Select the years of gridded data.

    The function selects the years of gridded data that cover the
    years of interest. It finds the first year of available gridded
    data that is less than or equal to the minimum selected year and
    the last year of available gridded data that is greater than or
    equal to the maximum selected year.

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
    # Get the first year of available gridded data that is less than
    # or equal to the minimum selected year.
    first_selected_year_of_gridded_data = max(
        year
        for year in available_years_of_gridded_data
        if year <= min(selected_years)
    )

    # Get the last year of available gridded data that is greater than
    # or equal to the maximum selected year.
    last_selected_year_of_gridded_data = min(
        year
        for year in available_years_of_gridded_data
        if year >= max(selected_years)
    )

    # Select and return the years of gridded data that cover the years
    # of interest.
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
) -> pd.Series:
    """
    Get the total value of a variable from gridded data.

    This function retrieves the total value of a specified variable
    (e.g., population or GDP PPP) for a given country or subdivision
    over a range of selected years. It utilizes gridded data files,
    which are aggregated based on the provided shape of the country or
    subdivision. The function can handle both historical data and
    future projections based on scenarios.

    Parameters
    ----------
    variable : str
        The variable to retrieve. It can be either "population" or
        "gdp_ppp".
    code : str
        The code of the subdivision of interest.
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

    Returns
    -------
    pandas.Series
        The total value of the variable for the selected years.

    Raises
    ------
    ValueError
        If the variable is not "population" or "gdp_ppp".
        If only one of scenario or
        last_available_historical_years_of_gridded_data is provided.
        If last_available_historical_years_of_gridded_data is greater
        than the minimum available year of gridded data.
    """
    if variable not in ["population", "gdp_ppp"]:
        raise ValueError(
            "The variable must be either 'population' or 'gdp_ppp'."
        )

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
        > min(available_years_of_gridded_data)
    ):
        raise ValueError(
            "last_available_historical_years_of_gridded_data must be less "
            "than the minimum available (future) year of gridded data."
        )

    # If an extra available year of gridded data is provided, add it
    # to the list of available years of gridded data.
    if last_available_historical_years_of_gridded_data:
        available_years_of_gridded_data = [
            last_available_historical_years_of_gridded_data,
            *available_years_of_gridded_data,
        ]

    # Sort the available years of gridded data.
    available_years_of_gridded_data.sort()

    # Get years of available gridded data that cover the selected years.
    selected_years_of_gridded_data = _select_years_of_gridded_data(
        available_years_of_gridded_data,
        selected_years,
    )

    # Initialize the list to store the total values.
    total_value_list = []

    for year in selected_years_of_gridded_data:
        if (
            last_available_historical_years_of_gridded_data
            and year == last_available_historical_years_of_gridded_data
        ):
            # Extract the total value for the last year of
            # historical gridded data without scenario.
            total_value_list.append(
                _aggregate_gridded_data(variable, code, year, scenario=None)
            )
        else:
            # Extract the total value for the year and
            # scenario of interest.
            total_value_list.append(
                _aggregate_gridded_data(
                    variable, code, year, scenario=scenario
                )
            )

    # Construct a Series with the total values and the selected
    # years of gridded data as index.
    total_values = pd.Series(
        data=total_value_list,
        index=selected_years_of_gridded_data,
    )

    # Set the name of the Series and its index.
    total_values.index.name = "Year"
    if variable == "population":
        total_values.name = "Population"
    elif variable == "gdp_ppp":
        total_values.name = "GDP PPP"

    # Interpolate to the selected years and return it.
    return total_values.reindex(
        list(
            range(
                total_values.index.min(),
                total_values.index.max() + 1,
            )
        )
    ).interpolate()
