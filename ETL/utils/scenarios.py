# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module povides utility functions for the data retrieval for
    different scenarios.
"""

import os

import pandas
import yaml


def get_year_and_scenario_combinations(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    available_historical_years: list[int],
    available_future_years: list[int],
    scenario: str | None,
    available_scenarios: list[str],
) -> list[tuple[int, str | None]]:
    """
    Get the list of years and scenario combinations.

    Parameters
    ----------
    year : int | None
        The specific year for which the data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which the data is to be
        downloaded.
    end_year : int | None
        The end year of the range of years for which the data is to be
        downloaded.
    last_year_of_historical_data : int
        The last year for which historical data is available.
    available_years : list[int]
        The list of available years for the data retrieval.
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios : list[str]
        The list of available scenarios for the data retrieval.

    Returns
    -------
    year_scenario_list : list[tuple]
        A list of tuples, where each tuple contains a year and an
        optional scenario.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Get the list of available years.
    available_years = sorted(
        available_historical_years + available_future_years
    )

    if year is not None:
        if start_year is not None or end_year is not None:
            raise ValueError(
                "If year is specified, start_year and end_year must be None."
            )
        if year not in available_years:
            raise ValueError(
                f"year must be one of the available years: {available_years}."
            )
        # Use the specified year.
        years = [year]
    elif start_year is not None and end_year is not None:
        if start_year > end_year:
            raise ValueError("start_year must be less than end_year.")
        if start_year not in available_years:
            raise ValueError(
                "start_year must be one of the available years: "
                f"{available_years}."
            )
        if end_year not in available_years:
            raise ValueError(
                "end_year must be one of the available years: "
                f"{available_years}."
            )
        # Use the range of years from start_year to end_year.
        years = [y for y in available_years if start_year <= y <= end_year]
    elif (start_year is not None and end_year is None) or (
        start_year is None and end_year is not None
    ):
        raise ValueError("Both start_year and end_year must be specified.")
    else:
        # Use all available years.
        years = available_years

    if scenario is not None:
        if scenario.upper() not in available_scenarios:
            raise ValueError(
                "scenario must be one of the following: "
                f"{available_scenarios}."
            )
        # Use the specified scenario.
        scenarios = [scenario.upper()]
    else:
        # Use all available scenarios.
        scenarios = available_scenarios

    # Create a list of year and scenario combinations.
    year_scenario_list: list[tuple[int, str | None]] = []
    for year in years:
        if year in available_historical_years:
            year_scenario_list.append((year, None))
        elif year in available_future_years:
            for scenario in scenarios:
                year_scenario_list.append((year, scenario))

    return year_scenario_list


def get_iam_region(iso_alpha_2_code: str) -> str:
    """
    Get the IAM region for a given ISO Alpha-2 country code.

    Parameters
    ----------
    iso_alpha_2_code : str
        The ISO Alpha-2 country code.

    Returns
    -------
    iam_region : str
        The corresponding IAM region.

    Raises
    ------
    ValueError
        If no IAM region is found for the given ISO Alpha-2 code.
    """
    # Define the path to the yaml file containing the mapping of ISO
    # Alpha-2 codes to IAM regions.
    iam_region_mappping = os.path.join(
        os.path.dirname(__file__), "iam_region_mapping.yaml"
    )

    # Read the mapping from the yaml file.
    with open(iam_region_mappping, "r", encoding="utf-8") as file:
        iso_to_region = yaml.safe_load(file)

    # Get the IAM region for the given ISO Alpha-2 code.
    region_code = iso_to_region.get(iso_alpha_2_code, None)

    if region_code is None:
        raise ValueError(
            f"No IAM region found for ISO Alpha-2 code: {iso_alpha_2_code}"
        )

    return region_code


def calculate_values_from_growth_rate(
    last_historical_value: float,
    future_years: list[int],
    annual_growth_rate: pandas.Series,
) -> pandas.Series:
    """
    Calculate future values based on growth rates.

    Parameters
    ----------
    last_historical_value : float
        The last known historical value.
    future_years : list[int]
        A list of future years for which values need to be calculated.
    annual_growth_rate : pandas.Series
        A Series containing annual growth rates indexed by year.

    Returns
    -------
    future_values : pandas.Series
        A Series containing the calculated future values indexed by
        year.
    """
    # Initialize a Series to store the future values.
    future_values = pandas.Series(
        index=future_years,
        dtype=float,
    )

    # Set the previous value to the last historical value.
    previous_value = last_historical_value

    # Calculate the future values by applying the annual growth rates to
    # the last historical value.
    for year in future_years:
        # Use the closest growth rate that is less than or equal to
        # the year.
        annual_growth_rate_of_year = annual_growth_rate[
            annual_growth_rate.index < year
        ].iloc[-1]

        # Calculate the value for the year.
        future_values[year] = previous_value * (
            1 + annual_growth_rate_of_year / 100
        )

        # Update the previous value.
        previous_value = future_values[year]

    return future_values
