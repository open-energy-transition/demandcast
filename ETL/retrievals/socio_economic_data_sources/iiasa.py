# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module is used to read Excel files already downloaded from the
    Shared Socioeconomic Pathways (SSP) database of the International
    Institute for Applied Systems Analysis (IIASA). The files contain
    future projections of population, electricity demand per capita and
    GDP PPP per capita for different scenarios.

    Source: https://tntcat.iiasa.ac.at/SspDb
"""

import os

import pandas
import yaml


def _get_iam_region(iso_alpha_3_code: str, n_regions: int) -> str:
    """
    Get the IAM region for a given ISO Alpha-3 country code.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 country code.
    n_regions : int
        The number of IAM regions available.

    Returns
    -------
    iam_region : str
        The corresponding IAM region.

    Raises
    ------
    ValueError
        If no IAM region is found for the given ISO Alpha-3 code.
    """
    # Define the path to the yaml file containing the mapping of ISO
    # Alpha-3 codes to IAM regions.
    iam_region_mapping = os.path.join(
        os.path.dirname(__file__), f"iam_{n_regions}_regions_mapping.yaml"
    )

    # Read the mapping from the yaml file.
    with open(iam_region_mapping, "r", encoding="utf-8") as file:
        iso_to_region = yaml.safe_load(file)

    # Get the IAM region for the given ISO Alpha-2 code.
    region_code = iso_to_region.get(iso_alpha_3_code, None)

    if region_code is None:
        raise ValueError(
            f"No IAM region found for ISO Alpha-3 code: {iso_alpha_3_code}"
        )

    return region_code


def _calculate_values_from_growth_rate(
    last_historical_value: float,
    last_historical_year: int,
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
    previous_year = last_historical_year

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
        ) ** (year - previous_year)

        # Update the previous value.
        previous_value = future_values[year]
        previous_year = year

    return future_values


def get(
    variable: str,
    iso_alpha_3_code: str = "",
    scenario: str = "",
    last_historical_value: float = 0.0,
    last_historical_year: int = 0,
    future_years: list[int] = [],
) -> pandas.Series:
    """
    Get the future data from IIASA.

    Future data of population, electricity demand per capita and GDP PPP
    per capita for different scenarios are calculated based on growth
    rates provided in Excel files already downloaded from the Shared
    Socioeconomic Pathways (SSP) database of the International Institute
    for Applied Systems Analysis (IIASA). The function first looks for
    the growth rates corresponding to the country and scenario of
    interest, and then applies them to the last historical value to
    obtain the future values. If the country is not available, the
    function looks for the corresponding IAM region and uses the growth
    rates of the region instead.

    Parameters
    ----------
    variable : str
        The variable to get. It can be either
        "population", "electricity_demand_per_capita" or
        "gdp_ppp_per_capita".
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.
    scenario : str
        The scenario of interest.
    last_historical_value : float
        The last historical value of the variable of interest.
    last_historical_year : int
        The year of the last historical value.
    future_years : list[int]
        The list of future years where the variable of interest is to be
        projected.

    Returns
    -------
    pandas.Series
        The future data from IIASA with years as index.

    Raises
    ------
    ValueError
        If the variable is not one of the expected values, or if no data
        is found for the given country and scenario.
    """
    # Define the file of the future data to be read.
    if variable == "population":
        files_of_interest = [
            "IAM_national_population_growth.xlsx",
            "IAM_32_regional_population_growth.xlsx",
        ]
    elif variable == "annual_electricity_demand_per_capita":
        files_of_interest = [
            "IAM_5_regional_annual_electricity_demand_per_capita_growth.xlsx",
        ]
    elif variable == "gdp_ppp_per_capita":
        files_of_interest = [
            "IAM_national_gdp_ppp_per_capita_growth.xlsx",
            "IAM_32_regional_gdp_ppp_per_capita_growth.xlsx",
        ]
    else:
        raise ValueError(
            "The variable must be either "
            "'population', 'electricity_demand_per_capita' or "
            "'gdp_ppp_per_capita'."
        )

    # Initialize an empty DataFrame to store the annual growth rates.
    annual_growth_rate = pandas.DataFrame()

    for file_of_interest in files_of_interest:
        # Define the file path of the future data to be read.
        file_path = os.path.join(
            os.path.dirname(__file__),
            "manual_downloads",
            file_of_interest,
        )

        # Read the Excel file.
        annual_growth_rate_in_file = pandas.read_excel(
            file_path,
            sheet_name="data",
            index_col=0,
        )

        annual_growth_rate = pandas.concat(
            [annual_growth_rate, annual_growth_rate_in_file],
            ignore_index=True,
        )

    if iso_alpha_3_code not in annual_growth_rate["Region"].to_list():
        # Get the number of regions in the file name.
        n_regions = int(file_of_interest.split("_")[1])

        # Get the code of the region of interest.
        code_of_interest = _get_iam_region(
            iso_alpha_3_code,
            n_regions=n_regions,
        )
    else:
        code_of_interest = iso_alpha_3_code

    # Extract the data for the country and scenario of interest.
    annual_growth_rate = annual_growth_rate[
        (annual_growth_rate["Region"] == code_of_interest)
        & (annual_growth_rate["Scenario"] == scenario)
    ]

    # Check that there is only one row.
    if len(annual_growth_rate) != 1:
        raise ValueError(
            f"Expected one row for country {iso_alpha_3_code} and scenario "
            f"{scenario}, but got {len(annual_growth_rate)}."
        )

    # Convert to a Series with years as index by selecting only the
    # columns that are digits and dropping NaN values.
    annual_growth_rate = annual_growth_rate.iloc[
        0,
        annual_growth_rate.columns.astype(str).str.isdigit(),
    ].dropna()

    # Calculate the future data by applying the annual growth rates to
    # the last historical value.
    return _calculate_values_from_growth_rate(
        last_historical_value,
        last_historical_year,
        future_years,
        annual_growth_rate,
    )
