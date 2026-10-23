"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the European Network of Transmission System
    Operators for Electricity (ENTSO-E). The data is retrieved in
    one-year intervals, with the client of entsoe-py, which retries
    after connection errors. A request that ENTSO-E answers with an
    error of its server is split into months, then days, and the days
    that still fail are left out. The errors are raised without the API
    key, which the URLs of the requests have.

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

    The times of some periods are wrong on ENTSO-E, as the daily profile
    in local time shows against the same days of the other years, and
    the module corrects them:

    - Northern Ireland: the times are an hour late when the United
      Kingdom is on winter time (GMT), in every year. The values equal
      the system demand of NI of EirGrid's Smart Grid Dashboard within
      1 MW, 30 minutes from its local times in summer and 90 minutes in
      winter (2019, 2022 and 2024), and the morning rise of the demand
      is at about 7:00 in summer as in Ireland, but at about 7:50 in
      winter.
    - Ukraine: the times are an hour late in the summer of 2018, from
      2018-03-25 to 2018-10-28, an hour early in the winter of 2018 to
      2019, until 2019-03-31, as if daylight saving time were reversed,
      and an hour early after daylight saving time ended in 2019, until
      2019-11-09, and in 2021, until 2021-11-30.
    - Bulgaria: the times are an hour early from 2016-10-30, when
      daylight saving time ended, to 2016-11-17.

    The hours that two corrected periods give twice are kept once. The
    load of Luxembourg changes in 2017 and 2018, when the profiles of
    many days are 2 to 3 hours off those of the other years among days
    that match them, and rises by about 24% from 2019. It looks like a
    change of large industrial loads rather than of the times, so it is
    not corrected.

    ENTSO-E republishes the data of the TSOs, so it is compiled in the
    yaml file: the combined demand of a code takes the data of its TSO
    first (see cleaning/combining.py).

    Source: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
    Source: https://github.com/EnergieID/entsoe-py
"""

import datetime
import itertools
import logging

import numpy as np
import pandas as pd
import requests
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

import utils.codes
import utils.config
import utils.time_series

# The areas of ENTSO-E of the subdivisions, by their code. The areas of
# the countries are their ISO Alpha-2 codes.
AREAS = {"GBR_GB": "GB", "GBR_NIR": "GB_NIR"}

# The periods whose times are wrong on ENTSO-E, by code, from and to in
# UTC, with the hours to add to them.
TIME_CORRECTIONS = {
    "BGR": [("2016-10-30 01:00", "2016-11-17 22:00", 1)],
    "UKR": [
        ("2018-03-25 01:00", "2018-10-28 01:00", -1),
        ("2018-10-28 01:00", "2019-03-31 01:00", 1),
        ("2019-10-27 01:00", "2019-11-09 22:00", 1),
        ("2021-10-31 01:00", "2021-11-30 22:00", 1),
    ],
}

# The codes whose times are an hour late in winter, with the time zone
# of the winter.
LATE_IN_WINTER = {"GBR_NIR": "Europe/London"}


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


def _correct_times(time_series: pd.Series, code: str) -> pd.Series:
    """
    Correct the times of the periods that are wrong on ENTSO-E.

    Parameters
    ----------
    time_series : pandas.Series
        The electricity demand, at times with a time zone.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    pandas.Series
        The electricity demand, at the corrected times, with the times
        that two periods give twice kept once.
    """
    times = pd.DatetimeIndex(time_series.index).tz_convert("UTC")
    hours = np.zeros(len(times))
    for start, end, shift in TIME_CORRECTIONS.get(code, []):
        hours[
            (times >= pd.Timestamp(start, tz="UTC"))
            & (times < pd.Timestamp(end, tz="UTC"))
        ] = shift
    if code in LATE_IN_WINTER:
        local = times.tz_convert(LATE_IN_WINTER[code]).tz_localize(None)
        winter = local - times.tz_localize(None) == pd.Timedelta(0)
        hours[np.asarray(winter)] = -1
    corrected = pd.Series(
        time_series.to_numpy(),
        index=pd.DatetimeIndex(time_series.index)
        + pd.to_timedelta(hours, unit="h"),
    )
    return corrected[~corrected.index.duplicated()].sort_index()


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
    electricity_demand_time_series = _fetch_demand(
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

        # Correct the times of the periods that are wrong on ENTSO-E.
        electricity_demand_time_series = _correct_times(
            electricity_demand_time_series, code
        )

    return electricity_demand_time_series


# The periods into which a request to ENTSO-E is split when it answers
# with an error, from the largest.
_SPLITS = ["MS", "D"]


def _query_load(
    client: EntsoePandasClient,
    area: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    splits: list[str],
) -> pd.Series:
    """
    Query the load of an area of ENTSO-E, around the periods it fails.

    ENTSO-E answers some periods with an error of the server (400,
    "Unexpected ERROR occurred during processing of use case"), such as
    the load of Cyprus on 2025-10-09, while it gives the days around
    them. The period is then split into months, and a month that fails
    into days, and the days that fail are left out.

    Parameters
    ----------
    client : entsoe.EntsoePandasClient
        The client of the API of ENTSO-E.
    area : str
        The area of ENTSO-E.
    start : pandas.Timestamp
        The start of the period.
    end : pandas.Timestamp
        The end of the period.
    splits : list[str]
        The frequencies of the periods into which the period is split if
        it fails, from the largest.

    Returns
    -------
    pandas.Series
        The actual load in MW, without the days that fail.

    Raises
    ------
    requests.exceptions.HTTPError
        If ENTSO-E answers with another error than 400.
    """
    try:
        return client.query_load(area, start=start, end=end)["Actual Load"]
    except requests.exceptions.HTTPError as error:
        if error.response is None or error.response.status_code != 400:
            raise
    if not splits:
        # The error is not logged, since its URL has the API key.
        logging.warning(
            f"ENTSO-E answers the load of {area} from {start} to {end} "
            "with an error, so this period is left out."
        )
        return pd.Series(dtype="float64")

    edges = sorted(
        {
            start,
            end,
            *pd.date_range(start, end, freq=splits[0], inclusive="neither"),
        }
    )
    parts = []
    for part_start, part_end in itertools.pairwise(edges):
        try:
            part = _query_load(client, area, part_start, part_end, splits[1:])
        except NoMatchingDataError:
            continue
        if not part.empty:
            parts.append(part)
    if not parts:
        return pd.Series(dtype="float64")
    load = pd.concat(parts)
    return load[~load.index.duplicated()]


def _fetch_demand(
    api_key: str,
    iso_alpha_3_code: str,
    start_date_and_time: pd.Timestamp,
    end_date_and_time: pd.Timestamp,
    retries: int = 3,
    retry_delay: int = 5,
    area: str | None = None,
) -> pd.Series:
    """
    Fetch the electricity demand time series from the ENTSO-E API.

    This function retrieves the hourly electricity demand time series
    for a specified country using the ENTSO-E API, whose client retries
    the request after connection errors. The periods that ENTSO-E
    answers with an error of the server are split into months and days,
    and the days that still fail are left out (see _query_load).
    The errors of the requests are raised without the API key, which
    their URL has.
    The data is returned as a
    pandas Series with the time index in the time zone of the country
    and the values in MW.

    Parameters
    ----------
    api_key : str
        The API key for the ENTSO-E API.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.
    start_date_and_time : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date_and_time : pandas.Timestamp
        The end date and time of the data retrieval.
    retries : int, optional
        The number of attempts, in case of connection errors.
    retry_delay : int, optional
        The delay between attempts in seconds.
    area : str | None, optional
        The area of ENTSO-E, such as GB_NIR for Northern Ireland,
        instead of the country of the code.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.
    """
    # Get the area of ENTSO-E: the ISO Alpha-2 code of the country, if
    # no other area is given.
    if area is None:
        area = utils.codes.get_iso_alpha_2_code(iso_alpha_3_code)

    # Define the ENTSO-E API client, which retries after connection
    # errors.
    client = EntsoePandasClient(
        api_key=api_key, retry_count=retries, retry_delay=retry_delay
    )

    try:
        return _query_load(
            client,
            area,
            start_date_and_time,
            end_date_and_time,
            _SPLITS,
        )

    except NoMatchingDataError:
        # If the data is not available, skip to the next country.
        logging.warning(
            f"No data available for {iso_alpha_3_code} between "
            f"{start_date_and_time.date()} and {end_date_and_time.date()}."
        )

        return pd.Series()

    except requests.exceptions.RequestException as error:
        # The message of the error has the URL of the request, with the
        # API key, so the error is raised again without it, and without
        # the original error, which would show it in the logs.
        raise type(error)(
            str(error).replace(api_key, "***"), response=error.response
        ) from None
