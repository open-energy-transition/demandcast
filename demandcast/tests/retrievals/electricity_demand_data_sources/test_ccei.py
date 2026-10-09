"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CCEI.
"""

from retrievals.electricity_demand_data_sources import ccei


def test_download_and_extract_data_of_ontario(fake_downloads, assert_demand):
    """Test that the hours of IESO are read in Eastern Standard Time."""
    fake_downloads.serve(
        "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/"
        "CCEI,DF_HFED_ON,1.0/N...ONTARIO_DEMAND?"
        "&dimensionAtObservation=AllDimensions&format=csv",
        "ccei_on.csv",
    )

    time_series = ccei.download_and_extract_data("CAN_ON")

    # The local times (DATETIME_LOCAL) are the ends of IESO's hours in
    # Eastern Standard Time all year, with the hour 24 at 00:00 of the
    # same day. The times in UTC (TIME_PERIOD) follow daylight saving
    # time instead, with the hour 2 of 10 March at 06:59:59.
    assert_demand(
        time_series,
        "UTC",
        {
            "2024-01-02 06:00": 14700,
            "2024-01-03 05:00": 15400,
            "2024-03-10 06:00": 13400,
            "2024-03-10 07:00": 13200,
            "2024-03-10 08:00": 13000,
            "2024-07-14 19:00": 19600,
        },
        dtype="int64",
    )
