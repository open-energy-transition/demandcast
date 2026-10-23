"""
License: AGPL-3.0.

Description:

    This module provides functions for time series: the split of a
    period into shorter ones, the local time of the starts of
    intervals, the local years, the conversion of yearly values into
    hourly ones and their saving, and the cleaning of the data.
"""

import datetime
import itertools
import os
from typing import Any

import numpy as np
import pandas as pd


def split_period(
    start_date: datetime.date,
    end_date: datetime.date,
    frequency: str,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Split a period into shorter periods.

    The periods start at the start date and at each start of a period
    of the frequency, and end at the start of the next one or at the end
    date. A period without duration has no shorter periods.

    Parameters
    ----------
    start_date : datetime.date
        The start of the period.
    end_date : datetime.date
        The end of the period.
    frequency : str
        The frequency of the starts of the shorter periods, as in
        pandas.date_range.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The start and end of each shorter period.
    """
    boundaries = pd.date_range(start_date, end_date, freq=frequency)
    boundaries = boundaries.union(
        pd.to_datetime([start_date, end_date])
    ).drop_duplicates()
    return list(itertools.pairwise(boundaries))


def localize_interval_starts(
    time_series: pd.Series,
    time_zone: str | datetime.tzinfo,
    interval: pd.Timedelta,
    ambiguous: Any = "raise",
    nonexistent: str = "raise",
) -> pd.Series:
    """
    Localize the starts of intervals and mark their ends.

    Many data sources give the value of each interval at its start, in
    local time, while DemandCast marks each value with the end of its
    interval. The starts are localized first and the interval is then
    added in absolute time, so that the ends are right also when
    daylight saving time starts or ends.

    Parameters
    ----------
    time_series : pandas.Series
        The time series, with the starts of the intervals in local time
        and without time zone.
    time_zone : str | datetime.tzinfo
        The time zone of the starts.
    interval : pandas.Timedelta
        The length of the intervals.
    ambiguous : Any, optional
        How to localize the ambiguous starts, as in
        pandas.Series.tz_localize.
    nonexistent : str, optional
        How to localize the nonexistent starts, as in
        pandas.Series.tz_localize.

    Returns
    -------
    pandas.Series
        The time series, with the ends of the intervals in the time
        zone.
    """
    localized_time_series = time_series.tz_localize(
        time_zone, ambiguous=ambiguous, nonexistent=nonexistent
    )
    localized_time_series.index = localized_time_series.index + interval
    return localized_time_series


def get_local_year_bounds(
    year: int, time_zone: datetime.tzinfo
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Get the start and the end of a year in local time.

    A year can start at a midnight that does not exist, when daylight
    saving time starts then, as in Peru on 1990-01-01, so it starts at
    the first time after it.

    Parameters
    ----------
    year : int
        The year.
    time_zone : datetime.tzinfo
        The local time zone.

    Returns
    -------
    tuple[pandas.Timestamp, pandas.Timestamp]
        The local midnights of January 1 of the year and of the next
        year, in UTC.
    """

    def new_year(year: int) -> pd.Timestamp:
        return (
            pd.Timestamp(year, 1, 1)
            .tz_localize(
                time_zone, ambiguous=False, nonexistent="shift_forward"
            )
            .tz_convert("UTC")
        )

    return new_year(year), new_year(year + 1)


def get_local_years(
    times: pd.DatetimeIndex, time_zone: datetime.tzinfo
) -> pd.Index:
    """
    Get the local year of the hours that end at the given times.

    The year of an hour is that of its start in local time, so that the
    hour that ends at midnight on January 1 belongs to the year before.

    Parameters
    ----------
    times : pandas.DatetimeIndex
        The ends of the hours, with a time zone or in UTC without one.
    time_zone : datetime.tzinfo
        The local time zone.

    Returns
    -------
    pandas.Index
        The local year of each hour.
    """
    times = pd.DatetimeIndex(times)
    if times.tz is None:
        times = times.tz_localize("UTC")
    return (times - pd.Timedelta(hours=1)).tz_convert(time_zone).year


def convert_from_yearly_to_hourly(
    time_series: pd.Series, time_zone: datetime.tzinfo
) -> pd.Series:
    """
    Convert a yearly time series to an hourly time series.

    The hours are stamped at their ends, like the electricity demand,
    and take the value of the local year of their starts.

    Parameters
    ----------
    time_series : pandas.Series
        The yearly time series to convert.
    time_zone : datetime.tzinfo
        The time zone of the time series.

    Returns
    -------
    pandas.Series
        The hourly time series, at the ends of the hours of the local
        years, from 01:00 on January 1 of the first year to midnight on
        January 1 after the last year, in the local time zone.
    """
    start, _ = get_local_year_bounds(int(time_series.index.min()), time_zone)
    _, end = get_local_year_bounds(int(time_series.index.max()), time_zone)
    index = pd.date_range(
        start + pd.Timedelta(hours=1), end, freq="h"
    ).tz_convert(time_zone)

    return pd.Series(
        get_local_years(index, time_zone).map(time_series.to_dict()),
        index=index,
    )


def save_yearly_values(
    yearly_values: pd.Series,
    years: list[int],
    variable_name: str,
    file_path_without_ext: str,
    time_zone: datetime.tzinfo,
) -> None:
    """
    Save yearly values as hourly values, keeping the other saved years.

    The values of the given years are converted to the hours of their
    local years and cleaned, and replace the saved values of those
    years. Both files are replaced only once they are written.

    Parameters
    ----------
    yearly_values : pandas.Series
        The value of each year.
    years : list[int]
        The years to save.
    variable_name : str
        The name of the variable.
    file_path_without_ext : str
        The path of the Parquet and CSV files, without extension.
    time_zone : datetime.tzinfo
        The time zone of the local years.
    """
    time_series = clean_data(
        convert_from_yearly_to_hourly(
            yearly_values[yearly_values.index.isin(years)], time_zone
        ),
        variable_name,
    )

    if os.path.exists(file_path_without_ext + ".parquet"):
        saved = pd.read_parquet(file_path_without_ext + ".parquet")[
            time_series.name
        ]
        saved_years = get_local_years(pd.DatetimeIndex(saved.index), time_zone)
        saved = saved.loc[
            ~saved_years.isin(
                get_local_years(pd.DatetimeIndex(time_series.index), time_zone)
            )
        ]
        if not saved.empty:
            time_series = pd.concat([saved, time_series]).sort_index()

    for extension in (".parquet", ".csv"):
        temporary_path = file_path_without_ext + ".tmp" + extension
        if extension == ".parquet":
            time_series.to_frame().to_parquet(temporary_path)
        else:
            time_series.to_csv(temporary_path)
        os.replace(temporary_path, file_path_without_ext + extension)


def clean_data(time_series: pd.Series, variable_name: str) -> pd.Series:
    """
    Clean the time series.

    This function removes NaN values, zero values, and duplicated time
    steps from the time series. It also ensures that the time series is
    converted to UTC and has a name for the index and the series.

    Parameters
    ----------
    time_series : pandas.Series
        Original time series.
    variable_name : str
        The name of the variable in the time series.

    Returns
    -------
    time_series : pandas.Series
        Time series of interest without NaN, zero values, and duplicated
        time steps.

    Raises
    ------
    ValueError
        If the time series is not timezone-aware.
    """
    # Check if the time series is timezone-aware.
    if (
        not isinstance(time_series.index, pd.DatetimeIndex)
        or time_series.index.tz is None
    ):
        raise ValueError("The time series must be timezone-aware.")
    # Convert the time zone of the electricity demand time series to
    # UTC and remove the time zone information.
    time_series = time_series.tz_convert("UTC").tz_localize(None)

    # Set the name of the index and the series.
    time_series.index.name = "Time (UTC)"
    time_series.name = variable_name

    # Remove timestamps with NaT values.
    time_series = time_series[time_series.index.notna()]

    # Remove NaN and zero values from the time series.
    time_series = time_series[time_series.notna() & (time_series != 0)]

    # Remove duplicated time steps from the time series.
    time_series = time_series[~time_series.index.duplicated()]

    # Sort the time series by index.
    time_series = time_series.sort_index()

    return time_series


def keep_latest_download(values: pd.Series, files: pd.Series) -> pd.Series:
    """
    Keep one value of each time, from the latest download of the data.

    The files that were downloaded manually can overlap: a later
    download repeats times of an earlier one, sometimes with values
    that the data source revised. The files are ranked by the last time
    at which they have a number, so that the latest download comes
    last. Each time takes the number of the latest file that has one,
    or no number if no file has one; within a file, the first value of
    a time is kept.

    Parameters
    ----------
    values : pandas.Series
        The values of all the files, indexed by time, or by keys and
        time, such as the state and the time, with the time last.
    files : pandas.Series
        The name of the file of each value, in the same order.

    Returns
    -------
    pandas.Series
        One value of each index, sorted by the index.
    """
    times = values.index.get_level_values(-1)
    file_names = np.asarray(files)
    has_number = values.notna().to_numpy()
    last_times = (
        pd.Series(times[has_number]).groupby(file_names[has_number]).max()
    )
    ranks = (
        pd.Series(file_names)
        .map(last_times.rank(method="first"))
        .fillna(0)
        .to_numpy()
    )
    # Sort by whether there is a number, then by the rank of the file,
    # then by the position in reverse, so that the last row of each
    # index is the one to keep.
    order = np.lexsort((-np.arange(len(values)), ranks, has_number))
    ordered = values.iloc[order]
    return ordered[~ordered.index.duplicated(keep="last")].sort_index()
