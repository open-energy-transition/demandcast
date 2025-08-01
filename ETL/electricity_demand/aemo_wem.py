#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Australian Energy Market Operator
    (AEMO) for the Wholesale Electricity Market (WEM) in Western
    Australia. The data is retrieved from 2006 to 2023 in one-year
    intervals in CSV format, and from October 1, 2023, to today in daily
    intervals in JSON format.

    Source: https://data.wa.aemo.com.au/#operational-demand
    Source: https://data.wa.aemo.com.au/public/market-data/wemde/operationalDemandWithdrawal/dailyFiles/
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
    logging.debug("Use for any purpose with attribution to AEMO.")
    logging.debug(
        "Source: "
        "https://aemo.com.au/privacy-and-legal-notices/copyright-permissions"
    )
    return True


def _check_input_parameters(
    pre_reform: bool, year: int, month: int | None, day: int | None
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    pre_reform : bool
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023).
    year : int
        The year of the data to retrieve.
    month : int, optional
        The month of the data to retrieve.
    day : int, optional
        The day of the data to retrieve.
    """
    # Check if the input parameters are valid.
    assert (pre_reform, year, month, day) in get_available_requests(), (
        "The request is not supported."
    )


def get_available_requests() -> list[tuple[bool, int, int | None, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the AEMO website.

    Returns
    -------
    list[tuple[bool, int, int | None, int | None]]
        List of tuples in the format (year, month, day).
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="aemo_wem"
    )["AU_WA"]

    # Define the date that marks the beginning of the post-reform
    # period.
    post_reform_start_date = pandas.Timestamp("2023-10-01")

    # Define the list of available requests for the pre-reform period,
    # which are the years from 2006 to 2023.
    pre_reform_values = [
        year
        for year in range(start_date.year, post_reform_start_date.year + 1)
    ]

    # Define the list of available requests for the post-reform period,
    # which are the year, month, and day from October 1, 2023, to today.
    post_reform_values = (
        pandas.date_range(
            start=post_reform_start_date,
            end=end_date,
            freq="D",
        )
        .strftime("%Y-%m-%d")
        .str.split("-")
        .tolist()
    )

    # Return the available requests that combine the two lists and add a
    # boolean flag to indicate if the request is for the pre-reform
    # period.
    return [(True, year, None, None) for year in pre_reform_values] + [
        (False, int(year), int(month), int(day))
        for year, month, day in post_reform_values
    ]


def get_url(
    pre_reform: bool, year: int, month: int | None, day: int | None
) -> str:
    """
    Get the URL of the electricity demand data on the AEMO website.

    Parameters
    ----------
    pre_reform : bool
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023).
    year : int
        The year of the data to retrieve.
    month : int, optional
        The month of the data to retrieve.
    day : int, optional
        The day of the data to retrieve.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(pre_reform, year, month, day)

    if pre_reform:
        # If the request is for the pre-reform period, set the URL to
        # fetch .csv files for data from 2006 to 2023.
        return (
            "https://data.wa.aemo.com.au/datafiles/operational-demand/"
            f"operational-demand-{year}.csv"
        )

    else:
        # If the request is for the post-reform period, set the URL to
        # fetch .json files for data from September 2023 onward.
        return (
            "https://data.wa.aemo.com.au/public/market-data/wemde/"
            "operationalDemandWithdrawal/dailyFiles/"
            f"OperationalDemandAndWithdrawal_{year}-{month:02d}-{day:02d}.json"
        )


def download_and_extract_data_for_request(
    pre_reform: bool, year: int, month: int | None, day: int | None
) -> pandas.DataFrame:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the AEMO website.

    Parameters
    ----------
    pre_reform : bool
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023).
    year : int
        The year of the electricity demand data.
    month : int, optional
        The month of the electricity demand data.
    day : int, optional
        The day of the electricity demand data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity generation time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(pre_reform, year, month, day)

    if pre_reform:
        logging.info(
            f"Retrieving electricity demand data for the year {year}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_data(url, "csv")

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pandas.DataFrame):
            raise ValueError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )
        else:
            # Extract the electricity demand data from the dataset.
            electricity_demand_time_series = pandas.Series(
                dataset["Operational Demand (MW)"].values,
                index=pandas.to_datetime(dataset["Trading Interval"]),
            )

            # Add the timezone information to the index.
            electricity_demand_time_series.index = (
                electricity_demand_time_series.index.tz_localize(
                    "Australia/Perth",
                    ambiguous="NaT",
                    nonexistent="NaT",
                ).tz_convert("UTC")
            )

            # Add 30 minutes to the index because the demand data seems
            # to be reported at the beginning of the trading interval.
            electricity_demand_time_series.index = (
                electricity_demand_time_series.index
                + pandas.Timedelta(minutes=30)
            )

    else:
        logging.info(
            "Retrieving electricity demand data for "
            f"{year}-{month:02d}-{day:02d}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_data(
            url,
            "html",
            read_with="requests.get",
            read_as="json",
            json_keys=["data", "data"],
        )

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pandas.DataFrame):
            raise ValueError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )
        else:
            # Extract the electricity demand data from the dataset.
            electricity_demand_time_series = pandas.Series(
                dataset["operationalDemand"].values,
                index=pandas.to_datetime(dataset["asAtTimeStamp"], utc=True),
            )

    return electricity_demand_time_series
