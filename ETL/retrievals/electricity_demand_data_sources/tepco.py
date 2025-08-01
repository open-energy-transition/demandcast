# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Tokyo Electric Power Company (TEPCO) in
    Japan. The data is retrieved for the years from 2016 to the current
    year. The data is retrieved from the available CSV files on the
    TEPCO website.

    Source: https://www4.tepco.co.jp/en/forecast/html/download-e.html
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
    logging.debug("Personal use only. Redistribution is not allowed.")
    logging.debug("Source: https://www4.tepco.co.jp/en/pg/legal/index-e.html")
    return False


def _check_input_parameters(year: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    """
    # Check if the year is supported.
    assert year in get_available_requests(), (
        f"The year {year} is not in the supported range."
    )


def get_available_requests() -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the TEPCO website.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="tepco"
    )["JP_Kantō"]

    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the TEPCO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if input parameters are valid.
    _check_input_parameters(year)

    # Return the URL of the electricity demand data.
    return f"https://www4.tepco.co.jp/forecast/html/images/juyo-{year}.csv"


def download_and_extract_data_for_request(year: int) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the TEPCO website.

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

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.get",
        read_as="tabular",
        csv_kwargs={"skiprows": 2},
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Define the index of the time series.
        index = pandas.to_datetime(
            [
                date + " " + time
                for date, time in zip(dataset["DATE"], dataset["TIME"])
            ]
        ).tz_localize("Asia/Tokyo")

        # Extract the electricity demand time series. Multiply by 10 to
        # convert from 10,000 kW (Japanese way of expressing unit of
        # power) to MW.
        electricity_demand_time_series = (
            pandas.Series(dataset["ÀÑ(kW)"].values, index=index) * 10
        )

        # Add one hour to the time index because the time values appear
        # to be provided at the beginning of the time interval.
        electricity_demand_time_series.index += pandas.Timedelta(hours=1)

        return electricity_demand_time_series
