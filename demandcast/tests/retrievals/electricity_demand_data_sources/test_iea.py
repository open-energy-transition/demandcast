"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from the IEA.
"""

import datetime as dt
import json

import pandas as pd
import pytest

import utils.data_sources
from retrievals.electricity_demand_data_sources import iea


def test_get_available_requests():
    """Test that the requests are the quarters, up to the end date."""
    requests = iea.get_available_requests(
        "UKR_IPS", dt.date(2021, 8, 15), dt.date(2022, 2, 28)
    )

    assert requests == [
        (pd.Timestamp("2021-08-15"), pd.Timestamp("2021-10-01")),
        (pd.Timestamp("2021-10-01"), pd.Timestamp("2022-01-01")),
        (pd.Timestamp("2022-01-01"), pd.Timestamp("2022-03-01")),
    ]


def test_time_zones_of_the_entities():
    """
    Test that each entity has a time zone, and a region if needed.

    A subdivision of a country whose regions the API gives is one of
    them.
    """
    countries_with_regions = {code.split("_")[0] for code in iea.REGIONS}
    for entity in utils.data_sources.read_entities("iea"):
        assert entity.country_code in iea.TIME_ZONES
        if entity.country_code in countries_with_regions:
            assert entity.code in iea.REGIONS


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """
    Test that the local starts of the hours become their ends in UTC.

    The hour given twice when daylight saving time ends, the hour
    without value and the hours outside the period are left out, and
    the values in GW become MW.
    """
    fake_downloads.serve(iea.get_url(), "iea_deu.json")

    time_series = iea.download_and_extract_data_for_request(
        (pd.Timestamp("2024-10-27"), pd.Timestamp("2024-10-28")), "DEU"
    )

    assert fake_downloads.requests[0][2]["params"] == {
        "from": "2024-10-27",
        "to": "2024-10-28",
        "precision": "hour",
        "ISO3": "DEU",
    }
    assert_demand(
        time_series,
        "Europe/Berlin",
        {
            "2024-10-26 23:00": 50000.0,
            "2024-10-27 00:00": 49000.0,
            "2024-10-27 04:00": 46000.0,
        },
    )


def test_ends_of_hours(fake_downloads, assert_demand):
    """Test that the times of a region of the United States are ends."""
    fake_downloads.serve(iea.get_url(), "iea_texas.json")

    time_series = iea.download_and_extract_data_for_request(
        (pd.Timestamp("2024-07-01"), pd.Timestamp("2024-07-02")), "USA_TEX"
    )

    assert fake_downloads.requests[0][2]["params"]["Region"] == "Texas"
    # The first value is that of the last hour of the day before.
    assert_demand(
        time_series,
        "America/New_York",
        {"2024-07-01 05:00": 71000.0, "2024-07-02 04:00": 72000.0},
    )


def test_renamed_region(monkeypatch):
    """Test that the later name of a region gives the common hours."""
    values = {
        "SIN-CEN": pd.Series(
            [1000.0, 2000.0],
            index=pd.to_datetime(["2023-01-01 00:00", "2023-01-01 01:00"]),
        ),
        "SIN-CEL": pd.Series(
            [2100.0, 3000.0],
            index=pd.to_datetime(["2023-01-01 01:00", "2023-01-01 02:00"]),
        ),
    }
    monkeypatch.setattr(
        iea,
        "_download",
        lambda _start, _end, parameter: values[parameter["Region"]],
    )

    time_series = iea.download_and_extract_data_for_request(
        (pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")), "MEX_CEN"
    )

    assert time_series.tolist() == [1000.0, 2100.0, 3000.0]


def test_hour_given_once_when_daylight_saving_time_ends(monkeypatch):
    """Test that the repeated hour given once is left out."""
    monkeypatch.setattr(
        iea,
        "_download",
        lambda *_: pd.Series(
            [50.0, 49.0, 48.0],
            index=pd.to_datetime(
                ["2024-10-27 01:00", "2024-10-27 02:00", "2024-10-27 03:00"]
            ),
        ),
    )

    time_series = iea.download_and_extract_data_for_request(
        (pd.Timestamp("2024-10-27"), pd.Timestamp("2024-10-28")), "DEU"
    )

    assert time_series.tolist() == [50.0, 48.0]
    assert not time_series.index.hasnans


def test_period_requested_month_by_month(monkeypatch):
    """
    Test that a period that the API cannot answer is split into months.

    The quarter fails, and each of its months is then requested once.
    """
    requested = []

    def fetch_text(_url, request_params, **_):
        """
        Fail the request of the quarter, and answer those of the months.

        Returns
        -------
        str
            The records of the first hour of the month.

        Raises
        ------
        ConnectionError
            For the request of the quarter.
        """
        requested.append((request_params["from"], request_params["to"]))
        if request_params["from"] == "2024-07-01" and (
            request_params["to"] == "2024-10-01"
        ):
            raise ConnectionError("HTTPError: 500 Server Error")
        return json.dumps(
            [{"Date": f"{request_params['from']}T00:00:00.000Z", "Value": 1.5}]
        )

    monkeypatch.setattr(iea.utils.fetcher, "fetch_text", fetch_text)

    records = iea._fetch_records(
        pd.Timestamp("2024-07-01"),
        pd.Timestamp("2024-10-01"),
        {"Region": "Mid-Atlantic"},
    )

    assert requested == [
        ("2024-07-01", "2024-10-01"),
        ("2024-07-01", "2024-08-01"),
        ("2024-08-01", "2024-09-01"),
        ("2024-09-01", "2024-10-01"),
    ]
    assert [record["Date"][:10] for record in records] == [
        "2024-07-01",
        "2024-08-01",
        "2024-09-01",
    ]


def test_month_that_the_api_cannot_answer(monkeypatch):
    """Test that a month that the API cannot answer is an error."""

    def fetch_text(*_, **__):
        """
        Fail every request.

        Raises
        ------
        ConnectionError
            Always.
        """
        raise ConnectionError("HTTPError: 500 Server Error")

    monkeypatch.setattr(iea.utils.fetcher, "fetch_text", fetch_text)

    with pytest.raises(ConnectionError):
        iea._fetch_records(
            pd.Timestamp("2024-07-01"),
            pd.Timestamp("2024-08-01"),
            {"Region": "Mid-Atlantic"},
        )


def test_data_not_found_is_not_split(monkeypatch):
    """Test that data not found is an error, without months."""
    requested = []

    def fetch_text(_url, request_params, **_):
        """
        Answer that the data is not found.

        Raises
        ------
        DataNotFoundError
            Always.
        """
        requested.append(request_params["from"])
        raise iea.utils.fetcher.DataNotFoundError("HTTP error 404")

    monkeypatch.setattr(iea.utils.fetcher, "fetch_text", fetch_text)

    with pytest.raises(iea.utils.fetcher.DataNotFoundError):
        iea._fetch_records(
            pd.Timestamp("2024-07-01"),
            pd.Timestamp("2024-10-01"),
            {"Region": "Mid-Atlantic"},
        )
    assert requested == ["2024-07-01"]


def test_late_times_of_california(monkeypatch):
    """Test that the late values of California are left out."""
    monkeypatch.setattr(
        iea,
        "_download",
        lambda *_: pd.Series(
            [10.0, 11.0, 12.0, 13.0],
            index=pd.to_datetime(
                [
                    "2022-06-15 19:00",
                    "2022-06-15 20:00",
                    "2025-12-02 18:00",
                    "2025-12-02 19:00",
                ]
            ),
        ),
    )

    time_series = iea.download_and_extract_data_for_request(
        (pd.Timestamp("2022-06-15"), pd.Timestamp("2025-12-03")), "USA_CAL"
    )

    # The hours kept end at 2022-06-15 23:00 and 2025-12-03 00:00 in
    # UTC, just before and at the end of the period.
    assert time_series.tolist() == [10.0, 13.0]
