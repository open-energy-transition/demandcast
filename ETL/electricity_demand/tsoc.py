# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Transmission System Operator of Cyprus
    (TSOC). The data seems to represent the total electricity generation
    in MW, which can be considered a proxy for the electricity demand.
    The data is retrieved for the years from 2008 to the current year.
    The data is retrieved in 15-day intervals.

    Source: https://tsoc.org.cy/electrical-system/archive-total-daily-system-generation-on-the-transmission-system/
"""  # noqa: W505

import logging
import re

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
    logging.debug("All rights reserved by TSOC.")
    logging.debug("Source: https://tsoc.org.cy")
    return False


def _check_input_parameters(start_date: pandas.Timestamp) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    """
    # Read the start date of the available data.
    start_date_of_data_availability = pandas.to_datetime(
        utils.entities.read_date_ranges(data_source="tsoc")["CY"][0]
    )

    # Check that the start date is greater than or equal to the
    # beginning of the data availability.
    assert start_date >= start_date_of_data_availability, (
        "The beginning of the data availability is "
        f"{start_date_of_data_availability}."
    )


def get_available_requests() -> list[pandas.Timestamp]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the TSOC website.

    Returns
    -------
    list[pandas.Timestamp]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(data_source="tsoc")[
        "CY"
    ]

    # Return the available requests, which are the start dates of the
    # retrieval periods. We use 15-day intervals (the maximum available
    # on the website) to minimize the number of requests.
    return list(pandas.date_range(start_date, end_date, freq="15D"))


def get_url(start_date: pandas.Timestamp) -> str:
    """
    Get the URL of the electricity generation data on the TSOC website.

    Parameters
    ----------
    starting_date : pandas.Timestamp
        The starting date for the data retrieval period.

    Returns
    -------
    str
        The URL of the electricity generation data.
    """
    # Check if input parameters are valid.
    _check_input_parameters(start_date)

    # Convert the start and end dates and times to the required format.
    start_date = start_date.strftime("%d-%m-%Y")

    # Return the URL of the electricity generation data.
    return (
        "https://tsoc.org.cy/electrical-system/"
        "archive-total-daily-system-generation-on-the-transmission-system/?"
        f"startdt={start_date}&enddt=%2B15days"
    )


def _read_generation(generation_step):
    """
    Read and calculate the total generation.

    Parameters
    ----------
    generation_step : tuple of str
        A tuple containing the wind, solar, total, and conventional
        generation values.

    Returns
    -------
    float | None
        The total generation in MW, or None if data is unavailable.
    """
    # Extract the wind, solar, total, and conventional generation values
    # from the tuple.
    wind, solar, total, conventional = generation_step

    # If total generation is null, it usually means no data is
    # available.
    if total == "null":
        return None

    # If total generation is 0, attempt to compute it from wind, solar,
    # and conventional values.
    if total == "0":
        wind = float(wind) if wind != "null" else 0
        solar = float(solar) if solar != "null" else 0
        conventional = float(conventional) if conventional != "null" else 0
        total_estimated = wind + solar + conventional

        # If the sum is still 0, return None.
        return total_estimated if total_estimated > 0 else None

    # Otherwise, return the total generation as a float.
    return float(total)


def _read_timestamp_and_generation(
    page: str,
) -> tuple[list[str], list[str], list[str], list[float | None]]:
    """
    Extract dates, hours, minutes, and generation data from the page.

    Parameters
    ----------
    page : str
        The HTML file content.

    Returns
    -------
    tuple[list[str], list[str], list[str], list[float | None]]
        A tuple containing lists of dates, hours, minutes, and total
        generation data.
    """
    # Extract the dates, hours, minutes, and generation data from the
    # HTML content using regex patterns.
    dates = re.findall(r'var dateStr = "(\d{4}-\d{2}-\d{2})";', page)
    hours = re.findall(r'var hourStr = "(\d{2})";', page)
    minutes = re.findall(r'var minutesStr = "(\d{2})";', page)
    # The following values represent wind, solar, total, and
    # conventional generation, respectively.
    generation_matches = re.findall(
        r"\[dateStrFormat, (\d+|null), (\d+|null), (\d+|null), (\d+|null)\]",
        page,
    )

    # Process the generation data to determine the total generation.
    total_generation = [_read_generation(g) for g in generation_matches]

    return dates, hours, minutes, total_generation


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp,
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the TSOC website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The starting date for the data retrieval.

    Returns
    -------
    electricity_generation_time_series : pandas.Series
        The electricity generation time series in MW.

    Raises
    ------
    ValueError
        If the extracted page is not a string.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(start_date)

    logging.info(
        "Retrieving electricity demand data for the 15-day period "
        f"starting from {start_date.date()}."
    )

    # Get the URL of the electricity generation data.
    url = get_url(start_date)

    # Fetch HTML content from the URL.
    page = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="urllib.request",
        header_params={"User-Agent": "Mozilla/5.0"},
    )

    # Make sure the page content is a string.
    if not isinstance(page, str):
        raise ValueError(
            f"The extracted page is a {type(page)} object, expected a string."
        )
    else:
        # Extract time and generation data.
        dates, hours, minutes, generation = _read_timestamp_and_generation(
            page
        )

        # Construct datetime index with time zone.
        date_time = pandas.to_datetime(
            [
                f"{date} {hour}:{minute}"
                for date, hour, minute in zip(dates, hours, minutes)
            ]
        ).tz_localize("Asia/Nicosia", nonexistent="NaT", ambiguous="NaT")

        # Create a Pandas Series for the electricity generation data.
        electricity_generation_time_series = pandas.Series(
            data=generation, index=date_time
        )

        return electricity_generation_time_series
