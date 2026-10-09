"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Kansai
    Transmission and Distribution (Kansai TD).
"""

import pytest
from retrievals.electricity_demand_data_sources import kansaitd


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are years, then months from March 2024."""
    requests = kansaitd.get_available_requests()

    # The years are fiscal years, from April to March, so the data start
    # in April 2016, not in January as the YAML file says.
    assert requests[0] == (2016, None)
    assert requests[7:9] == [(2023, None), (2024, 3)]
    assert requests[-1] == (2025, 12)
    assert len(requests) == 30


@pytest.mark.parametrize("year", [2020, 2021])
def test_download_and_extract_data_for_request_yearly(
    year, fake_downloads, assert_demand
):
    """Test that the hourly demand of a fiscal year is read."""
    # The file of 2021 starts with a note and an empty row.
    fake_downloads.serve(
        "https://www.kansai-td.co.jp/denkiyoho/area-performance/csv/"
        f"area_jyukyu_jisseki_{year}.csv",
        f"kansaitd_{year}.csv",
    )

    time_series = kansaitd.download_and_extract_data_for_request(year, None)

    # The files cover the fiscal year, from April to March, and their
    # times mark the start of each hour.
    assert_demand(
        time_series,
        "Asia/Tokyo",
        {
            f"{year}-03-31 16:00": 12500,
            f"{year}-03-31 17:00": 12300,
            f"{year + 1}-03-31 15:00": 13000,
        },
        dtype="int64",
    )


def test_download_and_extract_data_for_request_monthly(
    fake_downloads, assert_demand
):
    """Test that the half-hourly demand of a month is read."""
    fake_downloads.serve(
        "https://www.kansai-td.co.jp/interchange/denkiyoho/area-performance/"
        "eria_jukyu_202403_06.csv",
        "kansaitd_2024-03.csv",
    )

    time_series = kansaitd.download_and_extract_data_for_request(2024, 3)

    # The files give the average demand in MW, with the date and the
    # start of each half hour in two columns.
    assert_demand(
        time_series,
        "Asia/Tokyo",
        {
            "2024-02-29 15:30": 15000,
            "2024-02-29 16:00": 14450,
            "2024-03-31 15:00": 11100,
        },
        dtype="int64",
    )
