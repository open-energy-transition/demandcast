"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from ENTSO-E.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import entsoe


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are periods of one year at most."""
    requests = entsoe.get_available_requests("BEL")

    assert requests[0] == (
        pd.Timestamp("2014-11-24"),
        pd.Timestamp("2015-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 12


# entsoe-py parses the XML of the responses with the HTML parser.
@pytest.mark.filterwarnings("ignore::bs4.XMLParsedAsHTMLWarning")
def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, monkeypatch
):
    """Test that the actual load is read and marks the ends of steps."""
    monkeypatch.setenv("ENTSOE_API_KEY", "test-key")
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(entsoe, "load_dotenv", lambda **_: None)
    fake_downloads.serve("https://web-api.tp.entsoe.eu/api", "entsoe.xml")

    time_series = entsoe.download_and_extract_data_for_request(
        pd.Timestamp("2024-03-31 00:00"),
        pd.Timestamp("2024-03-31 02:00"),
        "BEL",
    )

    # The client of ENTSO-E asks for the actual total load of Belgium.
    assert {
        "documentType": "A65",
        "processType": "A16",
        "outBiddingZone_Domain": "10YBE----------2",
        "periodStart": "202403310000",
        "periodEnd": "202403310200",
        "securityToken": "test-key",
    }.items() <= fake_downloads.requests[0][2]["params"].items()
    # The response is in UTC, and the client converts it to the time of
    # Brussels, where daylight saving time starts at 01:00 UTC. The
    # times are the starts of the 15 minutes, which move 15 minutes
    # later to mark their ends.
    assert_demand(
        time_series,
        "Europe/Brussels",
        {
            "2024-03-31 00:15": 8000.25,
            "2024-03-31 00:30": 7900.5,
            "2024-03-31 00:45": 7800.75,
            "2024-03-31 01:00": 7700.0,
            "2024-03-31 01:15": 7650.25,
            "2024-03-31 01:30": 7600.5,
            "2024-03-31 01:45": 7550.75,
            "2024-03-31 02:00": 7500.0,
        },
    )


def test_download_and_extract_data_for_request_without_api_key(monkeypatch):
    """Test that the error says how to set the API key."""
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(entsoe, "load_dotenv", lambda **_: None)

    with pytest.raises(ValueError, match="ENTSOE_API_KEY"):
        entsoe.download_and_extract_data_for_request(
            pd.Timestamp("2024-03-31"), pd.Timestamp("2024-04-01"), "BEL"
        )
