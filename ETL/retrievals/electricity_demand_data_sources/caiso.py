# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the California ISO (CAISO) in California
    USA. The data is retrieved for the years from 2019 to the current
    date. The data is retrieved from the available Excel files on the
    Caiso website.

    Source: https://www.caiso.com/library/historical-ems-hourly-load
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
    logging.debug("Use for any purpose with attribution to CAISO.")
    logging.debug("Source: https://www.caiso.com/privacy-terms-of-use")
    return True


def _check_input_parameters(year: int, month: int | None) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve.
    """
    # Check if the request is supported.
    assert (year, month) in get_available_requests(), (
        "The request is not available."
    )


def get_available_requests() -> list[tuple[int, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the CAISO website.

    Returns
    -------
    list[tuple[int, int | None]]
        The list of available requests.
    """
    # Get the start and end dates for California.
    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "caiso"
        )["USA_CAL"]
    )

    # Define the date that separates the two types of requests.
    Jan_2024 = pandas.Timestamp("2024-01-01")

    # Requests before January 2024.
    requests_before: list[tuple[int, int | None]] = [
        (year, None) for year in range(start_date.year, Jan_2024.year)
    ]

    # Requests after January 2024
    requests_after: list[tuple[int, int | None]] = []
    for year in range(Jan_2024.year, end_date.year + 1):
        start_month = 1
        end_month = 12
        if year == end_date.year:
            end_month = end_date.month - 2
        for month in range(start_month, end_month + 1):
            requests_after.append((year, month))

    # Return the list of available requests.
    return requests_before + requests_after


def get_url(year: int, month: int | None) -> str:
    """
    Get the URL of the electricity demand data on the CAISO website.

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
    # Check if the input parameters are valid.
    _check_input_parameters(year, month)

    # Define the base URL of the electricity demand data.
    base_url = "https://www.caiso.com/documents/"

    # Yearly data (2019–2023)
    if month is None:
        if year <= 2022:
            url = f"{base_url}historicalemshourlyload-{year}.xlsx"
        elif year == 2023:
            url = f"{base_url}historicalemshourlyloadfor{year}.xlsx"

    # Monthly data (2024 onward)
    else:
        month_name = calendar.month_name[month]
        if year == 2024 and month in [1, 2, 3]:  # Jan–Mar 2024
            url = (
                f"{base_url}historicalemshourlyloadfor{month_name}{year}.xlsx"
            )
        elif year >= 2024:  # April 2024 onwards
            url = f"{base_url}historical-ems-hourly-load-for-{month_name}-{year}.xlsx"
    return url


def download_and_extract_data_for_request(
    year: int, month: int | None
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CAISO website.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve.

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
    _check_input_parameters(year, month)

    # Get the URL of the electricity demand data.
    url = get_url(year, month)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_as="excel_table",
    )

    logging.info(
        "Retrieving electricity demand data for "
        + (
            f"{calendar.month_name[month]} {year}"
            if month is not None
            else f"{year}"
        )
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Keep only valid dates.
        dataset = dataset[
            pandas.to_datetime(dataset["Date"], errors="coerce").notna()
        ]

        if year <= 2020:
            # Define the new index.
            index = pandas.to_datetime(dataset["Date"]) + pandas.to_timedelta(
                dataset["HE"], unit="h"
            )

            # Define the electricity demand time series.
            electricity_demand_time_series = pandas.Series(
                dataset["CAISO Total"].values, index=index
            ).tz_localize("UTC")
        else:
            # Define the new index.
            index = pandas.to_datetime(dataset["Date"]) + pandas.to_timedelta(
                dataset["HR"], unit="h"
            )

            # Define the electricity demand time series.
            electricity_demand_time_series = pandas.Series(
                dataset["CAISO"].values, index=index
            ).tz_localize("UTC")

        return electricity_demand_time_series
