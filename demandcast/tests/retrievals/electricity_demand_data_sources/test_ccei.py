"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CCEI.
"""

import pandas as pd
from retrievals.electricity_demand_data_sources import ccei

# The URL of the data of CCEI, without the dataflow and the variable.
URL = "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/CCEI,DF_HFED_{}"
QUERY = "?&dimensionAtObservation=AllDimensions&format=csv"


def test_download_and_extract_data_of_alberta(fake_downloads, assert_demand):
    """Test that the demand every 5 minutes is read in UTC."""
    fake_downloads.serve(
        URL.format("AB,1.0/N...INTERNAL_LOAD") + QUERY, "ccei_ab.csv"
    )

    time_series = ccei.download_and_extract_data_for_request(None, "CAN_AB")

    # The times in UTC (TIME_PERIOD) are read as they are.
    assert_demand(
        time_series,
        "UTC",
        {
            "2024-01-01 07:00": 10400,
            "2024-01-01 07:05": 10380,
            "2024-01-01 07:10": 10350,
        },
        dtype="int64",
    )


def test_download_and_extract_data_of_new_brunswick(
    fake_downloads, assert_demand
):
    """Test that the times of New Brunswick are read in all formats."""
    fake_downloads.serve(URL.format("NB,1.0/N...LOAD") + QUERY, "ccei_nb.csv")

    time_series = ccei.download_and_extract_data_for_request(None, "CAN_NB")

    # In 2021, hourly times are mixed with 5-minute times that end with
    # ".000Z", which is removed so that pandas can read them together.
    # Later times have irregular seconds, which are kept.
    assert_demand(
        time_series,
        "UTC",
        {
            "2021-06-01 00:00": 1420,
            "2021-06-01 00:05": 1400,
            "2024-01-01 00:10": 2050,
        },
        dtype="int64",
    )
    assert time_series.index[1] == pd.Timestamp("2021-06-01 00:05:11Z")
    assert time_series.index[2] == pd.Timestamp("2024-01-01 00:10:22Z")


def test_download_and_extract_data_of_ontario(fake_downloads, assert_demand):
    """Test that the hours of IESO are read in Eastern Standard Time."""
    fake_downloads.serve(
        "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/"
        "CCEI,DF_HFED_ON,1.0/N...ONTARIO_DEMAND?"
        "&dimensionAtObservation=AllDimensions&format=csv",
        "ccei_on.csv",
    )

    time_series = ccei.download_and_extract_data_for_request(None, "CAN_ON")

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
