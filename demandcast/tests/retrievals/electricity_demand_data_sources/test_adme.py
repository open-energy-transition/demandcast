"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from ADME.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import adme


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = adme.get_available_requests()

    assert requests[0] == (
        pd.Timestamp("2019-01-01"),
        pd.Timestamp("2020-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 7


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the demand is read from the files with semicolons."""
    fake_downloads.serve(
        "https://adme.com.uy/panelControl/gpf.php?anod=2024&mesd=1&anoh=2025"
        "&mesh=1&granularidad=1&fuente=1&tipo=1",
        "adme.csv",
    )

    time_series = adme.download_and_extract_data_for_request(
        pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")
    )

    # The times mark the end of each hour. The files include the last
    # month, so January 2025 is also in the next request.
    assert_demand(
        time_series,
        "America/Montevideo",
        {
            "2024-01-01 04:00": 1501.5,
            "2024-01-01 05:00": 1460.75,
            "2025-02-01 03:00": 1720.125,
        },
    )
