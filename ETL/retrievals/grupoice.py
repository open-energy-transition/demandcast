# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Grupo ICE (GRUPOICE) in Costa Rica.
    The data is downloaded from Mar 01, 2012 up to the current date.
    The data is retrieved in one-day intervals.

    Note:
    Retrieving all the data takes a few hours due to the large
    number of CSV files that need to be processed.

    Source: https://apps.grupoice.com/CenceWeb
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
    logging.debug("All rights reserved by GRUPOICE.")
    logging.debug("Source: https://apps.grupoice.com/CenceWeb")
    return False


def _check_input_parameters(year: int, month: int, day: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data.
    month : int
        The month of the data.
    day : int
        The day of the data.
    """
    # Check if the input parameters are valid.
    assert (year, month, day) in get_available_requests(), (
        f"The {year}-{month:02d}-{day:02d} request is not available."
    )


def get_available_requests() -> list[tuple[int, int, int]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the GRUPOICE website.

    Returns
    -------
    requests : list[tuple[int, int, int]]
        List of tuples in the format (year, month, day).
    """
    # Get the start and end dates for Singapore.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="grupoice"
    )["CR"]

    # Subtract 5 days from the end date to ensure that the last
    # request is within the available data range.
    end_date = end_date - pandas.Timedelta("5days")

    # Return the available requests, which are tuples in the format
    # (year, month, day).
    return [
        (date.year, date.month, date.day)
        for date in pandas.date_range(
            start=start_date, end=end_date, freq="1D"
        )
    ]


def get_url(year: int, month: int, day: int) -> str:
    """
    Get the URL of the electricity demand data on the GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the data.
    month : int
        The month of the data.
    day : int
        The day of the data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year, month, day)

    # Construct the URL for the request.
    return (
        "https://apps.grupoice.com/CenceWeb/data/sen/csv/DemandaMW?intervalo=15&"
        f"inicio={year}{month:02d}{day:02d}&fin={year}{month:02d}{day:02d}"
    )


def download_and_extract_data_for_request(
    year: int, month: int, day: int
) -> pandas.Series:
    """
    Download and extract electricity demand data from GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the data.
    month : int
        The month of the data.
    day : int
        The day of the data.

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
    _check_input_parameters(year, month, day)

    logging.info(
        f"Retrieving electricity demand data for {year}-{month:02d}-{day:02d}."
    )

    # Construct the URL for the request.
    url = get_url(year, month, day)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_as="csv_table",
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["MW"].values,
            index=pandas.to_datetime(dataset["fechaHora"]),
        )

        # Add 15 minutes to each timestamp to represent the end of
        # the time period.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index + pandas.Timedelta(minutes=15)
        )

        # Add the timezone information.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize(
                "America/Costa_Rica"
            )
        )

        return electricity_demand_time_series
