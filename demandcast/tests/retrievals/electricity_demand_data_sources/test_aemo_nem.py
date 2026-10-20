"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AEMO for
    the National Electricity Market (NEM).
"""

import datetime

from retrievals.electricity_demand_data_sources import aemo_nem


def test_get_available_requests():
    """Test that the requests are the months of the data, to the end."""
    requests = aemo_nem.get_available_requests(
        "AUS_NSW", datetime.date(1998, 12, 7), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (1998, 12)
    assert requests[-1] == (2025, 12)
    assert len(requests) == 325


FOLDER_URL = (
    "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2025/"
    "MMSDM_2025_10/MMSDM_Historical_Data_SQLLoader/DATA/"
)


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the rooftop solar is added in NEM time, UTC+10."""
    url = (
        "https://www.aemo.com.au/aemo/data/nem/priceanddemand/"
        "PRICE_AND_DEMAND_202510_NSW1.csv"
    )
    # Daylight saving starts in Sydney on 5 October 2025 at 02:00.
    fake_downloads.serve(url, "aemo_nem_2025-10.csv")
    fake_downloads.serve(FOLDER_URL, "aemo_nem_rooftop_folder.html")
    fake_downloads.serve(
        "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/"
        "2025/MMSDM_2025_10/MMSDM_Historical_Data_SQLLoader/DATA/"
        "PUBLIC_ARCHIVE%23ROOFTOP_PV_ACTUAL%23FILE01%23202510010000.zip",
        "aemo_nem_rooftop.zip",
    )

    time_series = aemo_nem.download_and_extract_data_for_request(
        (2025, 10), "AUS_NSW"
    )

    assert fake_downloads.requests[0][2]["headers"] == {
        "User-Agent": "Mozilla/5.0"
    }
    # Each interval gets the rooftop solar of the 30 minutes it ends in,
    # the measured estimate rather than the satellite one, of New South
    # Wales: 01:55 and 02:00 none at night, 14:00 the measured 1500.25
    # MW, 14:30 the satellite 1300 MW, and 15:00, without an estimate,
    # is left out.
    assert_demand(
        time_series,
        "UTC+10:00",
        {
            "2025-10-04 15:55": 6000.5,
            "2025-10-04 16:00": 6010.25,
            "2025-10-05 04:00": 8500.25,
            "2025-10-05 04:30": 8400.0,
        },
    )


def test_download_and_extract_data_before_rooftop_solar(fake_downloads):
    """Test that the demand before 2017 has no rooftop solar."""
    fake_downloads.serve(
        "https://www.aemo.com.au/aemo/data/nem/priceanddemand/"
        "PRICE_AND_DEMAND_201612_NSW1.csv",
        "aemo_nem.csv",
    )

    time_series = aemo_nem.download_and_extract_data_for_request(
        (2016, 12), "AUS_NSW"
    )

    assert len(fake_downloads.requests) == 1
    assert time_series.iloc[2] == 7000.0


def test_download_and_extract_data_without_rooftop_solar(
    fake_downloads, caplog
):
    """Test that a month without rooftop solar is left out."""
    fake_downloads.serve(
        "https://www.aemo.com.au/aemo/data/nem/priceanddemand/"
        "PRICE_AND_DEMAND_202510_NSW1.csv",
        "aemo_nem_2025-10.csv",
    )
    fake_downloads.serve(FOLDER_URL, "aemo_nem_rooftop_folder_empty.html")

    time_series = aemo_nem.download_and_extract_data_for_request(
        (2025, 10), "AUS_NSW"
    )

    assert time_series.empty
    assert "not published yet" in caplog.text


def test_rooftop_solar_without_folder(monkeypatch):
    """Test that a month without its folder has no rooftop solar yet."""

    def fetch_content(_url):
        raise aemo_nem.utils.fetcher.DataNotFoundError("HTTP error 404")

    monkeypatch.setattr(aemo_nem, "_fetch_content", fetch_content)

    assert aemo_nem._get_rooftop_solar(2026, 10, "AUS_NSW") is None
