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

import datetime
import logging

import pandas as pd
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

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

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

    # Add one hour to the index because the electricity demand seems
    # to be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pd.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Asia/Bangkok")
    )

    return electricity_demand_time_series
