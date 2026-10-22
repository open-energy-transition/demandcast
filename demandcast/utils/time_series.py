"""
License: AGPL-3.0.

Description:

    This module provides functions to harmonize time series data by
    adding missing time steps, resampling the time resolution, and
    interpolating missing values. It also includes functions to check
    data quality and clean data.
"""

import datetime
import itertools
import logging
import os
from typing import Any

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


def add_missing_time_steps(
    time_series: pd.Series, local_time_zone: datetime.tzinfo
) -> pd.Series:
    """
    Add the missing time steps to a time series.

    This function checks if the time series has the expected number of
    time steps for a given year and adds the missing time steps if
    necessary. It assumes that the time series has a constant time
    resolution and that the time series is in the local time zone.

    Parameters
    ----------
    time_series : pandas.Series
        Original time series.
    local_time_zone : datetime.tzinfo
        Local time zone of the time series.

    Returns
    -------
    time_series : pandas.Series
        Time series of interest with the missing time steps added.
    """
    # Get the time resolution of the time series.
    time_resolution = time_series.index.to_series().diff().min()

    # Get the year of the time series.
    year = pd.DatetimeIndex(time_series.index).year[0]

    # Calculate the expected number of time steps in the time series.
    expected_number_of_time_steps = int(
        (8760 if year % 4 != 0 else 8784)
        * pd.Timedelta("1h")
        / time_resolution
    )

    # Check if there are less time steps than expected.
    if len(time_series) < expected_number_of_time_steps:
        logging.warning(
            f"Added {expected_number_of_time_steps - len(time_series)} "
            f"missing time steps out of {expected_number_of_time_steps}."
        )

        # Define the full time index for the time series in the local
        # time zone.
        full_local_time_index = pd.date_range(
            start=str(year),
            end=str(year + 1),
            freq=time_resolution,
            tz=local_time_zone,
        )[:-1]

        # Reindex the time series to include the missing time steps.
        time_series = time_series.reindex(full_local_time_index)

    return time_series


def resample_time_resolution(
    time_series: pd.Series, target_time_resolution: str = "1h"
) -> pd.Series:
    """
    Resample the time resolution of a time series.

    This function checks if the time resolution of the time series is
    less than the target time resolution and resamples the time series
    to the target time resolution if necessary. It assumes that the
    time series has a constant time resolution.

    Parameters
    ----------
    time_series : pandas.Series
        Original time series.
    target_time_resolution : str, optional
        Target time resolution of the time series.

    Returns
    -------
    time_series : pandas.Series
        Resampled time series.
    """
    # Get the time resolution of the time series.
    time_resolution = time_series.index.to_series().diff().min()

    # Check if the time resolution of the time series is less than the
    # target time resolution.
    if time_resolution < pd.Timedelta(target_time_resolution):
        # Resample the time series to the target time resolution.
        time_series = time_series.resample(target_time_resolution).mean()

        # Write the resampling information to the log file.
        logging.warning(
            "Resampled the time series from "
            f"{time_resolution.total_seconds() / 3600}h to "
            f"{target_time_resolution}."
        )

    return time_series


def linearly_interpolate(time_series: pd.Series) -> pd.Series:
    """
    Linearly interpolate the missing values in a time series.

    This function replaces isolated NaN values in the time series with
    the average of the previous and next values. It assumes that the
    time series has a constant time resolution and that the missing
    values are isolated (i.e., not part of a larger block of NaN
    values).

    Parameters
    ----------
    time_series : pandas.Series
        Original time series.

    Returns
    -------
    time_series : pandas.Series
        Time series of interest with the missing values interpolated.
    """
    # Get the number of original non-null values.
    original_non_null_values = time_series.notna().sum()

    # Where there is a NaN value, replace it with the average of the
    # previous and next values. This takes care of replacing isolated
    # NaN values.
    time_series[time_series.isna()] = (
        time_series.shift(-1) + time_series.shift(1)
    ) / 2

    # Get the number of interpolated values.
    interpolated_values = time_series.notna().sum() - original_non_null_values

    if interpolated_values > 0:
        # Write the number of interpolated values to the log file.
        logging.warning(
            f"Interpolated {interpolated_values} isolated missing values."
        )

    return time_series


def check_time_series_data_quality(time_series: pd.Series) -> None:
    """
    Check the data quality of a time series.

    This function checks for missing values, duplicated time steps,
    and the frequency of the time series. It logs warnings if any
    issues are found.

    Parameters
    ----------
    time_series : pandas.Series
        Original time series.
    """
    # Check if there are any missing values in the time series.
    if time_series.isna().sum() > 0:
        logging.warning(
            f"There are {time_series.isna().sum()} missing values in "
            "the time series."
        )

    # Check if there are any duplicated time steps in the time series.
    if time_series.index.duplicated().sum() > 0:
        logging.warning(
            f"There are {time_series.index.duplicated().sum()} duplicated "
            "time steps in the time series."
        )

    # Check the frequency of the time series.
    time_step_difference_values = (
        time_series.index.to_series()
        .diff()
        .value_counts()
        .rename("Occurrences")
        .rename_axis("Time step difference")
    )
    if len(time_step_difference_values) > 1:
        logging.warning(
            f"The time step differences are:\n{time_step_difference_values}."
        )
    else:
        logging.info(
            "The time series has a constant frequency of "
            f"{time_step_difference_values.index[0]}."
        )


def harmonize_time_series(
    time_series: pd.Series,
    local_time_zone: datetime.tzinfo,
    resample: bool = True,
    target_time_resolution: str = "1h",
    interpolate_missing_values: bool = True,
) -> pd.Series:
    """
    Harmonize a given time series.

    This function adds missing time steps to the time series, resamples
    the time resolution if necessary, and interpolates isolated missing
    values. It also checks the data quality of the time series.

    Parameters
    ----------
    time_series : pandas.Series
        The original time series.
    local_time_zone : datetime.tzinfo
        Local time zone of the time series.
    resample : bool, optional
        If True, resample the time series to the target time resolution.
    target_time_resolution : str, optional
        Target time resolution of the time series.
    interpolate_missing_values : bool, optional
        If True, interpolate isolated missing values in the time series.

    Returns
    -------
    time_series : pandas.Series
        The harmonized time series.
    """
    # Add the missing time steps to the time series.
    time_series = add_missing_time_steps(time_series, local_time_zone)

    # Resample the time resolution of the time series.
    if resample:
        time_series = resample_time_resolution(
            time_series, target_time_resolution=target_time_resolution
        )

    # Linearly interpolate the isolated missing values.
    if interpolate_missing_values:
        time_series = linearly_interpolate(time_series)

    return time_series


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
