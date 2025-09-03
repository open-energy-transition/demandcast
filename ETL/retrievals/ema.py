# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Energy Market Authority (EMA) in
    Singapore. The data is downloaded from Dec 15, 2014 up to the
    current date. The data is retrieved in one-week intervals.

    Note:
    Although data is retrieved in 7-day intervals,
    retrieving data over a longer historical range
    (e.g., multiple years) may take considerable time —
    up to 30 minutes in total, due to the number of API
    calls required.

    Source: https://www.ema.gov.sg/resources/statistics/half-hourly-system-demand-data
"""

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


def _check_input_parameters(date: str) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.
    """
    # Check if the date is supported.
    assert date in get_available_requests(), (
        f"The date {date} is not in the supported range."
    )


def get_available_requests() -> list[str]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EMA website.

    Returns
    -------
    list[str]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(data_source="ema")[
        "SG"
    ]

    # Return the available requests, which are the dates in the format
    # YYYY-MM-DD.
    return (
        pandas.date_range(start=start_date, end=end_date, freq="7D")
        .strftime("%Y-%m-%d")
        .to_list()
    )


def get_url(date: str) -> str:
    """
    Get the URL of the electricity demand data on the EMA website.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(date)

    # Extract the year, month, and day from the date
    year, month, day = date.split("-")

    # Return the URL of the electricity demand data.
    return (
        f"https://www.ema.gov.sg/content/dam/corporate/resources/statistics/half-hourly-data/"
        f"{year}/{year}{month}{day}.xls"
    )


def download_and_extract_data_for_request(date: str) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the EMA website.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(date)

    logging.info(f"Retrieving electricity demand data for {date}.")

    # Get the URL of the electricity demand data.
    url = get_url(date)

    # Fetch the data from the URL.
    dataset: pandas.DataFrame = utils.fetcher.fetch_data(url, "excel")

    # Select relevant rows/columns
    dataset = dataset.iloc[4:, [0] + [1 + 3 * i for i in range(0, 7)]]
    dataset.reset_index(drop=True)

    # Set start date
    start_date = pandas.Timestamp(date).date()

    # Rename columns: first is 'Hour', rest are consecutive dates
    dataset.columns = ["Hour"] + [
        start_date + pandas.Timedelta(days=i) for i in range(1, 8)
    ]
    dataset = dataset.dropna(axis=0, how="any")

    # Reshape dataset to long format
    dataset = dataset.melt(
        id_vars=dataset.columns[0], var_name="Date", value_name="Value"
    )

    # Combine Date and Hour into datetime
    dataset["DateTime"] = dataset["Date"].astype(str) + " " + dataset["Hour"]

    # Convert to datetime index
    index = pandas.to_datetime(
        dataset["DateTime"], errors="coerce", format="%Y-%m-%d %H:%M"
    )
    dataset = dataset.dropna(subset=["DateTime"])

    # Create time series
    electricity_demand_time_series = pandas.Series(
        dataset["Value"].values, index=index
    )

    # Localize to Singapore timezone
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Singapore")
    )

    return electricity_demand_time_series
