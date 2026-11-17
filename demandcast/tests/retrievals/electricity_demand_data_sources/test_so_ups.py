"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from SO UES.
"""

import datetime as dt

import pytest

import utils.fetcher
from retrievals.electricity_demand_data_sources import so_ups


def test_get_available_requests():
    """Test that the requests are the days of the data."""
    requests = so_ups.get_available_requests(
        "RUS_CENTER", dt.date(2024, 2, 28), dt.date(2024, 3, 1)
    )

    assert requests == [
        dt.date(2024, 2, 28),
        dt.date(2024, 2, 29),
        dt.date(2024, 3, 1),
    ]


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the consumption is read, and not the generation."""
    fake_downloads.serve(so_ups.get_url(), "so_ups.html")

    time_series = so_ups.download_and_extract_data_for_request(
        dt.date(2024, 3, 11), "RUS_CENTER"
    )

    assert fake_downloads.requests[0][2]["params"] == {
        "tx_mscdugraph_pi[controller]": "Graph",
        "tx_mscdugraph_pi[action]": "fullview",
        "tx_mscdugraph_pi[viewDate]": "2024-03-11",
        "tx_mscdugraph_pi[viewKpo]": "530000",
    }
    # The hours are their ends in Moscow time, three hours ahead of UTC,
    # and the empty value of the last hour is left out.
    assert len(time_series) == 23
    assert_demand(
        time_series.take([0, -1]),
        "Europe/Moscow",
        {
            "2024-03-10 21:00": 30000.0,
            "2024-03-11 19:00": 30220.0,
        },
    )


def test_daylight_saving_time(fake_downloads):
    """Test that the hour repeated after the skipped one is kept."""
    fake_downloads.serve(so_ups.get_url(), "so_ups_daylight_saving.html")

    time_series = so_ups.download_and_extract_data_for_request(
        dt.date(2010, 3, 28), "RUS_CENTER"
    )

    assert len(time_series) == 23
    assert (time_series.index.to_series().diff().dropna() == "1h").all()
    assert time_series.iloc[2] == 20030.0


def test_other_day(fake_downloads):
    """Test that the chart of another day is not taken for the day."""
    fake_downloads.serve(so_ups.get_url(), "so_ups_other_day.html")

    with pytest.raises(utils.fetcher.DataNotFoundError):
        so_ups.download_and_extract_data_for_request(
            dt.date(2000, 1, 1), "RUS_CENTER"
        )
