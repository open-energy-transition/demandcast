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
