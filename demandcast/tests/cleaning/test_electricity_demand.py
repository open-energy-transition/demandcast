"""
License: AGPL-3.0.

Description:

    Tests for the cleaning of the processed electricity demand.
"""

import os

import cleaning.electricity_demand
import pandas as pd
import pytest
import utils.config


def _write_processed_data(time_series: pd.Series) -> None:
    """Write the processed electricity demand of a test data source."""
    file_path = utils.config.get_electricity_demand_file_path(
        "processed", "IND", "test"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    time_series.index.name = "Time (UTC)"
    time_series.name = "Load (MW)"
    time_series.to_frame().to_parquet(file_path)


def test_clean_data(tmp_folders):
    """Test that the values of each hour are averaged at its end."""
    # Values every 15 minutes, at the ends of the intervals, and an
    # hour without values.
    times = pd.DatetimeIndex(
        pd.date_range("2024-01-01 00:15", "2024-01-01 01:00", freq="15min")
    ).append(pd.DatetimeIndex(["2024-01-01 03:00"]))
    _write_processed_data(pd.Series([1.0, 2.0, 3.0, 4.0, 10.0], index=times))

    cleaned = cleaning.electricity_demand.clean_data("IND", "test")

    expected = pd.Series(
        [2.5, 10.0],
        index=pd.DatetimeIndex(
            ["2024-01-01 01:00", "2024-01-01 03:00"], name="Time (UTC)"
        ),
        name="Load (MW)",
    )
    pd.testing.assert_series_equal(cleaned, expected, check_freq=False)
    saved = pd.read_parquet(
        os.path.join(
            tmp_folders["cleaned_electricity_demand_folder"],
            "IND_test.parquet",
        )
    )["Load (MW)"]
    pd.testing.assert_series_equal(saved, expected, check_freq=False)


@pytest.mark.usefixtures("tmp_folders")
def test_clean_data_with_half_hours():
    """Test that hourly values on the half hour become full hours."""
    # The ends of the hours of India (UTC+5:30) are on the half hour in
    # UTC.
    times = pd.DatetimeIndex(["2024-01-01 00:30", "2024-01-01 01:30"])
    _write_processed_data(pd.Series([100.0, 200.0], index=times))

    cleaned = cleaning.electricity_demand.clean_data("IND", "test")

    assert pd.DatetimeIndex(cleaned.index).strftime("%H:%M").tolist() == [
        "01:00",
        "02:00",
    ]
    assert cleaned.tolist() == [100.0, 200.0]
