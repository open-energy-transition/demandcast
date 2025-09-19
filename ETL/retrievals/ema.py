# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Energy Market Authority (EMA) in
    Singapore. The data is downloaded from Jan 06, 2014 up to the
    current date. The data is retrieved in one-week intervals.

    Note:
    Although data is retrieved in 7-day intervals, retrieving data
    over a longer historical range (e.g., multiple years) may take
    considerable time — up to 20 minutes in total.

    Source: https://www.ema.gov.sg/resources/statistics/half-hourly-system-demand-data
"""

import calendar
import logging

import pandas
import utils.entities
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Open data.")
    logging.debug("Source: https://www.ema.gov.sg/terms-of-use")
    return True


def _check_input_parameters(
    pre_reform: bool, year: int, month: str | int, day: int
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    pre_reform : bool
        Indicates if the request is for the pre-reform period
        (until Nov 2014).
    year : int
        The year of the data.
    month : str or int
        The month of the data.
    day : int
        The day of the data.
    """
    if pre_reform and isinstance(month, int):
        month = calendar.month_abbr[month]
    elif not pre_reform and isinstance(month, int):
        month = f"{month:02d}"

    param_tuple = (pre_reform, year, month, f"{int(day):02d}")

    assert param_tuple in get_available_requests(), (
        "Unsupported request: "
        f"{param_tuple}. Allowed: {get_available_requests()}"
    )


def get_available_requests() -> list[tuple[bool, int, str | int, str]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EMA website.

    Returns
    -------
    list of tuple
    """
    start_date, end_date = utils.entities.read_date_ranges(data_source="ema")[
        "SG"
    ]
    post_reform_start = pandas.Timestamp("2014-12-15")
    requests = []

    # Pre-reform dates
    for date in pandas.date_range(
        start=start_date,
        end=post_reform_start - pandas.Timedelta(days=1),
        freq="7D",
    ):
        requests.append(
            (
                True,
                date.year,
                calendar.month_abbr[date.month],
                f"{date.day:02d}",
            )
        )

    # Post-reform dates
    for date in pandas.date_range(
        start=post_reform_start, end=end_date, freq="7D"
    ):
        requests.append(
            (False, date.year, f"{date.month:02d}", f"{date.day:02d}")
        )

    return requests


def get_url(pre_reform: bool, year: int, month: str | int, day: int) -> str:
    """
    Get the URL of the electricity demand data on the PUCSL website.

    Parameters
    ----------
    pre_reform : bool
        Indicates if the request is for the pre-reform period
        (until Nov 2014).
    year : int
        The year of the data.
    month : str or int
        The month of the data.
    day : int
        The day of the data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    _check_input_parameters(pre_reform, year, month, day)

    if pre_reform:
        return (
            "https://www.ema.gov.sg/content/dam/corporate/resources/statistics/half-hourly-data/"
            f"{year}/{int(day):02d}_{month}_{year}.xls"
        )
    else:
        month_str = f"{int(month):02d}"
        return (
            "https://www.ema.gov.sg/content/dam/corporate/resources/statistics/half-hourly-data/"
            f"{year}/{year}{month_str}{int(day):02d}.xls"
        )


def download_and_extract_data_for_request(
    pre_reform: bool, year: int, month: str | int, day: str
) -> pandas.Series:
    """
    Download and extract electricity demand data from EMA.

    Parameters
    ----------
    pre_reform : bool
        Whether the date is pre-reform (before 2014-12-15).
    year : int
        The year of the data.
    month : str or int
        The month of the data.
    day : str
        The day of the data.

    Returns
    -------
    pandas.Series
        Time series of electricity demand in MW (indexed by datetime).
    """
    logging.info(
        f"Retrieving electricity demand data for {year}-{month}-{day}."
    )

    # Construct URL
    url = get_url(pre_reform, year, month, day)

    # Fetch the data from the URL.
    try:
        dataset = utils.fetcher.fetch_data(
            url,
            "html",
            read_as="excel_table",
            header_params={"User-Agent": "Mozilla/5.0"},
            get_cookies=True,
            retries=1,
        )
    except Exception as e:
        logging.error(f"Failed to fetch dataset from {url}: {e}")
        dataset = pandas.DataFrame()

    if dataset.empty:
        logging.warning(
            f"No data returned for {year}-{month}-{day} (pre_reform={pre_reform})."
        )
        return pandas.Series(dtype=float, name="Value")

    # Convert month to integer
    if isinstance(month, int):
        month_int = month
    elif month.isdigit():  # numeric string like "12"
        month_int = int(month)
    else:  # month abbreviation like "Sep"
        month_int = list(calendar.month_abbr).index(month[:3].title())

    # Build request date
    request_date = pandas.Timestamp(
        year=int(year), month=month_int, day=int(day)
    )

    if request_date <= pandas.Timestamp("2014-09-22"):
        dataset = utils.fetcher.fetch_data(
            url,
            "html",
            read_as="excel_table",
            header_params={"User-Agent": "Mozilla/5.0"},
            excel_kwargs={"skiprows": 2},
            get_cookies=True,
            retries=1,
        )
        # Keep only first 48 rows and desired columns
        dataset = dataset.iloc[:48, 1:8]
        dataset.reset_index(drop=True)

    else:
        # Detect header row
        header_row = None
        for i in range(7):
            row = dataset.iloc[i].astype(str).str.upper()
            if " SYSTEM DEMAND (ACTUAL)" in row.to_numpy():
                header_row = i
                break
        if header_row is None:
            logging.warning(f"Header not found for {year}-{month}-{day}")
            return pandas.Series(dtype=float, name="Value")

        # Fetch dataset again skipping header
        dataset = utils.fetcher.fetch_data(
            url,
            "html",
            read_as="excel_table",
            header_params={"User-Agent": "Mozilla/5.0"},
            excel_kwargs={"skiprows": header_row + 1},
            get_cookies=True,
            retries=1,
        )

        # Keep only first 48 rows and desired columns
        dataset = dataset.iloc[:48, [1 + 3 * i for i in range(0, 7)]]
        dataset.reset_index(
            drop=True,
        )

    # Generate Hour column programmatically (48 slots per day)
    hours = pandas.date_range("00:00", periods=48, freq="30min").strftime(
        "%H:%M"
    )
    dataset["Hour"] = hours

    # Start date is the given day
    start_date = pandas.Timestamp(f"{year}-{month}-{day}").date()
    dataset.columns = [
        start_date + pandas.Timedelta(days=i) for i in range(0, 7)
    ] + ["Hour"]

    # Drop rows where all values are NaN
    dataset = dataset.dropna(axis=0, how="all")

    # Reshape the dataset from wide to long format.
    dataset = dataset.melt(id_vars="Hour", var_name="Date", value_name="Value")
    dataset["Value"] = pandas.to_numeric(dataset["Value"], errors="coerce")
    dataset = dataset.dropna(subset=["Value"])

    # Build the DateTime column by combining Date and Hour column
    dataset["DateTime"] = (
        dataset["Date"].astype(str) + " " + dataset["Hour"].astype(str)
    )

    # Define the new index.
    index = pandas.to_datetime(
        dataset["DateTime"], errors="coerce", format="%Y-%m-%d %H:%M"
    )
    dataset = dataset.dropna(subset=["DateTime"])

    # Define the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["Value"].values, index=index
    ).sort_index()

    # Add 30 minutes to the index because the electricity demand seems
    # to be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(minutes=30)
    )

    # Add the timezone information.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Singapore")
    )

    return electricity_demand_time_series
