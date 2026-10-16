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

    assert requests == list(range(1, 13))


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


def test_download_and_extract_data_of_shrawan(fake_downloads, assert_demand):
    """Test that the times as fractions of a day of Shrawan are read."""
    fake_downloads.serve(
        "https://api.opendatanepal.com/api/action/datastore_search?"
        "resource_id=0a9a3631-0249-4f48-8627-ce82691e2c79&sort=_id asc",
        "nea_shrawan.json",
    )

    time_series = nea.download_and_extract_data_for_request(4, "NPL")

    # Day 1 of month 4 of the Nepali year 2074 is 16 July 2017. The
    # fractions 0.04, 0.23 and 0.00 are 1:00, 5:30 and the end of the
    # day.
    assert_demand(
        time_series,
        "Asia/Kathmandu",
        {
            "2017-07-15 19:15": 835.3,
            "2017-07-15 23:45": 823.0,
            "2017-07-16 18:15": 881.6,
            "2017-07-16 19:15": 829.2,
            "2017-07-16 23:45": 820.5,
            "2017-07-17 18:15": 904.0,
        },
    )
