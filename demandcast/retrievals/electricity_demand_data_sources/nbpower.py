"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data from the website
    of the New Brunswick Power Corporation (NB Power) in Canada. The
    data is retrieved in one-month intervals.

    The archive gives the hourly load in MW of each month that has
    ended, by hour ending in Atlantic time with daylight saving time, so
    the file of a month runs from 00:00 of its first day to 23:00 of its
    last day. The current month is not in the archive yet.

    The module reads the NB load (NB_LOAD), which is the NB demand
    (NB_DEMAND) minus the estimated transmission losses, about 3 to
    4% lower. The NB load of CCEI is the same.

    Source: https://tso.nbpower.com/Public/en/system_information_archive.aspx
"""

import datetime as dt
import logging

import pandas as pd

import utils.fetcher

# The time zone of the times of the archive.
TIME_ZONE = "America/Moncton"


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[int, int]]:
    """
    Get the available requests.

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
        The year and month of each month whose last day is between the
        dates.
    """
    values_list = (
        pd.date_range(start=start_date, end=end_date, freq="ME")
        .strftime("%Y-%m")
        .str.split("-")
        .tolist()
    )

    return [(int(year), int(month)) for year, month in values_list]


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the NB Power website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return "https://tso.nbpower.com/Public/en/system_information_archive.aspx"


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

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

    Notes
    -----
    Each value is the average of the hour that ends at its time, as the
    5-minute data of New Brunswick from CCEI shows. When daylight saving
    time ends, 01:00 comes twice, first in daylight time. A time that
    cannot be read, does not exist, or is ambiguous but comes only once
    is dropped, since it cannot be placed.
    """
    year, month = year_and_month

    logging.info(
        "Retrieving electricity demand data for the "
        f"year {year} and month {month}."
    )

    url = get_url()

    dataset = utils.fetcher.fetch_dataframe(
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

    times = pd.DatetimeIndex(
        pd.to_datetime(
            dataset["HOUR"], format="%Y-%m-%d %H:%M", errors="coerce"
        )
    )
    electricity_demand_time_series = pd.Series(
        dataset["NB_LOAD"].to_numpy(),
        index=times.tz_localize(
            TIME_ZONE, ambiguous=~times.duplicated(), nonexistent="NaT"
        ),
    )
    placed = (
        times.duplicated(keep=False)
        | times.tz_localize(
            TIME_ZONE, ambiguous="NaT", nonexistent="NaT"
        ).notna()
    )

    return electricity_demand_time_series[
        electricity_demand_time_series.index.notna() & placed
    ]
