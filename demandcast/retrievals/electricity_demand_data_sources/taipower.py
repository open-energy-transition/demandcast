"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Taiwan from a dataset on Zenodo, under the CC BY 4.0
    license, with the data of Taipower on the open data platform of the
    government of Taiwan (data.gov.tw), under the Open Government Data
    License. The data is retrieved all at once, from a single CSV file.

    The file gives the load of the four areas of Taiwan (north, central,
    south and east) in MW every 10 minutes, from 2017-01-01 to
    2022-07-01, in the time of Taiwan, which has no daylight saving
    time. The module sums them. The values are the readings that
    Taipower publishes every 10 minutes, so they are kept at their
    times, including about 300 times that are not on the 10 minutes,
    such as 14:14. The data is missing from 2018-02-02 20:20 to
    2018-02-07 and from 2019-04-10 16:10 to 2019-06-06, and on parts of
    a few other days, such as 2021-05-04.

    Source: https://zenodo.org/records/7537890
"""

import datetime

import pandas as pd
import utils.fetcher


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
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "csv",
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

    # The readings are at their times in Taiwan.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Asia/Taipei")
    )

    return electricity_demand_time_series
