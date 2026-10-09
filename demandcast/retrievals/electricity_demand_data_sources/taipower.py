"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Taiwan from a publicly available repository with data
    provided by Taipower. The data is available from Jan 1, 2017 to
    July 1, 2022. The data is retrieved all at once.

    Note:
    There are missing data from 2018-02-03 to 2018-02-07 and
    2019-04-11 to 2019-06-06.

    Source: https://zenodo.org/records/7537890
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
    logging.debug("CC-BY 4.0 license. Use for any purpose with attribution.")
    logging.debug("Source: https://zenodo.org/records/7537890")
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is retrieved all at once, so there is a single request,
    without parameters.

    Parameters
    ----------
    code : str
        The code of Taiwan.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[None]
        The single request.
    """
    return [None]


def get_url() -> str:
    """
    Get the URL of the electricity demand data for Taiwan.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://zenodo.org/records/7537890/files/loadarea_10min_2017Jan_2022Jun.csv?download=1"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    for Taiwan.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Taiwan.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "csv",
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Sum the regional demand columns to get total national demand
    dataset["National Demand"] = (
        dataset["south"]
        + dataset["north"]
        + dataset["east"]
        + dataset["central"]
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["National Demand"].values,
        index=pd.to_datetime(dataset["datetime"]),
    )

    # Add 10 minutes to the index because the electricity demand
    # seems to be provided at the beginning of the time-interval
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pd.Timedelta(minutes=10)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Asia/Taipei")
    )

    return electricity_demand_time_series
