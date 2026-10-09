"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CEN.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import cen


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = cen.get_available_requests()

    assert requests[0] == (
        pd.Timestamp("1999-01-01"),
        pd.Timestamp("2000-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 27


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the hours are sorted and mark the end of each hour."""
    fake_downloads.serve(
        "https://sipub.coordinador.cl/api/v1/recursos/demandasistemareal?"
        "fecha__gte=2025-01-01&fecha__lte=2025-12-28",
        "cen.json",
    )

    time_series = cen.download_and_extract_data_for_request(
        pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-28")
    )

    assert fake_downloads.requests[0][2]["headers"]["Origin"] == (
        "https://www.coordinador.cl"
    )
    assert_demand(
        time_series,
        "America/Santiago",
        {
            "2025-01-01 03:00": 8100.0,
            "2025-01-01 04:00": 8000.5,
            "2025-01-01 05:00": 7900.25,
        },
    )


def test_download_and_extract_data_for_request_when_daylight_saving_ends(
    fake_downloads, assert_demand
):
    """Test that the 25th hour of the day follows the 24th."""
    # On 2025-04-05, daylight saving time ended at midnight, and the
    # 24th and 25th hours both started at 23:00.
    fake_downloads.serve(
        "https://sipub.coordinador.cl/api/v1/recursos/demandasistemareal?"
        "fecha__gte=2025-01-01&fecha__lte=2025-12-28",
        "cen_end_of_daylight_saving.json",
    )

    time_series = cen.download_and_extract_data_for_request(
        pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-28")
    )

    assert_demand(
        time_series,
        "America/Santiago",
        {
            "2025-04-06 02:00": 7000.0,
            "2025-04-06 03:00": 6900.0,
            "2025-04-06 04:00": 6800.0,
            "2025-04-06 05:00": 6700.0,
        },
    )
