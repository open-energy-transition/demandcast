"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the New Brunswick Power Corporation
    (NB Power) in Canada. The data is retrieved for the years from 2019,
    the first year of the archive, to current year. The data is
    retrieved in one-month intervals.

    Source: https://tso.nbpower.com/Public/en/system_information_archive.aspx
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
    logging.debug("All rights reserved by NB Power.")
    logging.debug("Source: https://www.nbpower.com/en/terms-of-use")
    return False


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[int, int]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the NB Power website.

    Parameters
    ----------
    code : str
        The code of New Brunswick.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[int, int]]
        The list of available requests.
    """
    # Get the list of available requests, which are the years and
    # months.
    values_list = (
        pd.date_range(start=start_date, end=end_date, freq="ME")
        .strftime("%Y-%m")
        .str.split("-")
        .tolist()
    )

    # Return the available requests, which are tuples in the format
    # (year, month).
    return [(int(year), int(month)) for year, month in values_list]


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the NB Power website.

    Returns
    -------
    str
        The URL of the electricity demand data
    """
    # Return the URL of the electricity demand data.
    return "https://tso.nbpower.com/Public/en/system_information_archive.aspx"


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the NB Power website.

    Parameters
    ----------
    year_and_month : tuple[int, int]
        The year and month of the electricity demand data.
    code : str
        The code of New Brunswick.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    year, month = year_and_month

    logging.info(
        "Retrieving electricity demand data for the "
        f"year {year} and month {month}."
    )

    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch HTML content from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.post",
        post_data_params={
            "__EVENTTARGET": "ctl00$cphMainContent$lbGetData",
            "ctl00$cphMainContent$ddlMonth": month,
            "ctl00$cphMainContent$ddlYear": year,
        },
        query_aspx_webpage=True,
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series. The times mark the
    # end of each hour: each value is the average of the hour before its
    # time, as the 5-minute data of New Brunswick from CCEI show.
    electricity_demand_time_series = pd.Series(
        dataset["NB_LOAD"].values,
        index=pd.to_datetime(dataset["HOUR"].values, format="%Y-%m-%d %H:%M"),
    )

    # Localize the times, which follow daylight saving time: when it
    # ends, 01:00 comes twice.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize(
            "America/Moncton", ambiguous="infer"
        )
    )

    return electricity_demand_time_series
