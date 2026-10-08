"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AEMO for
    the Wholesale Electricity Market (WEM).
"""

import pytest
from retrievals.electricity_demand_data_sources import aemo_wem


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are years before the reform, then days."""
    requests = aemo_wem.get_available_requests()

    assert requests[:2] == [(True, 2006, None, None), (True, 2007, None, None)]
    assert requests[17:19] == [
        (True, 2023, None, None),
        (False, 2023, 10, 1),
    ]
    assert requests[-1] == (False, 2025, 12, 28)
    assert len(requests) == 838


def test_download_and_extract_data_for_request_before_reform(
    fake_downloads, assert_demand
):
    """Test that the timestamps are in AWST, UTC+8 all year."""
    # Perth trialled daylight saving from 3 December 2006 at 02:00.
    fake_downloads.serve(
        "https://data.wa.aemo.com.au/datafiles/operational-demand/"
        "operational-demand-2006.csv",
        "aemo_wem_2006.csv",
    )

    time_series = aemo_wem.download_and_extract_data_for_request(
        True, 2006, None, None
    )

    # The timestamps mark the end of the 30-minute trading intervals.
    assert_demand(
        time_series,
        "UTC",
        {
            "2006-12-02 18:30": 1500.5,
            "2006-12-02 19:00": 1490.0,
            "2006-12-10 06:30": 2500.25,
        },
    )


def test_download_and_extract_data_for_request_after_reform(
    fake_downloads, assert_demand
):
    """Test the daily files of the five-minute intervals."""
    fake_downloads.serve(
        "https://data.wa.aemo.com.au/public/market-data/wemde/"
        "operationalDemandWithdrawal/dailyFiles/"
        "OperationalDemandAndWithdrawal_2025-01-15.json",
        "aemo_wem_2025-01-15.json",
    )

    time_series = aemo_wem.download_and_extract_data_for_request(
        False, 2025, 1, 15
    )

    assert_demand(
        time_series,
        "UTC",
        {"2025-01-15 00:05": 2800.5, "2025-01-15 00:10": 2810.0},
    )
