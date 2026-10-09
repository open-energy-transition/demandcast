"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CAISO.
"""

import datetime

import pandas as pd
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
