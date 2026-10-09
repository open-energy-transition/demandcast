"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from IESO.
"""

import pytest
from retrievals.electricity_demand_data_sources import ieso


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the old file and the years after."""
    assert ieso.get_available_requests() == [(None, True)] + [
        (year, False) for year in range(2002, 2026)
    ]


def test_download_and_extract_data_for_request_before_may_2002(
    fake_downloads, assert_demand
):
    """Test that the demand of 1994 to April 2002 is read in EST."""
    fake_downloads.serve(
        "https://www.ieso.ca/-/media/Files/IESO/Power-Data/data-directory/"
        "HourlyDemands_1994-2002.csv",
        "ieso_1994-2002.csv",
    )

    time_series = ieso.download_and_extract_data_for_request(None, True)

    # The certificate of the website is checked.
    assert fake_downloads.requests[0][2]["verify"] is True
    # The times are the starts of the hours, in two formats, which move
    # one hour later to mark their ends. They are in Eastern Standard
    # Time all year, so the days when daylight saving time starts and
    # ends in Toronto have all their hours.
    assert_demand(
        time_series,
        "UTC-05:00",
        {
            "1994-01-01 06:00": 14500,
            "1994-01-31 01:00": 19500,
            "1996-04-07 08:00": 12600,
            "1996-07-01 19:00": 17500,
            "1996-10-27 07:00": 13000,
            "2002-05-01 05:00": 14900,
        },
        dtype="int64",
    )


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the demand of a year is read in EST."""
    fake_downloads.serve(
        "https://reports-public.ieso.ca/public/Demand/PUB_Demand_2024.csv",
        "ieso_2024.csv",
    )

    time_series = ieso.download_and_extract_data_for_request(2024, False)

    # The hours are numbered from 1 to 24 by their ends, in Eastern
    # Standard Time all year, so the hour 24 ends at midnight of the
    # next day, and in summer the hour 14 ends at 19:00 UTC.
    assert_demand(
        time_series,
        "UTC-05:00",
        {
            "2024-01-01 06:00": 14500,
            "2024-03-10 07:00": 13200,
            "2024-03-10 08:00": 13000,
            "2024-07-14 19:00": 19600,
            "2025-01-01 05:00": 14300,
        },
        dtype="int64",
    )
