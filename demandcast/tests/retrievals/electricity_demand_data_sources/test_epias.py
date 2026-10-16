"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EPIAS.
"""

import datetime

import pandas as pd
import pytest
import utils.config
from retrievals.electricity_demand_data_sources import epias


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = epias.get_available_requests(
        "TUR", datetime.date(2015, 12, 31), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (
        pd.Timestamp("2015-12-31"),
        pd.Timestamp("2016-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-28"),
    )


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, monkeypatch
):
    """Test that the hours of the API, with a ticket, end in UTC."""
    monkeypatch.setenv("EPIAS_USERNAME", "user@example.org")
    monkeypatch.setenv("EPIAS_PASSWORD", "test-password")
    # Ignore a local .env file with a real account.
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)
    fake_downloads.serve(epias.TICKET_URL, "epias_ticket.txt", method="POST")
    fake_downloads.serve(epias.get_url(), "epias.json", method="POST")

    time_series = epias.download_and_extract_data_for_request(
        (pd.Timestamp("2016-03-27"), pd.Timestamp("2016-03-28")), "TUR"
    )

    # The account gets a ticket, which the request of the data sends,
    # with the dates in the time of Turkey.
    ticket_request, data_request = fake_downloads.requests
    assert ticket_request[2]["data"] == {
        "username": "user@example.org",
        "password": "test-password",
    }
    assert data_request[2]["headers"] == {"TGT": "TGT-test-ticket"}
    assert data_request[2]["json"] == {
        "startDate": "2016-03-27T00:00:00+02:00",
        "endDate": "2016-03-28T00:00:00+03:00",
    }
    # When daylight saving time starts, the hour that starts at 02:00
    # has no consumption, which the cleaning removes.
    assert_demand(
        time_series,
        "Europe/Istanbul",
        {
            "2016-03-27 00:00": 25949.63,
            "2016-03-27 01:00": 0.0,
            "2016-03-27 02:00": 24776.94,
            "2016-03-27 03:00": 24098.97,
        },
    )


def test_download_and_extract_data_without_data(fake_downloads, monkeypatch):
    """Test that a period without data gives an empty time series."""
    monkeypatch.setenv("EPIAS_USERNAME", "user@example.org")
    monkeypatch.setenv("EPIAS_PASSWORD", "test-password")
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)
    fake_downloads.serve(epias.TICKET_URL, "epias_ticket.txt", method="POST")
    fake_downloads.serve(epias.get_url(), "epias_empty.json", method="POST")

    # The data starts on 2015-12-31.
    time_series = epias.download_and_extract_data_for_request(
        (pd.Timestamp("2015-01-01"), pd.Timestamp("2015-01-02")), "TUR"
    )

    assert time_series.empty


def test_download_and_extract_data_without_account(monkeypatch):
    """Test that the error says how to set a missing account."""
    monkeypatch.delenv("EPIAS_USERNAME", raising=False)
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)

    with pytest.raises(ValueError, match="EPIAS_USERNAME"):
        epias.download_and_extract_data_for_request(
            (pd.Timestamp("2016-03-27"), pd.Timestamp("2016-03-28")), "TUR"
        )
