"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Taipower.
"""

from retrievals.electricity_demand_data_sources import taipower


def test_download_and_extract_data(fake_downloads, assert_demand):
    """Test that the demand of the four regions is summed."""
    fake_downloads.serve(
        "https://zenodo.org/records/7537890/files/"
        "loadarea_10min_2017Jan_2022Jun.csv?download=1",
        "taipower.csv",
    )

    time_series = taipower.download_and_extract_data_for_request(None, "TWN")

    # The times move ten minutes later, to the end of each interval.
    assert_demand(
        time_series,
        "Asia/Taipei",
        {
            "2016-12-31 16:10": 19730.0,
            "2016-12-31 16:20": 19575.0,
            "2022-07-01 16:00": 30920.0,
        },
    )
