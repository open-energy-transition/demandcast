"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data of Corsica from
    EDF SEI, with a synthetic CSV file of the API of EDF.
"""

import datetime as dt

import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import edf_sei


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    assert edf_sei.get_available_requests(
        "FRA_20R", dt.date(2019, 1, 1), dt.date(2021, 6, 30)
    ) == [2019, 2020, 2021]


@pytest.fixture
def dataset(fake_downloads, tmp_path):
    """
    Serve the rows of the days of the changes of the clocks in 2024.

    The times are written in UTC but are local, and the hour that the
    clocks skip in March has zero demand.
    """
    times = [
        *pd.date_range("2024-03-31 00:00", periods=4, freq="h"),
        *pd.date_range("2024-10-27 01:00", periods=3, freq="h"),
    ]
    demand = [200.0, 190.0, 0.0, 180.0, 170.0, 160.0, 150.0]
    rows = pd.DataFrame(
        {
            "statut": "Estimé",
            "date_heure": [
                time.strftime("%Y-%m-%dT%H:%M:%S+00:00") for time in times
            ],
            "production_totale_mw": demand,
        }
    )
    path = tmp_path / "lines.csv"
    rows.to_csv(path, index=False, encoding="utf-8-sig")
    fake_downloads.serve(edf_sei.get_url(), path)


@pytest.mark.usefixtures("dataset")
def test_download_and_extract_data(fake_downloads, assert_demand):
    """
    Test that the demand is at the ends of the hours in local time.

    The hour at 02:00 on 31 March does not exist and that at 02:00 on 27
    October is ambiguous, so both are left out. The hour that starts at
    00:00 on 31 March, in UTC+1, ends at 00:00 in UTC, and the one that
    starts at 03:00, in UTC+2, at 02:00 in UTC.
    """
    time_series = edf_sei.download_and_extract_data_for_request(
        2024, "FRA_20R"
    )

    assert fake_downloads.requests[0][2]["params"]["qs"] == (
        "date_heure:[2024-01-01 TO 2024-12-31]"
    )
    assert_demand(
        time_series,
        "Europe/Paris",
        {
            "2024-03-31 00:00": 200.0,
            "2024-03-31 01:00": 190.0,
            "2024-03-31 02:00": 180.0,
            "2024-10-27 00:00": 170.0,
            "2024-10-27 03:00": 150.0,
        },
    )
