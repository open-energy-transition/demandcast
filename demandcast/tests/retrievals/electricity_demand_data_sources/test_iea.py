"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from the IEA.
"""

import datetime as dt

import pandas as pd

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
