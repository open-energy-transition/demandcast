"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Grupo ICE (GRUPOICE) in Costa Rica.
    The data is retrieved in one-year intervals.

    Source: https://apps.grupoice.com/CenceWeb
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
    demand data from the GRUPOICE website.

    Parameters
    ----------
    code : str
        The code of Costa Rica.
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
    Get the URL of the electricity demand data on the GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Construct the URL for the request.
    return (
        "https://apps.grupoice.com/CenceWeb/data/sen/csv/DemandaMW?intervalo=15&"
        f"inicio={year}0101&fin={year}1231"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Costa Rica.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_as="csv_table",
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["MW"].values,
        index=pd.to_datetime(dataset["fechaHora"]),
    )

    # Add 15 minutes to each timestamp to represent the end of the time
    # period.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "America/Costa_Rica",
            pd.Timedelta(minutes=15),
        )
    )

    return electricity_demand_time_series
