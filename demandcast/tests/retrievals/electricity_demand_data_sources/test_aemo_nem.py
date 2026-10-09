"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AEMO for
    the National Electricity Market (NEM).
"""

import datetime

from retrievals.electricity_demand_data_sources import aemo_nem


def test_get_available_requests():
    """Test that the requests are the months of the data."""
    requests = aemo_nem.get_available_requests(
        "AUS_NSW", datetime.date(1998, 12, 7), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (1998, 12)
    assert requests[-1] == (2025, 11)
    assert len(requests) == 324


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the timestamps are in NEM time, UTC+10 all year."""
    url = (
        "https://aemo.com.au/aemo/data/nem/priceanddemand/"
        "PRICE_AND_DEMAND_202510_NSW1.csv"
    )
    # Daylight saving starts in Sydney on 5 October 2025 at 02:00.
    fake_downloads.serve(url, "aemo_nem.csv")

    time_series = aemo_nem.download_and_extract_data_for_request(
        (2025, 10), "AUS_NSW"
    )

    assert fake_downloads.requests[0][2]["headers"] == {
        "User-Agent": "Mozilla/5.0"
    }
    assert_demand(
        time_series,
        "UTC+10:00",
        {
            "2025-10-04 15:55": 6000.5,
            "2025-10-04 16:00": 6010.25,
            "2025-10-05 04:00": 7000.0,
        },
    )
