"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Energy Market Authority (EMA) in
    Singapore. The data is retrieved in one-week intervals.

    The weekly files give the system demand in MW of each half hour, at
    its end ("Period Ending Time") in the time of Singapore, which has
    no daylight saving time, from 00:30 to 00:00 of the next day. The
    system demand includes the demand of the consumers with their own
    embedded generators. The file of the week of 2014-11-03 gives only
    the NEM demand, which leaves them out and is about 3% lower.

    Note:
    Although data is retrieved in 7-day intervals, retrieving data
    over a longer historical range (e.g., multiple years) may take
    considerable time — up to 10 minutes in total.

    Source: https://www.ema.gov.sg/resources/statistics/half-hourly-system-demand-data
"""

import calendar
import datetime as dt
import logging

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[int, int, int]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of Singapore.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    requests : list[tuple[int, int, int]]
        List of tuples in the format (year, month, day).

    Notes
    -----
    The requests end one week before the end date, so that the last one
    is within the available data, and leave out the weeks whose files
    are not on the EMA website.
    """
    end_date = end_date - pd.Timedelta("7days")

    dates_not_available = [
        pd.Timestamp("2014-12-01"),
        pd.Timestamp("2014-12-08"),
        pd.Timestamp("2014-12-29"),
        pd.Timestamp("2015-01-12"),
        pd.Timestamp("2015-01-19"),
        pd.Timestamp("2015-01-26"),
        pd.Timestamp("2015-02-02"),
        pd.Timestamp("2015-02-09"),
        pd.Timestamp("2015-02-16"),
        pd.Timestamp("2015-02-23"),
        pd.Timestamp("2015-03-02"),
        pd.Timestamp("2015-03-09"),
        pd.Timestamp("2015-04-06"),
        pd.Timestamp("2015-04-13"),
    ]

    return [
        (date.year, date.month, date.day)
        for date in pd.date_range(start=start_date, end=end_date, freq="7D")
        if date not in dates_not_available
    ]


def get_url(year: int, month: int, day: int) -> str:
    """
    Get the URL of the electricity demand data on the EMA website.

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
    request_date = pd.Timestamp(year=year, month=month, day=day)

    base_url = (
        "https://www.ema.gov.sg/content/dam/corporate/resources/statistics/"
        "half-hourly-data/"
    )

    if request_date < pd.Timestamp("2014-12-15"):
        month_abbr = calendar.month_abbr[month]
        return base_url + f"{year}/{day:02d}_{month_abbr}_{year}.xls"
    if request_date == pd.Timestamp(
        "2025-01-13"
    ) or request_date == pd.Timestamp("2025-01-20"):
        return base_url + f"{year}/{year}{month:02d}{day:02d}.xlsx"
    return base_url + f"{year}/{year}{month:02d}{day:02d}.xls"


def download_and_extract_data_for_request(
    year_month_and_day: tuple[int, int, int], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data from EMA website.

    Parameters
    ----------
    year_month_and_day : tuple[int, int, int]
        The year, month and day of the data.
    code : str
        The code of Singapore.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    The columns of the values also hold the dates and the titles above
    them, so pandas reads them as objects, which are then converted to
    numbers.
    """
    year, month, day = year_month_and_day

    logging.info(
        f"Retrieving electricity demand data for {year}-{month:02d}-{day:02d}."
    )

    url = get_url(year, month, day)

    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_as="excel_table",
        header_params={"User-Agent": "Mozilla/5.0"},
        get_cookies=True,
    )

    # Keep the 48 rows of the half hours, from the one ending at 00:30.
    start_row = dataset[dataset.iloc[:, 0] == "00:30"].index[0]
    dataset = dataset.iloc[start_row : start_row + 48, :]

    request_date = pd.Timestamp(year=year, month=month, day=day)

    # Keep only the columns with system demand data.
    if request_date == pd.Timestamp("2014-11-03"):
        dataset = dataset.iloc[:, [1 + 2 * i for i in range(7)]]
    elif request_date <= pd.Timestamp("2014-09-22"):
        dataset = dataset.iloc[:, 1:8]
    else:
        dataset = dataset.iloc[:, [1 + 3 * i for i in range(7)]]

    dataset = dataset.apply(pd.to_numeric)

    # Add a column for the hour of the day.
    dataset["Hour"] = pd.date_range(
        "00:00", periods=48, freq="30min"
    ).strftime("%H:%M")

    dataset.columns = [
        date.strftime("%Y-%m-%d")
        for date in pd.date_range(start=request_date, periods=7)
    ] + ["Hour"]

    # Reshape the dataset from wide to long format.
    dataset = dataset.melt(id_vars="Hour", var_name="Date", value_name="Value")

    # Define the electricity demand time series, at the starts of the
    # half hours.
    electricity_demand_time_series = pd.Series(
        dataset["Value"].values,
        index=pd.to_datetime(
            dataset["Date"] + " " + dataset["Hour"], format="%Y-%m-%d %H:%M"
        ),
    )

    # Move the times from the starts to the ends of the half hours.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Asia/Singapore",
            pd.Timedelta(minutes=30),
        )
    )

    return electricity_demand_time_series
