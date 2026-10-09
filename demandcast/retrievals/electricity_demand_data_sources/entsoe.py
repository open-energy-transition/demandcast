"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the European Network of Transmission System
    Operators for Electricity (ENTSO-E). The data is retrieved for the
    years from 2014 (end of year) to the current year. The data is
    retrieved in one-year intervals.

    Source: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
    Source: https://github.com/EnergieID/entsoe-py
"""

import datetime
import logging
import os

import pandas as pd
import utils.config
import utils.fetcher
from dotenv import load_dotenv


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("CC-BY 4.0 license. Use for any purpose with attribution.")
    logging.debug(
        "Source: https://transparency.entsoe.eu/content/static_content/download?path=/Static%20content/terms%20and%20conditions/230309_ENTSOE_Transparency_Terms_Conditions_MC_APPROVED.pdf"
    )
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the ENTSO-E website.

    Parameters
    ----------
    code : str
        The code of the country.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Define intervals for the retrieval periods. A one-year period is
    # the maximum available on the platform.
    intervals = pd.date_range(start_date, end_date, freq="YS")
    intervals = intervals.union(pd.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-year period.
    return list(zip(start_dates_and_times, end_dates_and_times, strict=True))


def get_url(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    code: str = "",
) -> str:
    """
    Get the URL of the electricity demand data on the ENTSO-E website.

    Used only to check if the platform is available.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    code : str
        The ISO Alpha-3 code of the country.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the ENTSO-E API key is not set in the environment variables.
    """
    # Convert the start and end dates and times to the required format.
    start = start_date.strftime("%Y%m%d%H00")
    end = end_date.strftime("%Y%m%d%H00")

    # Define the domain of the country.
    domain = "10YBE----------2"  # Belgium

    # Get the root directory of the project.
    root_directory = utils.config.read_folders_structure()["root_folder"]

    # Load the environment variables.
    load_dotenv(dotenv_path=os.path.join(root_directory, ".env"))

    # Get the ENTSO-E API client.
    api_key = os.getenv("ENTSOE_API_KEY")

    # Check if the API key is set.
    if api_key is None:
        raise ValueError(
            "The ENTSOE API key is not set. Please set the ENTSOE_API_KEY "
            "environment variable."
        )

    # Set some parameters for the API request.
    document_type = "A65"  # System total load
    process_type = "A16"  # Realised

    # Return the URL of the electricity demand data.
    return (
        f"https://web-api.tp.entsoe.eu/api?securityToken={api_key}&"
        f"documentType={document_type}&processType={process_type}&"
        f"outBiddingZone_Domain={domain}&periodStart={start}&periodEnd={end}"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ENTSO-E website.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The start and end date of the data retrieval period.
    code : str
        The ISO Alpha-3 code of the country.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the retrieval period is longer than 1 year, or if the
        ENTSO-E API key is not set in the environment variables.
    """
    start_date, end_date = period

    # Check if the retrieval period is less than 1 year, the maximum
    # available on the platform.
    if end_date - start_date > pd.Timedelta("366days"):
        raise ValueError(
            "The retrieval period must be less than or equal to 1 year. "
            f"start_date: {start_date}, end_date: {end_date}"
        )

    logging.info(
        f"Retrieving electricity demand data from {start_date.date()} to {end_date.date()}."
    )

    # Get the root directory of the project.
    root_directory = utils.config.read_folders_structure()["root_folder"]

    # Load the environment variables.
    load_dotenv(dotenv_path=os.path.join(root_directory, ".env"))

    # Get the ENTSO-E API client.
    api_key = os.getenv("ENTSOE_API_KEY")

    # Add the time zone to the start date.
    start_date = start_date.tz_localize("UTC")
    end_date = end_date.tz_localize("UTC")

    if api_key is None:
        raise ValueError(
            "The ENTSO-E API key is not set. Please set the ENTSOE_API_KEY "
            "environment variable."
        )

    # Download the electricity demand time series from the ENTSO-E
    # API.
    electricity_demand_time_series = utils.fetcher.fetch_entsoe_demand(
        api_key, code, start_date, end_date
    )

    if not electricity_demand_time_series.empty:
        # The time values are provided at the beginning of the time
        # steps. Move each one to the end of its step, the shorter of
        # the intervals to the times before and after it: some countries
        # changed from hourly to 15-minute data within a year, and the
        # data can have gaps. A single time value is one hour long.
        times = electricity_demand_time_series.index.to_series()
        steps = (
            pd.concat([times.diff(), -times.diff(-1)], axis=1)
            .min(axis=1)
            .fillna(pd.Timedelta("1h"))
        )
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index + pd.TimedeltaIndex(steps)
        )

    return electricity_demand_time_series
