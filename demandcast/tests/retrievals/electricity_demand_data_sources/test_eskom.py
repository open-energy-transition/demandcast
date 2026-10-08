"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Eskom, from
    manually downloaded files.
"""

import pytest
from retrievals.electricity_demand_data_sources import eskom


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the demand of each hour is read from the CSV files."""
    (manual_downloads_folder / "ESKOM_2023.csv").write_text(
        "Date Time Hour Beginning,Residual Demand,RSA Contracted Demand\n"
        "2023-04-01 00:00:00 AM,20000.5,22000.5\n"
        "2023-04-01 13:00:00 PM,23000,25000.25\n",
        encoding="utf-8",
    )

    time_series = eskom.download_and_extract_data()

    # The hours are read in 24-hour format, ignoring AM and PM, and the
    # times mark the end of each hour.
    assert_demand(
        time_series,
        "Africa/Johannesburg",
        {"2023-03-31 23:00": 22000.5, "2023-04-01 12:00": 25000.25},
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'ESK'"):
        eskom.download_and_extract_data()
