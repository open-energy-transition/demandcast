"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NB Power.
"""

import datetime as dt

from retrievals.electricity_demand_data_sources import nbpower

URL = "https://tso.nbpower.com/Public/en/system_information_archive.aspx"


def test_get_available_requests():
    """Test that the requests are the months of the archive."""
    requests = nbpower.get_available_requests(
        "CAN_NB", dt.date(2019, 1, 1), dt.date(2025, 12, 28)
    )

    # The archive starts in 2019: the form rejects earlier years. The
    # last month is November 2025, since the data ends five days before
    # today.
    assert requests[0] == (2019, 1)
    assert requests[-1] == (2025, 11)
    assert len(requests) == 83


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the file of a month is posted for and read."""
    # The form of the page is posted back with the month and the year.
    fake_downloads.serve(URL, "nbpower_page.html")
    fake_downloads.serve(URL, "nbpower.csv", method="POST")

    time_series = nbpower.download_and_extract_data_for_request(
        (2024, 11), "CAN_NB"
    )

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


def test_times_that_cannot_be_placed_are_dropped(
    fake_downloads, assert_demand, tmp_path
):
    """
    Test that a time that cannot be placed drops only its own value.

    The second 01:00 of the day when daylight saving time ends is
    missing, so the first one could be in either time, a time cannot be
    read, and 02:00 does not exist on the day when it starts.
    """
    file_path = tmp_path / "nbpower.csv"
    file_path.write_text(
        "HOUR,NB_LOAD\n"
        "2024-03-10 01:00,1700\n"
        "2024-03-10 02:00,1690\n"
        "2024-03-10 03:00,1680\n"
        "2024-11-03 00:00,1480\n"
        "2024-11-03 01:00,1460\n"
        "2024-11-03 02:00,1420\n"
        "2024-11-03 2:00 AM,1410\n",
        encoding="utf-8",
    )
    fake_downloads.serve(URL, "nbpower_page.html")
    fake_downloads.serve(URL, file_path, method="POST")

    time_series = nbpower.download_and_extract_data_for_request(
        (2024, 11), "CAN_NB"
    )

    assert_demand(
        time_series,
        "America/Moncton",
        {
            "2024-03-10 05:00": 1700,
            "2024-03-10 06:00": 1680,
            "2024-11-03 03:00": 1480,
            "2024-11-03 06:00": 1420,
        },
        dtype="int64",
    )
