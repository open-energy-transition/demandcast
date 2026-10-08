"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EGAT.
"""

from retrievals.electricity_demand_data_sources import egat


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    assert egat.get_available_requests() == [2023, 2024]


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the demand of the five regions is summed."""
    fake_downloads.serve(
        "https://zenodo.org/records/17109911/files/system_2024.csv?download=1",
        "egat_2024.csv",
    )

    time_series = egat.download_and_extract_data_for_request(2024)

    # The times move one hour later, as if they marked the start of each
    # hour, although each file starts at 0:05, which suggests that they
    # mark the end. Each file ends on 1 January of the next year.
    assert_demand(
        time_series,
        "Asia/Bangkok",
        {
            "2023-12-31 18:05": 16201.5,
            "2023-12-31 19:00": 15940.0,
            "2025-01-01 17:00": 15450.0,
        },
    )
