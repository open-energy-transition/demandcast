# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to harmonize time series data by
    adding missing time steps, resampling the time resolution, and
    interpolating missing values. It also includes functions to check
    data quality and clean data.
"""

import datetime
import logging

import pandas


def add_missing_time_steps(
    time_series: pandas.Series, local_time_zone: datetime.tzinfo
) -> pandas.Series:
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
    year = time_series.index.year[0]

    # Calculate the expected number of time steps in the time series.
    expected_number_of_time_steps = int(
        (8760 if year % 4 != 0 else 8784)
        * pandas.Timedelta("1h")
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
        full_local_time_index = pandas.date_range(
            start=str(year),
            end=str(year + 1),
            freq=time_resolution,
            tz=local_time_zone,
        )[:-1]

        # Reindex the time series to include the missing time steps.
        time_series = time_series.reindex(full_local_time_index)

    return time_series


def resample_time_resolution(
    time_series: pandas.Series, target_time_resolution: str = "1h"
) -> pandas.Series:
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
    if time_resolution < pandas.Timedelta(target_time_resolution):
        # Resample the time series to the target time resolution.
        time_series = time_series.resample(target_time_resolution).mean()

        # Write the resampling information to the log file.
        logging.warning(
            "Resampled the time series from "
            f"{time_resolution.total_seconds() / 3600}h to "
            f"{target_time_resolution}."
        )

    return time_series


def linearly_interpolate(time_series: pandas.Series) -> pandas.Series:
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


def check_time_series_data_quality(time_series: pandas.Series) -> None:
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

    # Chech the frequency of the time series.
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
    time_series: pandas.Series,
    local_time_zone: datetime.tzinfo,
    resample: bool = True,
    target_time_resolution: str = "1h",
    interpolate_missing_values: bool = True,
) -> pandas.Series:
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


def convert_from_yearly_to_hourly(
    time_series: pandas.Series, time_zone: datetime.tzinfo
) -> pandas.Series:
    """
    Convert a yearly time series to an hourly time series.

    Parameters
    ----------
    time_series : pandas.Series
        The yearly time series to convert.
    time_zone : datetime.tzinfo
        The time zone of the time series.

    Returns
    -------
    pandas.Series
        The hourly time series.
    """
    # Define a new index with hourly frequency in the local time zone.
    index = pandas.date_range(
        start=(f"{str(time_series.index.min())}-01-01"),
        end=(f"{str(time_series.index.max())}-12-31 23:00:00"),
        freq="h",
        tz=time_zone,
    )

    return pandas.Series(index.year.map(time_series), index=index)


def clean_data(
    time_series: pandas.Series, variable_name: str
) -> pandas.Series:
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
    if time_series.index.tz is None:
        raise ValueError("The time series must be timezone-aware.")
    else:
        # Convert the time zone of the electricity demand time series to
        # UTC and remove the time zone information.
        time_series.index = time_series.index.tz_convert("UTC").tz_localize(
            None
        )

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
