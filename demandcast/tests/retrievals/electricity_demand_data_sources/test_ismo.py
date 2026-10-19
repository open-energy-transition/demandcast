"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from ISMO.
"""

import datetime

import pandas as pd
from retrievals.electricity_demand_data_sources import ismo


def test_get_available_requests():
    """Test that the requests are the fiscal years with files."""
    requests = ismo.get_available_requests(
        "PAK", datetime.date(2015, 1, 1), datetime.date(2026, 12, 31)
    )

    assert requests == [2025]


def test_get_available_requests_outside_files():
    """Test that a fiscal year without a file has no request."""
    requests = ismo.get_available_requests(
        "PAK", datetime.date(2025, 7, 1), datetime.date(2026, 6, 30)
    )

    assert requests == []


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the hourly demand moves to the ends of the hours."""
    file_path = tmp_path / "System Demand Profile_Hourly.xlsx"
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-07-01", "2024-07-01"]),
            "Hour": [0, 23],
            "Actual Metered Hourly Profile of System Demand \n"
            "(Excluding KE)\n(MW)": [21404.75, 22952.25],
        }
    ).to_excel(file_path, sheet_name="System Demand Profile", index=False)
    fake_downloads.serve(ismo.FILE_URLS[2025], file_path)

    time_series = ismo.download_and_extract_data_for_request(2025, "PAK")

    # The hours from 0 to 23 are their starts in Pakistan (UTC+5).
    assert_demand(
        time_series,
        "Asia/Karachi",
        {"2024-06-30 20:00": 21404.75, "2024-07-01 19:00": 22952.25},
    )
