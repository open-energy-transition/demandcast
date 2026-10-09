"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Transmission System Operator of Cyprus
    (TSOC). The data is the total demand every 15 minutes in MW, which
    TSOC publishes in one Excel file per year from 2018, on the archive
    page below. The data is retrieved in one-year intervals, for the
    years that have ended.

    The times of the files do not always follow the same convention:
    some years are 15 or 30 minutes early, and daylight saving time is
    applied wrongly in 2023 and 2024. The module corrects them with the
    shifts that align the files with the archive page, which displays
    Cyprus local time, and checks the result against the time of the
    estimated solar generation of the files: a remaining shift of whole
    hours is corrected, with a warning.

    Source: https://tsoc.org.cy/electrical-system/archive-total-daily-system-generation-on-the-transmission-system/
"""

import datetime
import logging
import urllib.parse

import numpy as np
import pandas as pd
import utils.fetcher

# The shift in minutes to add to the times of the files, from each day
# on, to get the start of each interval in Cyprus local time. They align
# the files with the archive page, and agree with the time of the solar
# generation.
TIME_SHIFTS = {
    "2018-01-01": 0,
    "2019-01-01": 30,
    "2021-08-01": 15,
    "2023-01-01": 0,
    "2023-03-27": -60,
    "2023-10-30": 0,
    "2024-03-31": 60,
    "2024-10-27": 0,
    "2024-10-29": 60,
    "2025-01-01": 0,
}

# The longitude of Nicosia in degrees, for the time of the solar noon.
LONGITUDE = 33.38

# How many hours after the solar noon the middle of the daily peak of
# the estimated solar generation comes, in the years whose times are
# right.
SOLAR_DELAY = 0.2

# The fewest clear days that can show a shift of whole hours.
MINIMUM_CLEAR_DAYS = 5


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


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the TSOC website: the years that have ended, since
    the file of a year is published after it ends.

    Parameters
    ----------
    code : str
        The code of Cyprus.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the TSOC website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the Excel file of the year.
    path = (
        "/files/electrical-system/daily-system-generation/"
        f"Ημερήσια Παραγωγή Ηλεκτρικού Συστήματος - {year}.xlsx"
    )
    return "https://tsoc.org.cy" + urllib.parse.quote(path)


def _solar_noon(days: pd.DatetimeIndex) -> np.ndarray:
    """
    Calculate the time of the solar noon in Nicosia.

    Parameters
    ----------
    days : pandas.DatetimeIndex
        The days.

    Returns
    -------
    numpy.ndarray
        The time of the solar noon of each day, in hours after midnight
        in UTC.
    """
    # The approximation of the equation of time of NOAA, in minutes.
    angle = 2 * np.pi / 365 * (days.dayofyear.to_numpy() - 1)
    equation_of_time = 229.18 * (
        0.000075
        + 0.001868 * np.cos(angle)
        - 0.032077 * np.sin(angle)
        - 0.014615 * np.cos(2 * angle)
        - 0.040849 * np.sin(2 * angle)
    )
    return (720 - 4 * LONGITUDE - equation_of_time) / 60


def _middle_of_solar_peak(day: pd.DataFrame) -> float:
    """
    Find the middle of the daily peak of the solar generation.

    The middle of the peak is halfway between the times when the solar
    generation rises above and falls below half of its maximum.

    Parameters
    ----------
    day : pandas.DataFrame
        The solar generation of a day ("solar") at the middle of each
        interval, in hours of local time ("hour").

    Returns
    -------
    float
        The middle of the peak in hours of local time, or NaN if it
        cannot be found.
    """
    hours = day["hour"].to_numpy()
    solar = np.nan_to_num(day["solar"].to_numpy())
    half = solar.max() / 2
    above = np.flatnonzero(solar >= half)
    if half <= 0 or above[0] == 0 or above[-1] == len(solar) - 1:
        return np.nan
    first, last = above[0], above[-1]

    # Interpolate the times of the crossings of half of the maximum.
    rise = hours[first - 1] + (half - solar[first - 1]) / (
        solar[first] - solar[first - 1]
    ) * (hours[first] - hours[first - 1])
    fall = hours[last] + (solar[last] - half) / (
        solar[last] - solar[last + 1]
    ) * (hours[last + 1] - hours[last])
    return float((rise + fall) / 2)


def _utc_offset(days: pd.Series) -> pd.Series:
    """
    Get the offset of Cyprus local time from UTC at the start of days.

    Parameters
    ----------
    days : pandas.Series
        The days, at midnight.

    Returns
    -------
    pandas.Series
        The offset of each day in hours.
    """
    offsets = {}
    for day in days.unique():
        offset = pd.Timestamp(day).tz_localize("Asia/Nicosia").utcoffset()
        offsets[day] = (offset or pd.Timedelta(0)) / pd.Timedelta(hours=1)
    return days.map(offsets)


def _correct_whole_hours(
    local_start: pd.Series, distributed: pd.Series, year: int
) -> pd.Series:
    """
    Correct the shifts of whole hours that the solar generation shows.

    The middle of the peak of the estimated distributed generation,
    mostly solar, is compared with the solar noon on the clear days of
    each month, separately before and after a change of daylight saving
    time. A difference of one hour or more, over at least a few clear
    days, moves the times by whole hours, with a warning.

    Parameters
    ----------
    local_start : pandas.Series
        The start of each interval in Cyprus local time.
    distributed : pandas.Series
        The estimated distributed generation of each interval in MW.
    year : int
        The year of the file.

    Returns
    -------
    pandas.Series
        The corrected starts of the intervals.
    """
    data = pd.DataFrame(
        {
            "day": local_start.dt.normalize(),
            "hour": local_start.dt.hour + local_start.dt.minute / 60 + 0.125,
            "distributed": distributed,
        }
    )
    data["offset"] = _utc_offset(data["day"])

    # The solar generation is the generation above the minimum of the
    # day.
    data["solar"] = data["distributed"] - data.groupby("day")[
        "distributed"
    ].transform("min")

    # Find the middle of the solar peak of the clear days, whose peak is
    # close to the ones of the sunniest days of their month.
    peaks = data.groupby("day")["solar"].max()
    month_peaks = peaks.groupby(pd.DatetimeIndex(peaks.index).month).transform(
        lambda month: month.quantile(0.75)
    )
    clear_days = peaks.index[peaks >= 0.9 * month_peaks]
    middles = (
        data[data["day"].isin(clear_days)]
        .groupby(["day", "offset"])[["hour", "solar"]]
        .apply(_middle_of_solar_peak)
        .dropna()
    )

    # Compare the middles, in UTC, with the solar noon, by month and
    # offset from UTC.
    days = pd.DatetimeIndex(middles.index.get_level_values("day"))
    offsets = middles.index.get_level_values("offset").to_numpy()
    delays = middles.to_numpy() - offsets - _solar_noon(days)
    segments = pd.Series(delays - SOLAR_DELAY).groupby([days.month, offsets])
    shifts = segments.median().round()[segments.size() >= MINIMUM_CLEAR_DAYS]

    # Move the times of the segments with a shift of whole hours.
    corrected = local_start.copy()
    for (month, offset), shift in zip(
        shifts.index.tolist(), shifts.to_numpy(), strict=True
    ):
        if shift == 0:
            continue
        logging.warning(
            f"The times of the TSOC file of {year} in month {month} seem "
            f"{shift:+.0f} hours from the solar generation, and are "
            "corrected."
        )
        rows = (data["day"].dt.month == month) & (data["offset"] == offset)
        corrected[rows] = local_start[rows] - pd.Timedelta(hours=shift)
    return corrected


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the TSOC website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Cyprus.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Read the start of each interval, the total demand and the
    # estimated distributed generation, below the four rows of the
    # header.
    dataset = utils.fetcher.fetch_data(
        get_url(year),
        "excel",
        excel_kwargs={"header": None, "skiprows": 4, "usecols": [0, 6, 8]},
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    dataset.columns = ["start", "demand", "distributed"]
    # The times are stored with rounding errors of up to a second.
    dataset["start"] = pd.to_datetime(
        dataset["start"], errors="coerce"
    ).dt.round("min")
    dataset = dataset[dataset["start"].notna()].reset_index(drop=True)

    # Shift the times by the corrections of their days, to the start of
    # each interval in Cyprus local time.
    shifts = pd.Series(TIME_SHIFTS).rename(index=pd.Timestamp).sort_index()
    shift_of_rows = shifts.reindex(
        dataset["start"].dt.normalize(), method="ffill"
    ).fillna(0)
    local_start = dataset["start"] + pd.to_timedelta(
        shift_of_rows.to_numpy(), unit="min"
    )

    # Correct the shifts of whole hours that remain.
    local_start = _correct_whole_hours(
        local_start,
        pd.to_numeric(dataset["distributed"], errors="coerce"),
        year,
    )

    # Mark the end of each interval, in Cyprus local time.
    electricity_demand_time_series = pd.Series(
        pd.to_numeric(dataset["demand"]).to_numpy(),
        index=pd.DatetimeIndex(local_start + pd.Timedelta(minutes=15)),
    ).tz_localize("Asia/Nicosia", ambiguous="NaT", nonexistent="NaT")

    return electricity_demand_time_series
