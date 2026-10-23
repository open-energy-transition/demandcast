"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AESO.
"""

import datetime

import pytest

from retrievals.electricity_demand_data_sources import aeso

URL_FOLDER = (
    "https://www.aeso.ca/assets/Uploads/data-requests/"
    "Hourly_Metered_Volumes_and_Pool_Price_and_AIL_"
)


@pytest.mark.parametrize(
    ("start_date", "end_date", "periods"),
    [
        (
            datetime.date(2001, 1, 1),
            datetime.date(2025, 7, 31),
            ["2001-2009", "2010-2019", "2020-Jul2025"],
        ),
        (
            datetime.date(2015, 6, 1),
            datetime.date(2020, 1, 1),
            ["2010-2019", "2020-Jul2025"],
        ),
        (
            datetime.date(2012, 1, 1),
            datetime.date(2012, 12, 31),
            ["2010-2019"],
        ),
    ],
)
def test_get_available_requests(start_date, end_date, periods):
    """Test that the requests are the files with data between dates."""
    assert aeso.get_available_requests("CAN_AB", start_date, end_date) == (
        periods
    )


@pytest.mark.parametrize(
    ("period", "file_name", "expected"),
    [
        # The file of 2010 to 2019 writes the dates month first.
        # Daylight saving time starts on 13 March 2011, which has no
        # local hour 2, but the times in UTC follow each other.
        (
            "2010-2019",
            "aeso_2010-2019.csv",
            {
                "2011-03-13 09:00": 8100,
                "2011-03-13 10:00": 8050,
                "2011-03-13 11:00": 8000,
            },
        ),
        # Daylight saving time ends on 3 November 2024, when the local
        # hour 1 comes twice.
        (
            "2020-Jul2025",
            "aeso_2020-Jul2025.csv",
            {
                "2024-11-03 08:00": 9900,
                "2024-11-03 09:00": 9850,
                "2024-11-03 10:00": 9800,
            },
        ),
    ],
)
def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, period, file_name, expected
):
    """Test that the AIL is read at the ends of the hours in UTC."""
    fake_downloads.serve(f"{URL_FOLDER}{period}.csv", file_name)

    time_series = aeso.download_and_extract_data_for_request(period, "CAN_AB")

    assert_demand(time_series, "UTC", expected, dtype="int64")
