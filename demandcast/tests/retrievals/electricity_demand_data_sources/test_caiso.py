"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CAISO.
"""

import datetime

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import caiso


def test_get_available_requests(fake_downloads):
    """Test that the months are the published ones, until today."""
    fake_downloads.serve(
        "https://www.caiso.com/library/historical-ems-hourly-load",
        "caiso_library.html",
    )

    # The years until 2023, then the months of the page until the end
    # of 2025: the months of 2026 are after today.
    requests = caiso.get_available_requests(
        "USA_CAL", datetime.date(2019, 1, 1), datetime.date(2025, 12, 28)
    )
    assert requests == [
        (2019, None),
        (2020, None),
        (2021, None),
        (2022, None),
        (2023, None),
        (2024, 1),
        (2024, 4),
        (2025, 12),
    ]


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the hours of the day mark the end of each hour."""
    file_path = tmp_path / "historical-ems-hourly-load-for-december-2025.xlsx"
    pd.DataFrame(
        {
            "Date": ["2025-12-01", "2025-12-01", "2025-12-01", "Total"],
            "HR": [1, 2, 3, None],
            "CAISO": [25000.5, 24000.0, 23500.25, 72500.75],
            "PGE": [10000.0, 9500.0, 9300.0, 28800.0],
        }
    ).to_excel(file_path, index=False)
    fake_downloads.serve(
        "https://www.caiso.com/documents/"
        "historical-ems-hourly-load-for-December-2025.xlsx",
        file_path,
    )

    time_series = caiso.download_and_extract_data_for_request(
        (2025, 12), "USA_CAL"
    )

    # The row of the totals is left out, and the hour ending at 01:00 in
    # Los Angeles ends at 09:00 in UTC.
    assert_demand(
        time_series,
        "America/Los_Angeles",
        {
            "2025-12-01 09:00": 25000.5,
            "2025-12-01 10:00": 24000.0,
            "2025-12-01 11:00": 23500.25,
        },
    )


def test_download_and_extract_data_at_the_end_of_summer_time(
    fake_downloads, assert_demand, tmp_path
):
    """Test that both hours ending at 01:00 are kept, in order."""
    file_path = tmp_path / "historical-ems-hourly-load-for-november-2024.xlsx"
    pd.DataFrame(
        {
            "Date": ["2024-11-03"] * 4,
            "HR": [1.0, 1.0, 2.0, 3.0],
            "CAISO": [21000.5, 20500.0, 20000.25, 19500.0],
        }
    ).to_excel(file_path, index=False)
    fake_downloads.serve(
        "https://www.caiso.com/documents/"
        "historical-ems-hourly-load-for-November-2024.xlsx",
        file_path,
    )

    time_series = caiso.download_and_extract_data_for_request(
        (2024, 11), "USA_CAL"
    )

    # The first hour ending at 01:00 is in daylight saving time (UTC-7)
    # and the second in standard time (UTC-8).
    assert_demand(
        time_series,
        "America/Los_Angeles",
        {
            "2024-11-03 08:00": 21000.5,
            "2024-11-03 09:00": 20500.0,
            "2024-11-03 10:00": 20000.25,
            "2024-11-03 11:00": 19500.0,
        },
    )


def test_download_and_extract_data_with_midnight_at_the_day_start(
    fake_downloads, assert_demand, tmp_path
):
    """Test that an hour 24 that starts a day ends the day before."""
    # In January 2019, the hour ending at midnight comes first in the
    # day after, which then has 25 hours in the first day of February.
    file_path = tmp_path / "historicalemshourlyload-2019.xlsx"
    pd.DataFrame(
        {
            "Date": ["2019-01-31", "2019-02-01", "2019-02-01", "2019-02-01"],
            "HE": [23, 24, 1, 24],
            "CAISO Total": [23400.5, 21900.0, 20700.25, 22100.0],
        }
    ).to_excel(file_path, index=False)
    fake_downloads.serve(
        "https://www.caiso.com/documents/historicalemshourlyload-2019.xlsx",
        file_path,
    )

    time_series = caiso.download_and_extract_data_for_request(
        (2019, None), "USA_CAL"
    )

    assert_demand(
        time_series,
        "America/Los_Angeles",
        {
            "2019-02-01 07:00": 23400.5,
            "2019-02-01 08:00": 21900.0,
            "2019-02-01 09:00": 20700.25,
            "2019-02-02 08:00": 22100.0,
        },
    )


def test_url_of_a_period_without_a_file():
    """Test that a period without a file of its length is an error."""
    with pytest.raises(ValueError, match="2024 is in monthly files"):
        caiso.get_url(2024, None)
    with pytest.raises(ValueError, match="2023 is in a yearly file"):
        caiso.get_url(2023, 5)
