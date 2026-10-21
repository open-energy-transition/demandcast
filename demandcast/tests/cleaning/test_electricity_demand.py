"""
License: AGPL-3.0.

Description:

    Tests for the cleaning of the processed electricity demand, with
    synthetic time series made for each rule.
"""

import os

import cleaning.electricity_demand
import numpy as np
import pandas as pd
import pytest
import utils.config

pytestmark = pytest.mark.usefixtures("tmp_folders", "frozen_now")


def _demand(start: str, periods: int, freq: str = "1h") -> pd.Series:
    """
    Make a demand of about 1000 MW with a daily cycle.

    Each value is unique, so that no value repeats and no day copies
    another one.

    Returns
    -------
    pandas.Series
        The demand, at times in UTC.
    """
    times = pd.date_range(start, periods=periods, freq=freq)
    hours = (times - times[0]) / pd.Timedelta(hours=1)
    values = 1000 + 100 * np.sin(2 * np.pi * hours / 24) + 0.001 * hours
    return pd.Series(np.asarray(values), index=times)


def _clean(demand: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    """
    Save a processed demand of India, clean it and read what is removed.

    Returns
    -------
    tuple[pandas.Series, pandas.DataFrame]
        The cleaned demand and the periods of the removed values.
    """
    file_path = utils.config.get_electricity_demand_file_path(
        "processed", "IND", "test"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    demand.index.name = "Time (UTC)"
    demand.name = "Load (MW)"
    demand.to_frame().to_parquet(file_path)

    cleaned = cleaning.electricity_demand.clean_data("IND", "test")

    removed = pd.read_parquet(
        utils.config.get_electricity_demand_file_path(
            "cleaned", "IND", "test"
        ).removesuffix(".parquet")
        + "_removed.parquet"
    )
    return cleaned, removed


def _removed_times(removed: pd.DataFrame, rule: str) -> list[str]:
    """
    Get the periods that a rule removes.

    Returns
    -------
    list[str]
        The start and end of each period, as "HH:MM-HH:MM" on the day.
    """
    periods = removed[removed["rule"] == rule]
    return [
        f"{start:%Y-%m-%d %H:%M}/{end:%Y-%m-%d %H:%M}"
        for start, end in zip(periods["start"], periods["end"], strict=True)
    ]


def test_clean_data_without_errors():
    """Test that a clean hourly demand is kept as it is."""
    demand = _demand("2024-01-01 01:00", 24 * 10)

    cleaned, removed = _clean(demand)

    pd.testing.assert_series_equal(
        cleaned, demand, check_freq=False, check_names=False
    )
    assert removed.empty
    assert removed.columns.tolist() == ["start", "end", "rule", "values"]


def test_clean_data_resamples_to_hours():
    """Test that the values of each hour are averaged at its end."""
    demand = _demand("2024-01-01 00:15", 4 * 24 * 3, "15min")

    cleaned, _ = _clean(demand)

    first_hour = demand["2024-01-01 00:15":"2024-01-01 01:00"].mean()
    assert cleaned.index[0] == pd.Timestamp("2024-01-01 01:00")
    assert cleaned.iloc[0] == pytest.approx(first_hour)
    assert len(cleaned) == 24 * 3


def test_clean_data_with_half_hours():
    """Test that hourly values on the half hour become full hours."""
    # The ends of the hours of India (UTC+5:30) are on the half hour in
    # UTC.
    demand = _demand("2024-01-01 00:30", 24 * 3)

    cleaned, _ = _clean(demand)

    assert pd.DatetimeIndex(cleaned.index).minute.unique().tolist() == [0]
    assert cleaned.iloc[0] == pytest.approx(demand.iloc[0])


def test_future_and_non_positive_values():
    """Test that future, zero and negative values are removed."""
    demand = _demand("2025-12-20 01:00", 24 * 20)
    demand.iloc[[10, 11]] = [0.0, -5.0]

    _, removed = _clean(demand)

    # Today is 2026-01-02 03:04 in the tests.
    assert _removed_times(removed, "non_positive") == [
        "2025-12-20 11:00/2025-12-20 12:00"
    ]
    assert _removed_times(removed, "future") == [
        "2026-01-02 04:00/2026-01-09 00:00"
    ]


def test_implausible_values():
    """Test that values far above the month around them are removed."""
    demand = _demand("2024-01-01 01:00", 24 * 40)
    # A value in kW instead of MW.
    demand.iloc[500] *= 1000

    _, removed = _clean(demand)

    assert _removed_times(removed, "implausible") == [
        "2024-01-21 21:00/2024-01-21 21:00"
    ]


def test_frozen_values():
    """Test that a value kept for 6 hours is removed, not 5 hours."""
    demand = _demand("2024-01-01 01:00", 24 * 10)
    demand.iloc[30:36] = 950.0
    demand.iloc[100:105] = 960.0

    _, removed = _clean(demand)

    assert _removed_times(removed, "frozen") == [
        "2024-01-02 07:00/2024-01-02 12:00"
    ]


def test_copied_days():
    """Test that a day that repeats an earlier day is removed."""
    demand = _demand("2024-01-01 01:00", 24 * 10)
    # The third local day of India repeats the first one.
    times = (
        pd.DatetimeIndex(demand.index)
        .tz_localize("UTC")
        .tz_convert("Asia/Kolkata")
    )
    first = demand[times.date == pd.Timestamp("2024-01-02").date()]
    third = times.date == pd.Timestamp("2024-01-04").date()
    demand[third] = first.to_numpy()

    _, removed = _clean(demand)

    assert _removed_times(removed, "copied_day") == [
        "2024-01-03 19:00/2024-01-04 18:00"
    ]


@pytest.mark.parametrize(
    ("freq", "factor", "is_spike"),
    [
        # A value twice the hours around it is a spike, not 30% more.
        ("1h", 2.0, True),
        ("1h", 1.3, False),
        # Every 15 minutes, a value 25% below the others is a spike.
        ("15min", 0.75, True),
        ("15min", 0.9, False),
    ],
)
def test_spikes(freq, factor, is_spike):
    """Test that a value that leaves and comes back is a spike."""
    demand = _demand("2024-01-01 01:00", 24 * 4 * 10, freq)
    demand.iloc[200] *= factor

    _, removed = _clean(demand)

    expected = f"{demand.index[200]:%Y-%m-%d %H:%M}"
    assert _removed_times(removed, "spike") == (
        [f"{expected}/{expected}"] if is_spike else []
    )


def test_peaks_and_steps_are_not_spikes():
    """Test that a peak of hours and a step of the level are kept."""
    demand = _demand("2024-01-01 01:00", 24 * 10)
    # A peak of three hours, and a lasting step of 60%.
    demand.iloc[50:53] *= 2
    demand.iloc[150:] *= 1.6

    _, removed = _clean(demand)

    assert removed.empty


def test_hours_with_too_few_values():
    """Test that an hour with less than half its values is removed."""
    demand = _demand("2024-01-01 00:15", 4 * 24 * 3, "15min")
    # Keep one value of 4 in the hour that ends at 2024-01-02 06:00.
    demand = demand.drop(demand["2024-01-02 05:15":"2024-01-02 05:45"].index)

    cleaned, removed = _clean(demand)

    assert pd.Timestamp("2024-01-02 06:00") not in cleaned.index
    assert _removed_times(removed, "low_coverage") == [
        "2024-01-02 06:00/2024-01-02 06:00"
    ]


def test_change_of_resolution():
    """Test that each part of a demand is cleaned at its resolution."""
    # Every 30 minutes for 3 days, then every 5 minutes for 3 days.
    half_hours = _demand("2024-01-01 00:30", 2 * 24 * 3, "30min")
    five_minutes = _demand("2024-01-04 00:05", 12 * 24 * 3, "5min")
    # A value 30% above the half hours around it is not a spike, and a
    # value 25% above the 5 minutes around it is.
    half_hours.iloc[50] *= 1.3
    five_minutes.iloc[500] *= 1.25
    demand = pd.concat([half_hours, five_minutes])

    cleaned, removed = _clean(demand)

    # Every hour is kept, also those with two values of 30 minutes.
    assert len(cleaned) == 24 * 6
    assert _removed_times(removed, "low_coverage") == []
    expected = f"{five_minutes.index[500]:%Y-%m-%d %H:%M}"
    assert _removed_times(removed, "spike") == [f"{expected}/{expected}"]


def _local_days(removed: pd.DataFrame, rule: str) -> set[str]:
    """
    Get the days of India whose values a rule removes.

    Returns
    -------
    set[str]
        The days, in the time of India, of the times of the values.
    """
    periods = removed[removed["rule"] == rule]
    days = set()
    for start, end in zip(periods["start"], periods["end"], strict=True):
        times = pd.date_range(start, end, freq="1h", tz="UTC")
        local = times.tz_convert("Asia/Kolkata")
        days |= {f"{day:%Y-%m-%d}" for day in local.normalize()}
    return days


def _days(start: str, end: str) -> set[str]:
    """
    Get the days from a start to an end, both included.

    Returns
    -------
    set[str]
        The days.
    """
    return {f"{day:%Y-%m-%d}" for day in pd.date_range(start, end)}


def _scale_days(demand: pd.Series, start: str, end: str, factor: float):
    """Scale the values of the days of India from a start to an end."""
    days = (
        pd.DatetimeIndex(demand.index)
        .tz_localize("UTC")
        .tz_convert("Asia/Kolkata")
        .tz_localize(None)
        .normalize()
    )
    within = (days >= pd.Timestamp(start)) & (days <= pd.Timestamp(end))
    demand[within] *= factor


def test_level_drops():
    """
    Test that a month far below the level of other years is removed.

    A drop of 10 days and a drop in the lockdowns of 2020 are kept.
    """
    demand = _demand("2019-01-01 01:00", 24 * 365 * 5)
    _scale_days(demand, "2022-06-01", "2022-06-30", 0.25)
    _scale_days(demand, "2022-10-01", "2022-10-10", 0.25)
    _scale_days(demand, "2020-04-01", "2020-04-30", 0.25)

    _, removed = _clean(demand)

    assert _local_days(removed, "level_drop") == _days(
        "2022-06-01", "2022-06-30"
    )


def test_level_drops_of_neighbouring_years():
    """
    Test that the drops of two years do not hide each other.

    The drop of 2023 is far below the level of the other years, and
    once it is left out of the level, so is that of 2021.
    """
    demand = _demand("2021-01-01 01:00", 24 * 365 * 4)
    _scale_days(demand, "2021-10-01", "2021-10-31", 0.35)
    _scale_days(demand, "2023-10-01", "2023-10-31", 0.35)

    _, removed = _clean(demand)

    assert _local_days(removed, "level_drop") == _days(
        "2021-10-01", "2021-10-31"
    ) | _days("2023-10-01", "2023-10-31")
