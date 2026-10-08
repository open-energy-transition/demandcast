"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EMI.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import emi


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = emi.get_available_requests()

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
    """Test that the half-hourly energy in GWh becomes demand in MW."""
    fake_downloads.serve(
        "https://www.emi.ea.govt.nz/Wholesale/Download/DataReport/CSV/W_GD_C"
        "?DateFrom=20240101&DateTo=20250101&RegionType=NZ",
        "emi.csv",
    )

    time_series = emi.download_and_extract_data_for_request(
        pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")
    )

    # When daylight saving ends on 7 April, 02:00 and 02:30 happen
    # twice, and when it starts on 29 September, 02:00 does not exist:
    # the periods that end at these times get no time, and the cleaning
    # of the data drops them.
    assert time_series[time_series.index.isna()].tolist() == [
        3600.0,
        3500.0,
        3700.0,
    ]
    # The files label the repeated half hours as ending at 03:10 and
    # 03:20, and the period that ends at 03:00 in daylight saving time
    # gets 03:00 in standard time, one hour late.
    assert_demand(
        time_series[time_series.index.notna()],
        "Pacific/Auckland",
        {
            "2023-12-31 11:30": 3000.0,
            "2024-04-06 15:00": 3400.0,
            "2024-04-06 15:10": 3300.0,
            "2024-04-06 15:20": 3200.0,
            "2024-04-06 15:30": 3100.0,
            "2024-09-28 14:30": 3650.0,
        },
    )
