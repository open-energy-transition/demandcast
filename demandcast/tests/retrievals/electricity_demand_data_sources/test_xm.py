"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from XM.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import xm


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the months of the data."""
    requests = xm.get_available_requests()

    assert requests[0] == (
        pd.Timestamp("2000-01-01"),
        pd.Timestamp("2000-02-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-12-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 312


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the hourly energy in kWh becomes the demand in MW."""
    fake_downloads.serve(
        "https://50uclmn31c.execute-api.us-east-1.amazonaws.com/prod/xmproxy?"
        "metricId=DemaReal&entity=Sistema&start=2025-12-01&end=2026-01-01",
        "xm.json",
        method="POST",
    )

    time_series = xm.download_and_extract_data_for_request(
        pd.Timestamp("2025-12-01"), pd.Timestamp("2026-01-01")
    )

    # Hour01 is the hour that ends at 01:00 in Bogota, 06:00 in UTC,
    # and the values of the fixture grow by 1 MW every hour.
    times = pd.date_range("2025-12-01 06:00", periods=48, freq="h")
    assert_demand(
        time_series,
        "America/Bogota",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [1000.0 + hour for hour in range(48)],
                strict=True,
            )
        ),
    )
