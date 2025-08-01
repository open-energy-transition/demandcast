# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Public Utilities Commission of Sri
    Lanka (PUCSL) in Sri Lanka. The data is downloaded from Jan 1, 2023
    up to the current date. The data is retrieved in one-week intervals.

    Note:
    Although data is retrieved in 7-day intervals,
    retrieving data over a longer historical range
    (e.g., multiple years) may take considerable time —
    up to 60 minutes in total, due to the number of API
    calls required.

    Source: https://gendata.pucsl.gov.lk/generation-profile
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
    logging.debug("All rights reserved by PUCSL.")
    logging.debug("Source: https://www.pucsl.gov.lk")
    return False


def _check_input_parameters(
    start_date: pandas.Timestamp,
    end_date: pandas.Timestamp,
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    """
    # Check if the retrieval period is within a week.
    assert (end_date - start_date) <= pandas.Timedelta("7days"), (
        "The retrieval period must be 7 days or less. "
        f"start_date: {start_date}, end_date: {end_date}"
    )

    # Read the start date of the available data.
    start_date_of_data_availability = pandas.to_datetime(
        utils.entities.read_date_ranges(data_source="pucsl")["LK"][0]
    )

    # Check that the start date is greater than or equal to the
    # beginning of the data availability.
    assert start_date >= start_date_of_data_availability, (
        "The beginning of the data availability is "
        f"{start_date_of_data_availability}."
    )


def get_available_requests() -> list[
    tuple[pandas.Timestamp, pandas.Timestamp]
]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the PUCSL website.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="pucsl"
    )["LK"]

    # Define intervals for the retrieval periods.
    intervals = pandas.date_range(start_date, end_date, freq="7D")
    intervals = intervals.union(
        pandas.to_datetime([start_date, end_date])
    ).drop_duplicates()
    intervals = intervals.sort_values()

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-year period.
    return list(zip(start_dates_and_times, end_dates_and_times))


def get_url(start_date: pandas.Timestamp, end_date: pandas.Timestamp) -> str:
    """
    Get the URL of the electricity demand data on the PUCSL website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date : pandas.Timestamp
        The end date and time of the data retrieval.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(start_date, end_date)

    # Convert timestamps to string format expected by the API
    from_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return (
        "https://gendata.pucsl.gov.lk/api/actual-system-dispatch"
        f"?dateAggregation=15min"
        f"&from={from_str}"
        f"&to={to_str}"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp, end_date: pandas.Timestamp
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the PUCSL website for the given date range.

    Parameters
    ----------
    start_date : datetime
        The start date and time of the data retrieval.
    end_date : datetime
        The end date and time of the data retrieval.

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
    _check_input_parameters(start_date, end_date)

    logging.info(
        f"Retrieving data from {start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(start_date, end_date)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(
        url, content_type="html", read_as="json", json_keys=["data"]
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Convert timestamps to datetime
        dataset["reportTimestamp"] = pandas.to_datetime(
            dataset["reportTimestamp"]
        )

        # Aggregate total generation (in MW) across all
        # power plants for each timestamp
        dataset_grouped = dataset.groupby("reportTimestamp", as_index=False)[
            "dispatchValueInMW"
        ].sum()

        # Extract the electricity demand time series
        electricity_demand_time_series = pandas.Series(
            dataset_grouped["dispatchValueInMW"].values,
            index=dataset_grouped["reportTimestamp"],
        )

        # Add 15 minutes to the index because the electricity demand
        # seems to be provided at the beginning of the time-interval
        electricity_demand_time_series.index += pandas.Timedelta(minutes=15)

        # Add the time zone information to the time series.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_convert("Asia/Colombo")
        )

        return electricity_demand_time_series
