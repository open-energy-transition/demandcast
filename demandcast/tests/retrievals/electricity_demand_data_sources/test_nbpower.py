"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NB Power.
"""

import pytest
from retrievals.electricity_demand_data_sources import nbpower

URL = "https://tso.nbpower.com/Public/en/system_information_archive.aspx"


@pytest.mark.usefixtures("frozen_now")
def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the file of a month is posted for and read."""
    # The form of the page is posted back with the month and the year.
    fake_downloads.serve(URL, "nbpower_page.html")
    fake_downloads.serve(URL, "nbpower.csv", method="POST")

    time_series = nbpower.download_and_extract_data_for_request(2024, 11)

    assert fake_downloads.requests[1][2]["data"] == {
        "__EVENTTARGET": "ctl00$cphMainContent$lbGetData",
        "ctl00$cphMainContent$ddlMonth": 11,
        "ctl00$cphMainContent$ddlYear": 2024,
        "__VIEWSTATE": "/wEPDwUKLTEyMzQ1Njc4OWRk",
        "__EVENTVALIDATION": "/wEdAAKZy7I8YmDVr1vZ",
    }
    # The times mark the end of each hour in local time. Daylight
    # saving time ends on 3 November 2024 at 02:00, so 01:00 comes
    # twice.
    assert_demand(
        time_series,
        "America/Moncton",
        {
            "2024-11-03 02:00": 1500,
            "2024-11-03 03:00": 1480,
            "2024-11-03 04:00": 1460,
            "2024-11-03 05:00": 1440,
            "2024-11-03 06:00": 1420,
        },
        dtype="int64",
    )
