"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NTDC, from
    manually downloaded files.
"""

import pytest
from retrievals.electricity_demand_data_sources import ntdc


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the hours and the loads with commas are read."""
    # The files have the date, the hour from 1 to 24 and the load.
    (manual_downloads_folder / "NTDC_2024.csv").write_text(
        'DATE,HOUR,SYSLOAD\n01/01/2024,1,"15,000"\n01/01/2024,24,"17,500.5"\n',
        encoding="utf-8",
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    # The times mark the end of each hour.
    assert_demand(
        time_series,
        "Asia/Karachi",
        {"2023-12-31 20:00": 15000.0, "2024-01-01 19:00": 17500.5},
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'NTD'"):
        ntdc.download_and_extract_data_for_request(None, "PAK")
