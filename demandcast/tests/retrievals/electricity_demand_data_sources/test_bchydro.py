"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from BC Hydro.
"""

import datetime

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import bchydro

URL_FOLDER = (
    "https://www.bchydro.com/content/dam/BCHydro/customer-portal/"
    "documents/corporate/suppliers/transmission-system/"
    "balancing_authority_load_data/Historical%20Transmission%20Data/"
)


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = bchydro.get_available_requests(
        "CAN_BC", datetime.date(2001, 4, 1), datetime.date(2025, 12, 28)
    )

    assert requests == list(range(2001, 2026))


@pytest.mark.parametrize(
    ("year", "file_name"),
    [
        (2001, "BalancingAuthorityLoadApr-Dec2001.xls"),
        (2008, "2008controlareaload.xls"),
        (2010, "jandec2010controlareaload.xls"),
        (2020, "BalancingAuthorityLoad2020.xls"),
        (2025, "BalancingAuthorityLoad%202025.xls"),
        (2027, "BalancingAuthorityLoad%202027.xls"),
    ],
)
def test_get_url(year, file_name):
    """Test that the years after 2025 keep the latest file name."""
    assert bchydro.get_url(year) == URL_FOLDER + file_name


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, tmp_path
):
    """Test that a year after 2025 is read in the latest format."""
    # Three rows of titles, then the hours ending (HE) of each day.
    file_path = tmp_path / "BalancingAuthorityLoad 2026.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame(
            [
                ["Hourly Control Area Load Report", None, None],
                ["Date Range:", "-2026", None],
                ["Area Group Name:", "BCHA", None],
            ]
        ).to_excel(writer, header=False, index=False)
        pd.DataFrame(
            {
                "Date ": ["01/01/2026"] * 3,
                "HE": [1, 2, 3],
                "Control Area Load": [8000, 7900, 7800],
            }
        ).to_excel(writer, startrow=3, index=False)
    fake_downloads.serve(
        URL_FOLDER + "BalancingAuthorityLoad%202026.xls", file_path
    )

    time_series = bchydro.download_and_extract_data_for_request(2026, "CAN_BC")

    # The hour ending at 01:00 in Vancouver ends at 09:00 in UTC.
    assert_demand(
        time_series,
        "America/Vancouver",
        {
            "2026-01-01 09:00": 8000,
            "2026-01-01 10:00": 7900,
            "2026-01-01 11:00": 7800,
        },
        dtype="int64",
    )
