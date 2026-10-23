"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Thailand from a publicly available repository containing
    data from the Electricity Generating Authority of Thailand (EGAT).
    The data is retrieved one year at a time.

    The files give the hourly generation and demand of the five regions
    of Thailand, and the exchanges with the neighbouring countries, in
    MW, in the time of Thailand, which has no daylight saving time. The
    demand is the sum of the regions. Each file starts at 00:05 of its
    first day and ends with the first day of the next year, which is
    the same in both files.

    Source: https://zenodo.org/records/17109911
"""

import datetime
import logging

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from EGAT.

    Parameters
    ----------
    code : str
        The code of Thailand.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


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
    # Return the URL of the electricity demand data.
    return (
        "https://zenodo.org/records/17109911/files/"
        f"system_{year}.csv?download=1"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from EGAT.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Thailand.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_dataframe(url, "csv")

    # Sum the regional demand columns to get total national demand.
    dataset["National Demand"] = (
        dataset["north_demand"]
        + dataset["south_demand"]
        + dataset["metropolitan_demand"]
        + dataset["central_demand"]
        + dataset["northeast_demand"]
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["National Demand"].values,
        index=pd.to_datetime(dataset["datetime"], format="%d/%m/%Y %H:%M"),
    )

    # The file does not say if its times are the starts or the ends of
    # the hours. The dip of the lunch break, from 12:00 to 13:00 in
    # Thailand, falls on the times of 12:00, which fits starts. Move
    # them to the ends of the hours.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Asia/Bangkok",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
