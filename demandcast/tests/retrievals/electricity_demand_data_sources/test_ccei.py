"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from CCEI.
"""

from retrievals.electricity_demand_data_sources import ccei

_BASE = "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/"
_QUERY = "?&dimensionAtObservation=AllDimensions&format=csv"


def test_download_and_extract_data(fake_downloads, assert_demand):
    """Test that the demand is read from the SDMX CSV files."""
    fake_downloads.serve(
        f"{_BASE}CCEI,DF_HFED_AB,1.0/N...INTERNAL_LOAD{_QUERY}",
        "ccei_ab.csv",
    )
    fake_downloads.serve(
        f"{_BASE}CCEI,DF_HFED_NB,1.0/N...LOAD{_QUERY}",
        "ccei_nb.csv",
    )
    fake_downloads.serve(
        f"{_BASE}CCEI,DF_HFED_ON,1.0/N...ONTARIO_DEMAND{_QUERY}",
        "ccei_on.csv",
    )

    alberta = ccei.download_and_extract_data("CAN_AB")
    new_brunswick = ccei.download_and_extract_data("CAN_NB")
    ontario = ccei.download_and_extract_data("CAN_ON")

    # The files already use UTC. New Brunswick appends ".000Z", which
    # is removed before the time is localized. Ontario drops the dummy
    # 06:59:59 step before the daylight saving time change.
    assert_demand(
        alberta,
        "UTC",
        {
            "2024-01-01 05:00": 1501.5,
            "2024-01-01 06:00": 1460.75,
            "2024-03-10 08:00": 1720.125,
        },
    )
    assert_demand(
        new_brunswick,
        "UTC",
        {
            "2024-01-01 05:00": 2100.5,
            "2024-01-01 06:00": 1980.0,
        },
    )
    assert_demand(
        ontario,
        "UTC",
        {
            "2024-03-10 06:00": 18010.0,
            "2024-03-10 07:00": 17640.5,
        },
    )
