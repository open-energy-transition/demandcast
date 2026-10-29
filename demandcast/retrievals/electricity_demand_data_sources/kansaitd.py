"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Kansai Transmission and Distribution
    (KansaiTD) in Japan. The data is retrieved from the available CSV
    files on the KansaiTD website.

    The files of the years until 2023 are fiscal years, from April to
    March, the first one from April 2016, and give the area demand in
    MWh of each hour. The last one ends in February 2024, and the
    monthly files from March 2024 give the average area demand in MW of
    each half hour. The days of both start at 00:00, so the times are
    the starts of the intervals, in the time of Japan, which has no
    daylight saving time. OCCTO republishes the same demand (see
    occto.py).

    The area demand counts the solar fed into the networks, but not the
    solar that the consumers of the surplus purchase scheme use
    themselves, which lowers the area demand: Kyushu states it for the
    national format ("「エリア需要」および「太陽光」には、
    余剰買取による太陽光発電の自家消費分は含んでいません"), so the
    embedded generation is partial in the YAML file.

    Source: https://www.kansai-td.co.jp/english/home/denkiyoho/area-performance/index.html
    Source: https://www.kyuden.co.jp/td_area_jukyu/jukyu.html
"""

import datetime
import logging

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[int, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the KansaiTD website.

    Parameters
    ----------
    code : str
        The code of the Kansai region.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[int, int | None]]
        The list of available requests.
    """
    # Define the date that separates the two types of requests.
    march_2024 = pd.Timestamp("2024-03-01")

    # Requests before March 2024.
    requests_before: list[tuple[int, int | None]] = [
        (year, None) for year in range(start_date.year, march_2024.year)
    ]

    # Requests after March 2024
    requests_after: list[tuple[int, int | None]] = [
        (year, month)
        for year in range(march_2024.year, end_date.year + 1)
        for month in range(1, 13)
        if (year < end_date.year or month <= end_date.month)
        and (year > march_2024.year or month >= march_2024.month)
    ]

    # Return the list of available requests.
    return requests_before + requests_after


def get_url(year: int, month: int | None) -> str:
    """
    Get the URL of the electricity demand data on the KansaiTD website.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Define the URL of the electricity demand data.
    if month is None:
        url = (
            "https://www.kansai-td.co.jp/"
            "denkiyoho/area-performance/csv/"
            f"area_jyukyu_jisseki_{year:04d}.csv"
        )
    else:
        url = (
            "https://www.kansai-td.co.jp/"
            "interchange/denkiyoho/area-performance/"
            f"eria_jukyu_{year:04d}{month:02d}_06.csv"
        )

    return url


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int | None], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the KansaiTD website.

    Parameters
    ----------
    year_and_month : tuple[int, int | None]
        The year and month of the data to retrieve, without a month
        before March 2024.
    code : str
        The code of the Kansai region.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    year, month = year_and_month

    if month is None:
        logging.info(
            f"Retrieving electricity demand data for the year {year}."
        )
    else:
        logging.info(
            f"Retrieving electricity demand data for the year {year} and "
            f"month {month}."
        )

    # Get the URL of the electricity demand data.
    url = get_url(year, month)

    # Determine number of rows to skip.
    skip_rows = 3 if year == 2021 else 1

    # Fetch CSV content from the URL with proper encoding.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "csv",
        csv_kwargs={
            "skiprows": skip_rows,
            "encoding": "cp932",
        },  # Japanese encoding
    )

    if month is None:
        # Extract the electricity demand time series.
        electricity_demand_time_series = pd.Series(
            dataset["エリア需要〔MWh〕"].values,
            index=pd.to_datetime(dataset["DATE_TIME"]),
        )

        # The times are the starts of the hours.
        interval = pd.Timedelta(hours=1)

    else:
        # Convert date and hour columns into hourly timestamps.
        index = pd.to_datetime(dataset["DATE"]) + pd.to_timedelta(
            dataset["TIME"].astype(str) + ":00"
        )

        # Extract the electricity demand time series.
        electricity_demand_time_series = pd.Series(
            dataset["エリア需要"].values,
            index=index,
        )

        # The times are the starts of the half hours.
        interval = pd.Timedelta(minutes=30)

    # Move the times to the ends of the intervals, in Japan time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series, "Asia/Tokyo", interval
        )
    )

    return electricity_demand_time_series
