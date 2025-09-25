# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Thailand from a publicly available repository developed for
    research purposes. The data is downloaded from Jan 1, 2023 to
    Jan 1, 2025. The data is retrieved all at once.

    Source: https://zenodo.org/records/17109911
"""  # noqa: W505

import logging

import pandas
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


def _check_input_parameters(file_number: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    file_number : int
        The number of the file to read.
    """
    # Check if the file number is supported.
    assert file_number in get_available_requests(), (
        f"File number {file_number} is not supported."
    )


def get_available_requests() -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for Thailand.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Return the available requests, which are the numbers of the Excel
    # files available on the Zenodo website.
    return [1, 2]


def get_url(file_number: int) -> str:
    """
    Get the URL of the electricity demand data for Thailand.

    Parameters
    ----------
    file_number : int
        The number of the file to read.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(file_number)

    # Define the URL of the electricity demand data.
    if file_number == 1:
        url = (
            "https://zenodo.org/records/17109911/files/"
            "system_2023.csv?download=1"
        )
    elif file_number == 2:
        url = (
            "https://zenodo.org/records/17109911/files/"
            "system_2024.csv?download=1"
        )

    return url


def download_and_extract_data_for_request(file_number: int) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    for Thailand.

    Parameters
    ----------
    file_number : int
        The number of the file to read.

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
    _check_input_parameters(file_number)

    logging.info(
        "Retrieving electricity demand data from the "
        f"file number {file_number}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(file_number)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Sum the regional demand columns to get total national demand
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
