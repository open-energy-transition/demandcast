"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the European Network of Transmission System
    Operators for Electricity (ENTSO-E). The data is retrieved in
    one-year intervals.

    The API gives the actual total load of each country in MW, at the
    start of each interval in UTC: hourly, 30 or 15 minutes depending on
    the country, which can change within a year. The data can have
    gaps, such as two hours in Ireland on the night of 2024-10-27, when
    daylight saving time ended. The actual total load is not on the list
    of data that ENTSO-E opens under CC BY 4.0.

    The United Kingdom has two areas: Great Britain (GB), the area of
    National Grid, from 2014-12-22 to 2021-06-14, when its data ends
    after the United Kingdom left the market of the European Union, and
    Northern Ireland (GB_NIR), the area of SONI, from 2015-01-01 to
    2025-10-23. The area of the United Kingdom (UK) gives their sum
    until 2021 and only Northern Ireland after, so it is not used. The
    load of Great Britain is close to the transmission demand of NESO
    with the embedded wind and solar generation, and about 3 to 6 GW
    above its national demand (see neso.py).

    Source: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
    Source: https://github.com/EnergieID/entsoe-py
"""

import datetime
import logging

import pandas as pd
import utils.config
import utils.fetcher
import utils.time_series

# The areas of ENTSO-E of the subdivisions, by their code. The areas of
# the countries are their ISO Alpha-2 codes.
AREAS = {"GBR_GB": "GB", "GBR_NIR": "GB_NIR"}


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
    # Split the period of the data into one-year periods, the maximum
    # available on the platform.
    return utils.time_series.split_period(start_date, end_date, "YS")


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

    # Get the API key.
    api_key = utils.config.read_api_key("ENTSOE_API_KEY", "ENTSO-E")

    # Add the time zone to the start date.
    start_date = start_date.tz_localize("UTC")
    end_date = end_date.tz_localize("UTC")

    # Download the electricity demand time series from the ENTSO-E
    # API.
    electricity_demand_time_series = utils.fetcher.fetch_entsoe_demand(
        api_key, code, start_date, end_date, area=AREAS.get(code)
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
