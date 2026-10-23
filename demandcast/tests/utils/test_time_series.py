"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the time_series module.
"""

import datetime
import itertools

import pandas as pd
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
    dates = pd.date_range("2023", "2024", freq="30min", tz=local_time_zone)[
        :-1
    ]

    # Define the data.
    data: list[int | None] = list(range(len(dates)))

    # Remove three data points, two of which are consecutive.
    data[2] = None
    data[3] = None
    data[10] = None

    return pd.Series(data, index=dates)


@pytest.mark.parametrize(
    ("start_date", "end_date", "frequency", "boundaries"),
    [
        (
            datetime.date(2023, 3, 17),
            datetime.date(2025, 1, 1),
            "YS",
            ["2023-03-17", "2024-01-01", "2025-01-01"],
        ),
        (
            datetime.date(2024, 1, 1),
            datetime.date(2024, 2, 20),
            "MS",
            ["2024-01-01", "2024-02-01", "2024-02-20"],
        ),
        (
            datetime.date(2024, 1, 1),
            datetime.date(2024, 1, 10),
            "7D",
            ["2024-01-01", "2024-01-08", "2024-01-10"],
        ),
        (datetime.date(2024, 1, 1), datetime.date(2024, 1, 1), "YS", []),
    ],
)
def test_split_period(start_date, end_date, frequency, boundaries):
    """Test that the periods start at the frequency and at the dates."""
    periods = utils.time_series.split_period(start_date, end_date, frequency)

    assert periods == list(itertools.pairwise(pd.to_datetime(boundaries)))


def test_localize_interval_starts():
    """Test that the ends are the starts plus the interval."""
    time_series = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.to_datetime(
            ["2024-03-31 01:00", "2024-03-31 01:30", "2024-03-31 03:00"]
        ),
    )

    result = utils.time_series.localize_interval_starts(
        time_series, "Europe/Paris", pd.Timedelta(minutes=30)
    )

    # Daylight saving time starts at 02:00, so the half hour that
    # starts at 01:30 ends at 03:00 in summer time.
    index = pd.DatetimeIndex(result.index)
    assert str(index.tz) == "Europe/Paris"
    assert index.tz_convert("UTC").strftime("%H:%M").tolist() == [
        "00:30",
        "01:00",
        "01:30",
    ]
    assert result.tolist() == [1.0, 2.0, 3.0]


def test_localize_interval_starts_with_ambiguous_starts():
    """Test that the ambiguous and nonexistent starts are passed on."""
    time_series = pd.Series(
        [1.0, 2.0],
        index=pd.to_datetime(["2024-10-27 02:00", "2024-03-31 02:00"]),
    )

    result = utils.time_series.localize_interval_starts(
        time_series,
        "Europe/Paris",
        pd.Timedelta(hours=1),
        ambiguous="NaT",
        nonexistent="NaT",
    )

    assert pd.isna(result.index).all()


def test_convert_from_yearly_to_hourly():
    """
    Test the conversion from yearly to hourly time series.

    This test checks if the function correctly converts a yearly time
    series to an hourly time series, ensuring that the length of the
    resulting series matches the expected number of hours for the given
    years.
    """
    # Prepare sample yearly data for 2020 and 2021.
    values = pd.Series([100, 200], index=pd.Index([2020, 2021]))

    # Convert to hourly.
    hourly_series = utils.time_series.convert_from_yearly_to_hourly(
        values, local_time_zone
    )

    # Check the length of the resulting series.
    expected_hours_2020 = 366 * 24
    expected_hours_2021 = 365 * 24
    assert len(hourly_series) == expected_hours_2020 + expected_hours_2021

    # Check the index type and timezone.
    assert isinstance(hourly_series.index, pd.DatetimeIndex)
    assert str(hourly_series.index.tz) == str(local_time_zone)

    # Check that the hours are stamped at their ends, with the value of
    # the year of their starts.
    assert hourly_series.index[0] == pd.Timestamp(
        "2020-01-01 01:00:00", tz=local_time_zone
    )
    assert hourly_series.iloc[0] == 100
    idx_2020_end = pd.Timestamp("2021-01-01 00:00:00", tz=local_time_zone)
    assert hourly_series[idx_2020_end] == 100
    idx_2021 = pd.Timestamp("2021-01-01 01:00:00", tz=local_time_zone)
    assert hourly_series[idx_2021] == 200
    idx_2021_end = pd.Timestamp("2022-01-01 00:00:00", tz=local_time_zone)
    assert hourly_series[idx_2021_end] == 200
    assert hourly_series.index[-1] == idx_2021_end

    # Check all unique values are as expected
    assert set(hourly_series.values) == {100, 200}


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
    time_series = pd.concat(
        [time_series, pd.Series([0], index=[time_series.index[5]])]
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
    cleaned_time_series = cleaned_time_series.tz_localize(None)

    # Check if the function raises an error for an timezone-naive index.
    with pytest.raises(
        ValueError, match="The time series must be timezone-aware"
    ):
        utils.time_series.clean_data(cleaned_time_series, "TestVariable")


def test_convert_from_yearly_to_hourly_with_missing_midnight():
    """
    Test the conversion when a year starts at a missing midnight.

    Peru started daylight saving time at 00:00 on 1990-01-01, so that
    time does not exist, and the year starts an hour later: its first
    hour ends at 02:00 in local time.
    """
    time_zone = pytz.timezone("America/Lima")
    values = pd.Series([100, 200], index=pd.Index([1990, 1991]))

    hourly_series = utils.time_series.convert_from_yearly_to_hourly(
        values, time_zone
    )

    assert hourly_series.index[0] == pd.Timestamp(
        "1990-01-01 06:00:00", tz="UTC"
    )
    assert hourly_series.index[-1] == pd.Timestamp(
        "1992-01-01 05:00:00", tz="UTC"
    )
    assert (
        hourly_series.index.to_series()
        .diff()
        .dropna()
        .eq(pd.Timedelta(hours=1))
        .all()
    )
    assert hourly_series.iloc[0] == 100
    assert hourly_series.iloc[-1] == 200


def test_save_yearly_values(tmp_path):
    """
    Test that saving some years keeps the other saved years.

    The years saved again replace their saved values, and both files
    have the same values.
    """
    file_path = str(tmp_path / "values")

    def save(values: dict[int, float], years: list[int]) -> None:
        utils.time_series.save_yearly_values(
            pd.Series(values), years, "Value", file_path, local_time_zone
        )

    # The years not requested are not saved.
    save({2022: 0.0, 2023: 1.0}, [2023])
    save({2024: 2.0}, [2024])
    save({2023: 3.0}, [2023])

    saved = pd.read_parquet(file_path + ".parquet")["Value"]
    local_years = utils.time_series.get_local_years(
        pd.DatetimeIndex(saved.index), local_time_zone
    )
    assert saved.groupby(local_years).agg(["min", "max", "count"]).to_dict(
        "index"
    ) == {
        2023: {"min": 3.0, "max": 3.0, "count": 8760},
        2024: {"min": 2.0, "max": 2.0, "count": 8784},
    }
    assert saved.index.is_monotonic_increasing
    from_csv = pd.read_csv(file_path + ".csv", index_col=0)["Value"]
    assert from_csv.to_numpy().tolist() == saved.to_numpy().tolist()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "values.csv",
        "values.parquet",
    ]


@pytest.mark.parametrize(
    ("time_zone", "first_end"),
    [
        ("UTC", "2024-01-01 01:00"),
        ("Europe/Paris", "2024-01-01 00:00"),
        ("Asia/Kolkata", "2023-12-31 19:30"),
    ],
)
def test_local_years_of_hours(time_zone, first_end):
    """
    Test that each hour belongs to the local year of its start.

    The hour that ends at midnight on January 1 belongs to the year
    before, in a time zone with a whole or a half hour from UTC.
    """
    tz = pytz.timezone(time_zone)
    start, end = utils.time_series.get_local_year_bounds(2024, tz)
    hours = pd.date_range(start + pd.Timedelta(hours=1), end, freq="h")

    years = utils.time_series.get_local_years(hours, tz)

    assert hours[0] == pd.Timestamp(first_end, tz="UTC")
    assert len(hours) == 8784
    assert set(years) == {2024}
    assert set(
        utils.time_series.get_local_years(
            hours[[0]] - pd.Timedelta(hours=1), tz
        )
    ) == {2023}


def test_keep_latest_download():
    """Test that each time takes the number of the latest download."""
    times = pd.to_datetime(
        [
            "2021-01-01",
            "2025-07-01",
            "2025-07-02",
            "2025-07-01",
            "2025-07-02",
            "2026-01-01",
            "2026-01-01",
        ]
    )
    values = pd.Series([1.0, 2.0, 3.0, 2.5, None, 4.0, 4.5], index=times)
    # The old download ends on 2025-07-02, the new one on 2026-01-01,
    # which has the time 2026-01-01 twice.
    files = pd.Series(["old.csv"] * 3 + ["new.csv"] * 4)

    kept = utils.time_series.keep_latest_download(values, files)

    assert kept.to_dict() == {
        pd.Timestamp("2021-01-01"): 1.0,
        pd.Timestamp("2025-07-01"): 2.5,
        pd.Timestamp("2025-07-02"): 3.0,
        pd.Timestamp("2026-01-01"): 4.0,
    }


def test_keep_latest_download_by_key():
    """Test that the values are kept for each key and time."""
    index = pd.MultiIndex.from_tuples(
        [("A", pd.Timestamp("2020-01-01")), ("B", pd.Timestamp("2020-01-01"))]
        * 2,
        names=["name", "time"],
    )
    values = pd.Series([1.0, 2.0, None, 3.0], index=index)
    files = pd.Series(["a.xlsx", "a.xlsx", "b.xlsx", "b.xlsx"])

    kept = utils.time_series.keep_latest_download(values, files)

    assert kept.tolist() == [1.0, 3.0]
    assert kept.index.equals(index[:2])
