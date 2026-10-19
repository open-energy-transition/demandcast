"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NESO.
"""

import datetime

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import neso

CATALOGUE_URL = (
    "https://api.neso.energy/api/3/action/package_show?id=historic-demand-data"
)
URL_2025 = (
    "https://api.neso.energy/api/3/action/datastore_search_sql?"
    "sql=SELECT%20*%20FROM%20%22b2bde559-3455-4021-b179-dfe60c0337b0%22"
    "%20ORDER%20BY%20%22_id%22%20ASC%20LIMIT%20100000"
)


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = neso.get_available_requests(
        "GBR_GB", datetime.date(2009, 1, 1), datetime.date(2025, 12, 28)
    )

    assert requests == list(range(2009, 2026))


def test_get_url(fake_downloads):
    """Test that the dataset of the year is found by its name."""
    fake_downloads.serve(CATALOGUE_URL, "neso_catalogue.json")

    assert neso.get_url(2025) == URL_2025


def test_get_url_without_dataset(fake_downloads):
    """Test that a year missing from the catalogue is an error."""
    # The catalogue of the fixture has no dataset for 2024.
    fake_downloads.serve(CATALOGUE_URL, "neso_catalogue.json")

    with pytest.raises(ValueError, match="2024"):
        neso.get_url(2024)


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the settlement periods end after the local midnight."""
    fake_downloads.serve(CATALOGUE_URL, "neso_catalogue.json")
    fake_downloads.serve(URL_2025, "neso.json")

    time_series = neso.download_and_extract_data_for_request(2025, "GBR_GB")

    # Each settlement period ends 30 minutes times its number after the
    # local midnight, in absolute time: when daylight saving time ends
    # on 26 October, the periods 3 to 6 end every 30 minutes from 00:30
    # in UTC, across the change of the clocks at 01:00 in UTC. The
    # forecasts are left out.
    assert_demand(
        time_series,
        "Europe/London",
        {
            "2025-01-01 00:30": 25000,
            "2025-01-01 01:00": 24500,
            "2025-10-26 00:30": 21000,
            "2025-10-26 01:00": 20800,
            "2025-10-26 01:30": 20600,
            "2025-10-26 02:00": 20400,
        },
        dtype="int64",
    )


@pytest.mark.parametrize(
    "dates",
    [
        ["2024-01-01", "2024-12-31"],
        ["2024-01-01T00:00:00", "2024-12-31T00:00:00"],
        ["01-JAN-2024", "31-DEC-2024"],
        ["01-Jan-24", "31-Dec-24"],
    ],
)
def test_read_dates(dates):
    """Test that the settlement dates are read in each format."""
    assert neso._read_dates(pd.Series(dates)).tolist() == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-12-31"),
    ]


def test_read_dates_in_another_format():
    """Test that dates in another format are rejected."""
    with pytest.raises(ValueError, match="not in one of the formats"):
        neso._read_dates(pd.Series(["2024/01/01"]))
