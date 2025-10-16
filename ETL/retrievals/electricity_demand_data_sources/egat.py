# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Thailand from a publicly available repository containing
    data from the Electricity Generating Authority of Thailand (EGAT).
    The data is available from Jan 1, 2023 to Jan 1, 2025. The data is
    retrieved all at once.

    Source: https://zenodo.org/records/17109911
"""

import logging

import pandas
import utils.entities
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("CC-BY 4.0 license.")
    logging.debug(
        "Source: https://creativecommons.org/licenses/by/4.0/legalcode"
    )
    return True


def _check_input_parameters(year: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    """
    # Check if the year is supported.
    assert year in get_available_requests(), (
        f"The year {year} is not in the supported range."
    )


def get_available_requests() -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from EGAT.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            data_source="thailand"
        )["THA"]
    )

    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data from EGAT.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Check if input parameters are valid.
    _check_input_parameters(year)

    # Return the URL of the electricity demand data.
    return (
        "https://zenodo.org/records/17109911/files/"
        f"system_{year}.csv?download=1"
    )


def download_and_extract_data_for_request(year: int) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from EGAT.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year)

    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Sum the regional demand columns to get total national demand.
        dataset["National Demand"] = (
            dataset["north_demand"]
            + dataset["south_demand"]
            + dataset["metropolitan_demand"]
            + dataset["central_demand"]
            + dataset["northeast_demand"]
        )

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["National Demand"].values,
            index=pandas.to_datetime(dataset["datetime"]),
        )

        # Add one hour to the index because the electricity demand seems
        # to be provided at the beginning of the hour.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index + pandas.Timedelta(hours=1)
        )

        # Add the timezone information to the index.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Asia/Bangkok")
        )

        return electricity_demand_time_series
