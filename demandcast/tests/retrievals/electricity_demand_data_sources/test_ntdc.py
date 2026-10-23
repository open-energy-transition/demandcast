"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NTDC, from
    manually downloaded files.
"""

import numpy as np
import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import ntdc


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the hours and the loads with commas are read."""
    # The files have the date, the hour from 1 to 24 and the load.
    (manual_downloads_folder / "NTDC_2024.csv").write_text(
        'DATE,HOUR,SYSLOAD\n01/01/2024,1,"15,000"\n01/01/2024,24,"17,500.5"\n',
        encoding="utf-8",
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    # The times mark the end of each hour.
    assert_demand(
        time_series,
        "Asia/Karachi",
        {"2023-12-31 20:00": 15000.0, "2024-01-01 19:00": 17500.5},
    )


def test_download_and_extract_data_with_text(manual_downloads_folder, caplog):
    """Test that a value that is not a number is left out."""
    (manual_downloads_folder / "NTDC_2024.csv").write_text(
        'DATE,HOUR,SYSLOAD\n01/01/2024,1,"15,000"\n01/01/2024,2,meter\n',
        encoding="utf-8",
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    assert "such as 'meter'" in caplog.text
    assert time_series.tolist() == [15000.0]


def test_download_and_extract_data_with_other_days(
    manual_downloads_folder, assert_demand
):
    """Test that the rows labelled with another day are moved."""
    # The hour 24 has the date of the day before and the hour 1 of the
    # next day the date of the day, as in the file of NTDC, after a gap
    # of a day, which stays.
    rows = [("05/01/2015", 22), ("05/01/2015", 23), ("05/01/2015", 24)]
    rows += [("07/01/2015", hour) for hour in range(1, 24)]
    rows += [("06/01/2015", 24), ("07/01/2015", 1)]
    rows += [("08/01/2015", hour) for hour in range(2, 5)]
    lines = [
        f'{date},{hour},"8,{index:03d}"'
        for index, (date, hour) in enumerate(rows)
    ]
    (manual_downloads_folder / "NTDC_2015.csv").write_text(
        "DATE,HOUR,SYSLOAD\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    # The times are the ends of the hours in Pakistan (UTC+5).
    times = pd.DatetimeIndex(
        pd.date_range("2015-01-05 17:00", periods=3, freq="h").append(
            pd.date_range("2015-01-06 20:00", periods=28, freq="h")
        )
    )
    assert_demand(
        time_series,
        "Asia/Karachi",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [8000.0 + index for index in range(len(rows))],
                strict=True,
            )
        ),
    )


def test_download_and_extract_data_of_two_downloads(
    manual_downloads_folder, assert_demand
):
    """Test that each hour takes the number of the latest download."""
    (manual_downloads_folder / "NTDC_2024_old.csv").write_text(
        "DATE,HOUR,SYSLOAD\n01/01/2024,1,15000\n01/01/2024,2,14000\n",
        encoding="utf-8",
    )
    # The later download ends later and revises the first hour.
    (manual_downloads_folder / "NTDC_2024_new.csv").write_text(
        "DATE,HOUR,SYSLOAD\n01/01/2024,1,15500\n01/01/2024,3,13000\n",
        encoding="utf-8",
    )

    assert_demand(
        ntdc.download_and_extract_data_for_request(None, "PAK"),
        "Asia/Karachi",
        {
            "2023-12-31 20:00": 15500.0,
            "2023-12-31 21:00": 14000.0,
            "2023-12-31 22:00": 13000.0,
        },
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'NTD'"):
        ntdc.download_and_extract_data_for_request(None, "PAK")


def test_correct_slipped_days():
    """
    Test that a day of 2019 an hour early moves back to its hours.

    The value that it brings onto the first hour of the next day is
    left out, and the days of the other years stay at their hours.
    """
    hours = np.arange(24)
    profile = 1000 + 400 * np.exp(-((hours - 19) ** 2) / 4) + 100 * hours / 24
    days = [
        *pd.date_range("2018-01-01", "2018-01-31"),
        pd.Timestamp("2019-01-11"),
        pd.Timestamp("2019-01-12"),
    ]
    starts, values = [], []
    for day in days:
        day_values = np.roll(profile, -1) if day == days[-2] else profile
        starts += list(day + pd.to_timedelta(hours, unit="h"))
        values += list(day_values)
    load = pd.Series(values, index=pd.DatetimeIndex(starts))

    corrected = ntdc._correct_slipped_days(load)

    early = pd.Timestamp("2019-01-11")
    for hour in range(1, 24):
        assert corrected[early + pd.Timedelta(hours=hour)] == profile[hour]
    assert early not in corrected.index
    next_day = pd.Timestamp("2019-01-12")
    assert corrected[next_day] == profile[0]
    pd.testing.assert_series_equal(
        corrected[:"2018-12-31"], load[:"2018-12-31"]
    )
