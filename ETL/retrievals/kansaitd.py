# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Kansai Transmission and Distribution
    (KANSAITD) in Japan. The data is retrieved for the years from
    2016 to the current date. The data is retrieved from the available
    CSV files on the kansai website.

    Source: https://www.kansai-td.co.jp/english/home/denkiyoho/area-performance/index.html
"""  # noqa: W505

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
    logging.debug("All rights reserved by KANSAI.")
    logging.debug("Source: https://www.kansai-td.co.jp/english/siteinfo/")
    return False


def _check_input_parameters(
    year: int, month: int | None, before_Mar_2024: bool
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve.
    before_Mar_2024 : bool
        Whether the url is for the time period before March 2024.
    """
    # Check if the request is supported.
    assert (year, month, before_Mar_2024) in get_available_requests(), (
        "The request is not available."
    )


def get_available_requests() -> list[tuple[int, int | None, bool]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the KANSAI website.

    Returns
    -------
    list[tuple[int, int | None, bool]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="kansaitd"
    )["JP_KANSAI"]

    # Define the date that separates the two periods of data.
    date_after_Mar_2024 = pandas.Timestamp("2024-03-01")

    # Requests before March 2024
    requests_before: list[tuple[int, int | None, bool]] = [
        (year, None, True)
        for year in range(start_date.year, date_after_Mar_2024.year)
    ]

    # Requests after March 2024
    requests_after: list[tuple[int, int | None, bool]] = []
    for year in range(date_after_Mar_2024.year, end_date.year + 1):
        start_month = 1
        end_month = 12
        if year == date_after_Mar_2024.year:
            start_month = date_after_Mar_2024.month
        if year == end_date.year:
            end_month = end_date.month
        for month in range(start_month, end_month + 1):
            requests_after.append((year, month, False))

    # Return the available requests, which are a combination of a year
    # number, month number and a boolean indicating whether the data
    # is before March 2024.
    # available_requests = [
    #       (year = 2016, month = None, before_Mar_2024 = True),
    #       (year = 2017, month = None, before_Mar_2024 = True),
    #       ...
    #       (year = 2024, month = 03, before_Mar_2024 = False),
    #       (year = 2024, month = 04, before_Mar_2024 = False),
    #       ...
    #       (year = last year, month = last month,
    #        before_Mar_2024 = False)]

    return requests_before + requests_after


def get_url(year: int, month: int | None, before_Mar_2024: bool) -> str:
    """
    Get the URL of the electricity demand data on the KANSAI website.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve.
    before_Mar_2024 : bool
        Whether the url is for the time period before March 2024.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(
        year=year, month=month, before_Mar_2024=before_Mar_2024
    )

    # Define the URL of the electricity demand data.
    if before_Mar_2024:
        url = (
            "https://www.kansai-td.co.jp/denkiyoho/area-performance/csv/"
            f"area_jyukyu_jisseki_{year:04d}.csv"
        )
    elif (
        month is not None
        and year >= 2024
        and year <= pandas.Timestamp.now().year
    ):
        url = (
            "https://www.kansai-td.co.jp/interchange/denkiyoho/area-performance/"
            f"eria_jukyu_{year:04d}{month:02d}_06.csv"
        )

    return url


def download_and_extract_data_for_request(
    year: int, month: int | None, before_Mar_2024: bool
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the KANSAI website.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    month : int | None
        The month of the data to retrieve.
    before_Mar_2024 : bool
        Whether the url is for the time period before March 2024.

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
    _check_input_parameters(
        year=year, month=month, before_Mar_2024=before_Mar_2024
    )

    # Get the URL of the electricity demand data.
    url = get_url(year=year, month=month, before_Mar_2024=before_Mar_2024)

    # Determine number of rows to skip
    skip_rows = 3 if year == 2021 else 1

    # Fetch CSV content from the URL with proper encoding.
    dataset = utils.fetcher.fetch_data(
        url,
        "csv",
        csv_kwargs={
            "skiprows": skip_rows,
            "encoding": "cp932",
        },  # Japanese encoding
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        if before_Mar_2024:
            logging.info(
                f"Retrieving electricity demand data for the year {year}."
            )

            # Extract the electricity demand time series.
            electricity_demand_time_series = pandas.Series(
                dataset["エリア需要〔MWh〕"].values,
                index=pandas.to_datetime(dataset["DATE_TIME"]),
            )

            # Add one hour to the time index because the time values
            # appear to be provided at the beginning of the time
            # interval.
            electricity_demand_time_series.index += pandas.Timedelta(hours=1)

        else:
            logging.info(
                f"Retrieving electricity demand data for the year {year} and {month}."
            )

            # Convert date and hour columns into hourly timestamps
            dataset["DATE_TIME"] = pandas.to_datetime(
                dataset["DATE"]
            ) + pandas.to_timedelta(dataset["TIME"].astype(str) + ":00")

            # Extract the electricity demand time series.
            electricity_demand_time_series = pandas.Series(
                dataset["エリア需要"].values,
                index=pandas.to_datetime(dataset["DATE_TIME"]),
            )

            # Add 30 minutes to the time index because the time values
            # appear to be provided at the beginning of the time
            # interval.
            electricity_demand_time_series.index += pandas.Timedelta(
                minutes=30
            )

        # Convert the time zone of the electricity demand time
        # series to UTC.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Asia/Tokyo")
        )

        return electricity_demand_time_series
