"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EMA.
"""

import datetime

import pandas as pd
from retrievals.electricity_demand_data_sources import ema


def _write_weekly_file(file_path, first_day):
    """
    Write a weekly file in the format of EMA.

    The file has a title, the dates and weekdays, and three columns
    per day: the actual system demand, and the actual and forecast
    demand of the market. The rows are the half hours, by end time.
    """
    days = pd.date_range(first_day, periods=7)
    columns = [" System Demand (Actual)", " NEM Demand (Actual)"]
    columns.append(" NEM Demand (Forecast)")
    end_times = pd.date_range("00:30", periods=48, freq="30min")
    rows = [
        ["Half-hourly system demand"] + [None] * 21,
        ["Date"] + [value for day in days for value in (day, None, None)],
        ["Period Ending Time"]
        + [
            value for day in days for value in (day.strftime("%a"), None, None)
        ],
        [None] * 22,
        [None] + columns * 7,
    ]
    for half_hour, end_time in enumerate(end_times):
        rows.append(
            [end_time.strftime("%H:%M")]
            + [
                value
                for day in range(7)
                for value in (6000.5 + 100 * day + half_hour, 1.0, 2.0)
            ]
        )
    rows.append(["4. All units in MW."] + [None] * 21)
    pd.DataFrame(rows).to_excel(file_path, header=False, index=False)


def test_get_available_requests():
    """Test that the requests are the published weeks of the data."""
    requests = ema.get_available_requests(
        "SGP", datetime.date(2014, 1, 6), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (2014, 1, 6)
    assert requests[-1] == (2025, 12, 15)
    assert len(requests) == 610
    # A week that EMA did not publish.
    assert (2014, 12, 1) not in requests


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the system demand of the week is read as numbers."""
    file_path = tmp_path / "20251215.xlsx"
    _write_weekly_file(file_path, "2025-12-15")
    fake_downloads.serve(
        "https://www.ema.gov.sg/content/dam/corporate/resources/statistics/"
        "half-hourly-data/2025/20251215.xls",
        file_path,
    )

    time_series = ema.download_and_extract_data_for_request(
        (2025, 12, 15), "SGP"
    )

    # The times are the ends of the half hours, in Singapore (UTC+8).
    times = pd.date_range("2025-12-14 16:30", periods=7 * 48, freq="30min")
    assert_demand(
        time_series,
        "Asia/Singapore",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [
                    6000.5 + 100 * day + half_hour
                    for day in range(7)
                    for half_hour in range(48)
                ],
                strict=True,
            )
        ),
    )
