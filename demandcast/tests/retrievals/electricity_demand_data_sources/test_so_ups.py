"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from SO UES.
"""

import datetime as dt

import pytest

from retrievals.electricity_demand_data_sources import so_ups


@pytest.fixture(autouse=True)
def no_interval(monkeypatch):
    """Send the requests of the tests without waiting between them."""
    monkeypatch.setattr(so_ups, "REQUEST_INTERVAL", 0.0)


def test_wait_for_the_interval(monkeypatch):
    """Test that a request waits for the rest of the interval."""
    sleeps: list[float] = []
    monkeypatch.setattr(so_ups, "REQUEST_INTERVAL", 2.0)
    monkeypatch.setattr(so_ups, "_last_request", {"time": 9.5})
    monkeypatch.setattr(so_ups.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(so_ups.time, "sleep", sleeps.append)

    so_ups._wait_for_the_interval()
    so_ups._last_request["time"] = 5.0
    so_ups._wait_for_the_interval()

    assert sleeps == [1.5]
    assert so_ups._last_request == {"time": 10.0}


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


@pytest.mark.parametrize(
    "file_name", ["so_ups_other_day.html", "so_ups_without_chart.html"]
)
def test_day_without_chart(fake_downloads, file_name):
    """Test that a day without its chart has no data."""
    fake_downloads.serve(so_ups.get_url(), file_name)

    time_series = so_ups.download_and_extract_data_for_request(
        dt.date(2002, 2, 1), "RUS_CENTER"
    )

    assert time_series.empty


def test_attempts_a_minute_apart(monkeypatch):
    """Test that the attempts of a request are a minute apart."""
    options = {}

    def fetch_text(_url, **kwargs):
        """
        Record the options of the request.

        Returns
        -------
        str
            A page without chart.
        """
        options.update(kwargs)
        return "<html></html>"

    monkeypatch.setattr(so_ups.utils.fetcher, "fetch_text", fetch_text)

    so_ups.download_and_extract_data_for_request(
        dt.date(2024, 3, 11), "RUS_CENTER"
    )

    assert options["retry_delay"] == 60
