"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data from the website
    of Kansai Transmission and Distribution (KansaiTD) in Japan. The
    data is retrieved from the available CSV files on the KansaiTD
    website.

    The files of the years until 2023 are fiscal years, from April to
    March, the first one from April 2016, and give the area demand in
    MWh of each hour. The last one ends in February 2024, and the
    monthly files from March 2024 give the average area demand in MW of
    each half hour. The days of both start at 00:00, so the times are
    the starts of the intervals, in the time of Japan, which has no
    daylight saving time. OCCTO republishes the same demand (see
    occto.py).

    The area demand leaves out the solar that the consumers use
    themselves, as in the national format (see occto.py), so the
    embedded generation is partial in the YAML file.

    Source: https://www.kansai-td.co.jp/english/home/denkiyoho/area-performance/index.html
"""

import datetime as dt
import logging

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[int, int | None]]:
    """
    Get the available requests.

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
        The year and month of each file, without a month for the files
        of the fiscal years before March 2024.
    """
    march_2024 = pd.Timestamp("2024-03-01")

    requests_before: list[tuple[int, int | None]] = [
        (year, None) for year in range(start_date.year, march_2024.year)
    ]

    requests_after: list[tuple[int, int | None]] = [
        (year, month)
        for year in range(march_2024.year, end_date.year + 1)
        for month in range(1, 13)
        if (year < end_date.year or month <= end_date.month)
        and (year > march_2024.year or month >= march_2024.month)
    ]

    return requests_before + requests_after


def get_url(year: int, month: int | None) -> str:
    """
    Get the URL of the electricity demand data on the KansaiTD website.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve, or None for a yearly file.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
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

    Notes
    -----
    The file of 2021 has three rows before its header, and the other
    files one.
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

    url = get_url(year, month)

    skip_rows = 3 if year == 2021 else 1

    dataset = utils.fetcher.fetch_dataframe(
        url,
        "csv",
        csv_kwargs={
            "skiprows": skip_rows,
            "encoding": "cp932",
        },  # Japanese encoding
    )

    if month is None:
        electricity_demand_time_series = pd.Series(
            dataset["エリア需要〔MWh〕"].values,
            index=pd.to_datetime(dataset["DATE_TIME"]),
        )

        # The times are the starts of the hours.
        interval = pd.Timedelta(hours=1)

    else:
        # The times are the starts of the half hours, such as "0:30".
        index = pd.to_datetime(dataset["DATE"]) + pd.to_timedelta(
            dataset["TIME"].astype(str) + ":00"
        )

        electricity_demand_time_series = pd.Series(
            dataset["エリア需要"].values,
            index=index,
        )

        interval = pd.Timedelta(minutes=30)

    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series, "Asia/Tokyo", interval
        )
    )

    return electricity_demand_time_series
