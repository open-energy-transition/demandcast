# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the time_series module in the ETL
    utility package.
"""

import logging

import numpy
import pandas
import pytest
import pytz
import utils.time_series

local_time_zone = pytz.timezone("America/New_York")


@pytest.fixture
def sample_time_series():
    """
    Fixture to provide a sample time series for testing.

    This function creates a pandas Series with a datetime index and some
    missing values. The time series is defined to have a 30-minute
    resolution, spanning one year from 2023 to 2024. It contains some
    missing data points, specifically at indices 2, 3, and 10.

    Returns
    -------
    pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Define a one-year-long time series with 30-minute resolution.
    dates = pandas.date_range(
        "2023", "2024", freq="30min", tz=local_time_zone
    )[:-1]

    # Define the data.
    data = list(range(len(dates)))

    # Remove three data points, two of which are consecutive.
    data[2] = None
    data[3] = None
    data[10] = None

    return pandas.Series(data, index=dates)


def test_add_missing_time_steps(sample_time_series):
    """
    Test if the function adds missing time steps to the time series.

    This test checks if the function correctly identifies and adds
    missing time steps to the time series, ensuring that the length of
    the time series remains the same after adding the missing time step.

    Parameters
    ----------
    sample_time_series : pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Store the original length of the time series.
    original_length = len(sample_time_series)

    # Remove a time step.
    time_series = sample_time_series.drop(sample_time_series.index[20])

    # Count the number of missing data points.
    missing_data_points = time_series.isna().sum()

    # Add the missing time step back.
    filled_time_series = utils.time_series.add_missing_time_steps(
        time_series, local_time_zone
    )

    # Check if the missing time step is added.
    assert len(filled_time_series) == original_length

    # Ensure that there is one additional missing data point.
    assert filled_time_series.isna().sum() == missing_data_points + 1


def test_resample_time_resolution(sample_time_series):
    """
    Test if the function resamples the time series.

    This test checks if the function correctly resamples the time series
    to a specified time resolution, ensuring that the length of the
    resampled time series matches the expected number of time steps for
    the given resolution. For a one-year-long time series with hourly
    resolution, the expected number of time steps is 8760.

    Parameters
    ----------
    sample_time_series : pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Resample to hourly resolution.
    resampled_time_series = utils.time_series.resample_time_resolution(
        sample_time_series, "1h"
    )

    # The one-year-long time series resampled to hourly resolution
    # should have 8760 time steps.
    assert len(resampled_time_series) == 8760


def test_linearly_interpolate(sample_time_series):
    """
    Test if the function linearly interpolates missing values.

    This test checks if the function correctly interpolates missing
    values in the time series, ensuring that only isolated missing
    values are interpolated. It also verifies that the interpolation is
    performed correctly by checking specific indices in the time series.

    Parameters
    ----------
    sample_time_series : pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Check the data point expected to be interpolated.
    assert numpy.isnan(sample_time_series.iloc[10])

    # Count the number of missing data points.
    missing_data_points = sample_time_series.isna().sum()

    # Interpolate missing values where the two surrounding values are
    # known.
    interpolated_time_series = utils.time_series.linearly_interpolate(
        sample_time_series
    )

    # Check if only isolated missing values are interpolated.
    assert interpolated_time_series.isna().sum() == missing_data_points - 1

    # Check correct interpolation.
    assert numpy.isnan(interpolated_time_series.iloc[2])
    assert numpy.isnan(interpolated_time_series.iloc[3])
    assert interpolated_time_series.iloc[10] == 10


def test_harmonize_time_series(sample_time_series):
    """
    Test if the function harmonizes the time series.

    This test checks if the function correctly harmonizes the time
    series by adding missing time steps, resampling the time resolution,
    and interpolating missing values. It ensures that the resulting time
    series has no missing values and the expected number of time steps
    (8760 for a one-year-long time series with hourly resolution).

    Parameters
    ----------
    sample_time_series : pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Harmonize the time series by adding missing time steps, resampling
    # the time resolution, and interpolating missing values.
    harmonized_time_series = utils.time_series.harmonize_time_series(
        sample_time_series, local_time_zone
    )

    # Should have no missing values.
    assert harmonized_time_series.isna().sum() == 0

    # Check total number of time steps.
    assert len(harmonized_time_series) == 8760

    # Test the function when both resample and interpolate are False.
    not_harmonized_time_series = utils.time_series.harmonize_time_series(
        sample_time_series,
        local_time_zone,
        resample=False,
        interpolate_missing_values=False,
    )
    assert isinstance(not_harmonized_time_series, pandas.Series)


def test_check_time_series_data_quality_logs(caplog, sample_time_series):
    """
    Test the check_time_series_data_quality function.

    This test checks if the function correctly identifies missing values
    in the time series and logs a warning message. It uses the caplog
    fixture to capture log messages at the WARNING level.

    Parameters
    ----------
    caplog : pytest.LogCaptureFixture
        A fixture provided by pytest to capture log messages.
    sample_time_series : pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Test if the function logs a warning for missing values.
    with caplog.at_level(logging.WARNING):
        utils.time_series.check_time_series_data_quality(sample_time_series)
        assert "missing values" in caplog.text

    # Add a duplicate index and a zero value for testing.
    time_series = pandas.concat(
        [
            sample_time_series,
            pandas.Series([0], index=[sample_time_series.index[5]]),
        ]
    )

    with caplog.at_level(logging.WARNING):
        utils.time_series.check_time_series_data_quality(time_series)
        assert "missing values" in caplog.text


def test_clean_data(sample_time_series):
    """
    Test the clean_data function.

    This test checks if the clean_data function correctly cleans the
    time series by removing NaN values, zeros, and duplicate indices.
    It also verifies that the cleaned time series has the expected index
    and name.

    Parameters
    ----------
    sample_time_series : pandas.Series
        A pandas Series representing a time series with a datetime index
        and some missing values.
    """
    # Add a duplicate index and a zero value for testing.
    time_series = sample_time_series.copy()
    time_series = pandas.concat(
        [time_series, pandas.Series([0], index=[time_series.index[5]])]
    )
    time_series.iloc[1] = 0

    cleaned_time_series = utils.time_series.clean_data(
        time_series, "TestVariable"
    )

    # Should have no NaN, zeros, or duplicates.
    assert cleaned_time_series.isna().sum() == 0
    assert (cleaned_time_series == 0).sum() == 0
    assert cleaned_time_series.index.duplicated().sum() == 0
    assert cleaned_time_series.index.name == "Time (UTC)"
    assert cleaned_time_series.name == "TestVariable"

    # Remove the time zone from the index.
    cleaned_time_series.index = cleaned_time_series.index.tz_localize(None)

    # Check if the function raises an error for an timezone-naive index.
    with pytest.raises(ValueError):
        utils.time_series.clean_data(cleaned_time_series, "TestVariable")
