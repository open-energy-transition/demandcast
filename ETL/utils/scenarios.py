# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module povides utility functions for the data retrieval for
    different scenarios.
"""

import os

import yaml


def get_year_and_scenario_combinations(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    ssp: int | None,
    available_years: list[int],
    available_ssps: list[int],
) -> list[tuple[int, str | None]]:
    """
    Get the list of years and SSP combinations.

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
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.
    available_years : list[int]
        The list of available years for the data retrieval.
    available_ssps : list[int]
        The list of available SSPs for the data retrieval.

    Returns
    -------
    year_scenario_list : list[tuple[int, str | None]]
        A list of tuples, where each tuple contains a year and an
        optional SSP scenario.
    """
    if year is not None:
        assert start_year is None and end_year is None, (
            "If year is specified, start_year and end_year must be None."
        )
        assert year in available_years, (
            f"year must be one of the available years: {available_years}."
        )
        # Use the specified year.
        years = [year]
    elif start_year is not None and end_year is not None:
        assert start_year < end_year, "start_year must be less than end_year."
        assert start_year in available_years, (
            "start_year must be one of the available years: "
            f"{available_years}."
        )
        assert end_year in available_years, (
            f"end_year must be one of the available years: {available_years}."
        )
        # Use the range of years from start_year to end_year.
        years = [y for y in available_years if start_year <= y <= end_year]
    else:
        # Use all available years.
        years = available_years

    if ssp is not None:
        assert ssp in available_ssps, (
            f"ssp must be one of the following: {available_ssps}."
        )
        # Use the specified SSP.
        ssps = [ssp]
    else:
        # Use all available SSPs.
        ssps = available_ssps

    # Create a list of year and SSP combinations.
    year_scenario_list: list[tuple[int, str | None]] = []
    for year in years:
        if year <= 2020:
            year_scenario_list.append((year, None))
        elif year >= 2025:
            for ssp in ssps:
                year_scenario_list.append((year, f"ssp{ssp}"))

    return year_scenario_list


def get_iam_region(iso_alpha_2: str) -> str:
    """
    Get the IAM region for a given ISO Alpha-2 country code.

    Parameters
    ----------
    iso_alpha_2 : str
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
    region_code = iso_to_region.get(iso_alpha_2, None)

    if region_code is None:
        raise ValueError(
            f"No IAM region found for ISO Alpha-2 code: {iso_alpha_2}"
        )

    return region_code
