"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NEA.
"""

import datetime

from retrievals.electricity_demand_data_sources import nea


def test_get_available_requests():
    """Test that the requests are the months of the Nepali year."""
    requests = nea.get_available_requests(
        "NPL", datetime.date(2017, 4, 14), datetime.date(2018, 4, 13)
    )

    assert requests == [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12]


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the Nepali days and hourly columns are converted."""
    fake_downloads.serve(
        "https://api.opendatanepal.com/api/action/datastore_search?"
        "resource_id=b72c50b8-2e05-43f6-8232-7696caf07c70&sort=_id asc",
        "nea.json",
    )

    time_series = nea.download_and_extract_data_for_request(12, "NPL")

    # Day 1 of month 12 of the Nepali year 2074 is 15 March 2018, and
    # 0:00 is the end of the day.
    assert_demand(
        time_series,
        "Asia/Kathmandu",
        {
            "2018-03-14 19:15": 800.5,
            "2018-03-14 20:15": 780.0,
            "2018-03-15 18:15": 750.25,
            "2018-03-15 19:15": 810.0,
            "2018-03-15 20:15": 790.5,
            "2018-03-16 18:15": 760.0,
        },
    )
