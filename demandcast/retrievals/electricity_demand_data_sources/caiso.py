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
import datetime
import logging
import re

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
    logging.debug("Use for any purpose with attribution to CAISO.")
    logging.debug("Source: https://www.caiso.com/privacy-terms-of-use")
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[int, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the CAISO website. The data until 2023 is in one
    file per year, and the data from 2024 on in one file per month,
    published one to four months after the month ends, so the months
    are read from the download page.

    Parameters
    ----------
    code : str
        The code of California.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[int, int | None]]
        The list of available requests.

    Raises
    ------
    TypeError
        If the extracted page is not a string.
    """
    # Requests before 2024.
    requests_before: list[tuple[int, int | None]] = [
        (year, None) for year in range(start_date.year, 2024)
    ]

    # Read the page that lists the files.
    page = utils.fetcher.fetch_data(
        "https://www.caiso.com/library/historical-ems-hourly-load",
        "html",
        read_as="text",
    )

    # Make sure the page is a string.
    if not isinstance(page, str):
        raise TypeError(
            f"The extracted page is a {type(page)} object, expected a string."
        )

    # Find the months of the monthly files, such as
    # "historical-ems-hourly-load-for-may-2026.xlsx", or
    # "historicalemshourlyloadforjanuary2024.xlsx" for the first ones.
    month_numbers = {
        name.lower(): number
        for number, name in enumerate(calendar.month_name)
        if name
    }
    published_months = {
        (int(year), month_numbers[month_name.lower()])
        for month_name, year in re.findall(
            r"historical-?ems-?hourly-?load-?for-?([a-z]+)-?(\d{4})\.xlsx",
            page,
            flags=re.IGNORECASE,
        )
        if month_name.lower() in month_numbers
    }

    # Requests from 2024 onward, for the published months.
    requests_after: list[tuple[int, int | None]] = [
        (year, month)
        for year, month in sorted(published_months)
        if pd.Timestamp(year, month, 1) <= pd.Timestamp(end_date)
    ]

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
    # Define the base URL of the electricity demand data.
    base_url = "https://www.caiso.com/documents/"

    # Define the full URL based on the year and month.
    if month is None:
        # Yearly data before 2024.
        if year <= 2022:
            url = f"{base_url}historicalemshourlyload-{year}.xlsx"
        elif year == 2023:
            url = f"{base_url}historicalemshourlyloadfor{year}.xlsx"
    else:
        # Monthly data from 2024 onward.
        month_name = calendar.month_name[month]
        if year == 2024 and month in [1, 2, 3]:  # January to March 2024
            url = (
                f"{base_url}historicalemshourlyloadfor{month_name}{year}.xlsx"
            )
        elif year >= 2024:  # April 2024 onwards
            url = f"{base_url}historical-ems-hourly-load-for-{month_name}-{year}.xlsx"

    return url


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int | None], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CAISO website.

    Parameters
    ----------
    year_and_month : tuple[int, int | None]
        The year and month of the data to retrieve, without a month
        until 2023.
    code : str
        The code of California.

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
        "Retrieving electricity demand data for "
        + (
            f"{calendar.month_name[month]} {year}"
            if month is not None
            else f"{year}"
        )
    )

    # Get the URL of the electricity demand data.
    url = get_url(year, month)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_as="excel_table",
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Keep only rows with valid data.
    dataset = dataset[pd.to_datetime(dataset["Date"], errors="coerce").notna()]

    # Define the column names based on the year.
    if year <= 2020:
        hourly_column = "HE"
        demand_column = "CAISO Total"
    else:
        hourly_column = "HR"
        demand_column = "CAISO"

    # Define the new index.
    index = pd.to_datetime(dataset["Date"]) + pd.to_timedelta(
        dataset[hourly_column], unit="h"
    )

    # Define the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset[demand_column].values, index=index
    ).tz_localize("America/Los_Angeles", nonexistent="NaT", ambiguous="NaT")

    return electricity_demand_time_series
