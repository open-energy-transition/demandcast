"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EIA.
"""

import datetime

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import eia


def test_get_available_requests():
    """Test that the requests are the half years of the data."""
    requests = eia.get_available_requests(
        "USA_CAL", datetime.date(2020, 1, 1), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-07-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-07-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 12


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, monkeypatch
):
    """Test that the periods are times in UTC and the values numbers."""
    monkeypatch.setenv("EIA_API_KEY", "test-key")
    fake_downloads.serve(
        "https://api.eia.gov/v2/electricity/rto/region-data/data/?"
        "api_key=test-key&facets[type][]=D&facets[respondent][]=CAL&"
        "start=2025-07-01T00&end=2025-12-28T00&frequency=hourly&"
        "data[0]=value&sort[0][column]=period&sort[0][direction]=asc&"
        "offset=0&length=5000",
        "eia.json",
    )

    time_series = eia.download_and_extract_data_for_request(
        (pd.Timestamp("2025-07-01"), pd.Timestamp("2025-12-28")), "USA_CAL"
    )

    # The API gives the values as text.
    assert_demand(
        time_series,
        "UTC",
        {
            "2025-07-01 00:00": 30000,
            "2025-07-01 01:00": 29500,
            "2025-07-01 02:00": 29000,
        },
        dtype="int64",
    )


@pytest.mark.parametrize("api_key", [None, ""])
def test_get_url_without_api_key(monkeypatch, api_key):
    """Test that the error says how to set a missing or empty API key."""
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    if api_key is not None:
        monkeypatch.setenv("EIA_API_KEY", api_key)
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(eia, "load_dotenv", lambda **_: None)

    with pytest.raises(ValueError, match="EIA_API_KEY"):
        eia.get_url(
            pd.Timestamp("2025-07-01"), pd.Timestamp("2025-12-28"), "USA_CAL"
        )
