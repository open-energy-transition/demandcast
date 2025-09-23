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
"""  # noqa: W505

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


def _check_input_parameters(year: int, month: int, day: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data.
    month : int
        The month of the data.
    day : int
        The day of the data.
    """
    # Check if the input parameters are valid.
    assert (year, month, day) in get_available_requests(), (
        f"The {year}-{month:02d}-{day:02d} request is not available."
    )


def get_available_requests() -> list[tuple[int, int, int]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EMA website.

    Returns
    -------
    requests : list[tuple[int, int, int]]
        List of tuples in the format (year, month, day).
    """
    # Get the start and end dates for Singapore.
    start_date, end_date = utils.entities.read_date_ranges(data_source="ema")[
        "SG"
    ]

    # Subtract one week from the end date to ensure that the last
    # request is within the available data range.
    end_date = end_date - pandas.Timedelta("7days")

    # Create a list of dates that are not available on the EMA website.
    dates_not_available = [
        pandas.Timestamp("2014-12-01"),
        pandas.Timestamp("2014-12-08"),
        pandas.Timestamp("2014-12-29"),
        pandas.Timestamp("2015-01-12"),
        pandas.Timestamp("2015-01-19"),
        pandas.Timestamp("2015-01-26"),
        pandas.Timestamp("2015-02-02"),
        pandas.Timestamp("2015-02-09"),
        pandas.Timestamp("2015-02-16"),
        pandas.Timestamp("2015-02-23"),
        pandas.Timestamp("2015-03-02"),
        pandas.Timestamp("2015-03-09"),
        pandas.Timestamp("2015-04-06"),
        pandas.Timestamp("2015-04-13"),
    ]

    # Return the available requests, which are tuples in the format
    # (year, month, day).
    return [
        (date.year, date.month, date.day)
        for date in pandas.date_range(
            start=start_date, end=end_date, freq="7D"
        )
        if date not in dates_not_available
    ]


def get_url(year: int, month: int, day: int) -> str:
    """
    Get the URL of the electricity demand data on the EMA website.

    Parameters
    ----------
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
    # Check if the input parameters are valid.
    _check_input_parameters(year, month, day)

    # Construct the request date.
    request_date = pandas.Timestamp(year=year, month=month, day=day)

    # Define the base URL.
    base_url = (
        "https://www.ema.gov.sg/content/dam/corporate/resources/statistics/"
        "half-hourly-data/"
    )

    # Construct the URL for the request.
    if request_date < pandas.Timestamp("2014-12-15"):
        month_abbr = calendar.month_abbr[month]
        return base_url + f"{year}/{day:02d}_{month_abbr}_{year}.xls"
    elif request_date == pandas.Timestamp(
        "2025-01-13"
    ) or request_date == pandas.Timestamp("2025-01-20"):
        return base_url + f"{year}/{year}{month:02d}{day:02d}.xlsx"
    else:
        return base_url + f"{year}/{year}{month:02d}{day:02d}.xls"


def download_and_extract_data_for_request(
    year: int, month: int, day: int
) -> pandas.Series:
    """
    Download and extract electricity demand data from EMA website.

    Parameters
    ----------
    year : int
        The year of the data.
    month : str or int
        The month of the data.
    day : str
        The day of the data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year, month, day)

    logging.info(
        f"Retrieving electricity demand data for {year}-{month:02d}-{day:02d}."
    )

    # Construct the URL for the request.
    url = get_url(year, month, day)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_as="excel_table",
        header_params={"User-Agent": "Mozilla/5.0"},
        get_cookies=True,
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Find the row that contains the string "00:30" in the first
        # column.
        start_row = dataset[dataset.iloc[:, 0] == "00:30"].index[0]

        # Keep only the rows from the start row and the following 48
        # rows.
        dataset = dataset.iloc[start_row : start_row + 48, :]

        # Reconstruct the request date.
        request_date = pandas.Timestamp(year=year, month=month, day=day)

        # Keep only the columns with system demand data.
        if request_date == pandas.Timestamp("2014-11-03"):
            dataset = dataset.iloc[:, [1 + 2 * i for i in range(0, 7)]]
        elif request_date <= pandas.Timestamp("2014-09-22"):
            dataset = dataset.iloc[:, 1:8]
        else:
            dataset = dataset.iloc[:, [1 + 3 * i for i in range(0, 7)]]

        # Add a column for the hour of the day.
        dataset["Hour"] = pandas.date_range(
            "00:00", periods=48, freq="30min"
        ).strftime("%H:%M")

        # Rename the columns to the corresponding dates.
        dataset.columns = [
            date.strftime("%Y-%m-%d")
            for date in pandas.date_range(start=request_date, periods=7)
        ] + ["Hour"]

        # Reshape the dataset from wide to long format.
        dataset = dataset.melt(
            id_vars="Hour", var_name="Date", value_name="Value"
        )

        # Define the new index.
        index = pandas.to_datetime(
            dataset["Date"] + " " + dataset["Hour"], format="%Y-%m-%d %H:%M"
        )

        # Define the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["Value"].values, index=index
        )

        # Add the timezone information.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Asia/Singapore")
        )

        return electricity_demand_time_series
