"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from TSOC.
"""

import numpy as np
import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import tsoc

URL_2019 = (
    "https://tsoc.org.cy/files/electrical-system/daily-system-generation/"
    "%CE%97%CE%BC%CE%B5%CF%81%CE%AE%CF%83%CE%B9%CE%B1%20"
    "%CE%A0%CE%B1%CF%81%CE%B1%CE%B3%CF%89%CE%B3%CE%AE%20"
    "%CE%97%CE%BB%CE%B5%CE%BA%CF%84%CF%81%CE%B9%CE%BA%CE%BF%CF%8D%20"
    "%CE%A3%CF%85%CF%83%CF%84%CE%AE%CE%BC%CE%B1%CF%84%CE%BF%CF%82%20"
    "-%202019.xlsx"
)


def _write_yearly_file(file_path, first_day, minutes_early):
    """
    Write a yearly file of TSOC for ten days of January.

    The estimated distributed generation has a solar peak in the
    middle of the day, and the times of the file are early by some
    minutes.
    """
    # The start of each interval in Cyprus local time, UTC+2 in winter.
    starts = pd.date_range(first_day, periods=10 * 96, freq="15min")
    middles = (starts + pd.Timedelta(minutes=7.5)).to_series()
    hours = middles.dt.hour + middles.dt.minute / 60
    noon = tsoc._solar_noon(pd.DatetimeIndex(starts.normalize())) + 2
    solar = np.clip(1 - ((hours - noon - tsoc.SOLAR_DELAY) / 4) ** 2, 0, None)
    times = starts - pd.Timedelta(minutes=minutes_early)

    rows: list[list[object]] = [
        [None] * 11,
        [None] * 11,
        [None, None, None, None, "Wind", None, "Total", None, "Distributed"],
        [None, None, None, None, "MW", None, "MW", None, "MW"],
    ]
    rows[2] += [None, "Conventional"]
    rows[3] += [None, "MW"]
    for number, time in enumerate(times):
        rows.append(
            [
                time,
                "-",
                time + pd.Timedelta(minutes=15),
                None,
                50.0,
                None,
                500.5 + number,
                None,
                10 + 300 * solar.iloc[number],
                None,
                400.0,
            ]
        )
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years that have ended."""
    assert tsoc.get_available_requests() == list(range(2018, 2025))


@pytest.mark.usefixtures("frozen_now")
def test_get_url():
    """Test that the URL of a year is the address of its Excel file."""
    assert tsoc.get_url(2019) == URL_2019


@pytest.mark.usefixtures("frozen_now")
def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the times of 2019 move 30 minutes to the end in UTC."""
    file_path = tmp_path / "2019.xlsx"
    _write_yearly_file(file_path, "2019-01-10", minutes_early=30)
    fake_downloads.serve(URL_2019, file_path)

    time_series = tsoc.download_and_extract_data_for_request(2019)

    # The files of 2019 are 30 minutes early, and the intervals that
    # start at 00:00 in Cyprus end at 22:15 in UTC.
    times = pd.date_range("2019-01-09 22:15", periods=10 * 96, freq="15min")
    assert_demand(
        time_series,
        "Asia/Nicosia",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [500.5 + number for number in range(10 * 96)],
                strict=True,
            )
        ),
    )


@pytest.mark.usefixtures("frozen_now")
def test_download_and_extract_data_for_request_one_hour_late(
    fake_downloads, assert_demand, tmp_path, caplog
):
    """Test that the solar generation corrects a shift of one hour."""
    url_2024 = URL_2019.replace("2019.xlsx", "2024.xlsx")
    file_path = tmp_path / "2024.xlsx"
    _write_yearly_file(file_path, "2024-01-10", minutes_early=-60)
    fake_downloads.serve(url_2024, file_path)

    time_series = tsoc.download_and_extract_data_for_request(2024)

    times = pd.date_range("2024-01-09 22:15", periods=10 * 96, freq="15min")
    assert_demand(
        time_series,
        "Asia/Nicosia",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [500.5 + number for number in range(10 * 96)],
                strict=True,
            )
        ),
    )
    assert "seem +1 hours from the solar generation" in caplog.text
