"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EMI.
"""

import datetime

import pandas as pd
from retrievals.electricity_demand_data_sources import emi


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = emi.get_available_requests(
        "NZL", datetime.date(2005, 1, 1), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (
        pd.Timestamp("2005-01-01"),
        pd.Timestamp("2006-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 21


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test the demand in MW and the days of daylight saving time."""
    fake_downloads.serve(
        "https://www.emi.ea.govt.nz/Wholesale/Download/DataReport/CSV/W_GD_C"
        "?DateFrom=20240101&DateTo=20250101&RegionType=NZ",
        "emi.csv",
    )

    time_series = emi.download_and_extract_data_for_request(
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")), "NZL"
    )

    # When daylight saving ends on 7 April, the half hours that start at
    # 02:00 and 02:30 happen twice, the second time labelled as starting
    # at 02:40 and 02:50. When it starts on 29 September, the half hour
    # that starts at 01:30 ends at 03:00. All the half hours follow each
    # other in UTC.
    assert_demand(
        time_series,
        "Pacific/Auckland",
        {
            "2023-12-31 11:30": 3000.0,
            "2024-04-06 13:00": 3600.0,
            "2024-04-06 13:30": 3500.0,
            "2024-04-06 14:00": 3400.0,
            "2024-04-06 14:30": 3300.0,
            "2024-04-06 15:00": 3200.0,
            "2024-04-06 15:30": 3100.0,
            "2024-09-28 14:00": 3700.0,
            "2024-09-28 14:30": 3650.0,
        },
    )
