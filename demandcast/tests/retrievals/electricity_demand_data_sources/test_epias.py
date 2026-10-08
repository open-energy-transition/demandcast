"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from EPIAS, from
    manually downloaded files.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import epias


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the hourly demand is read from the Excel files."""
    pd.DataFrame(
        {
            "Tarih": ["01/01/2024 00:00:00", "01/01/2024 01:00:00"],
            "Tüketim Miktarı(MWh)": [30000.5, 29000.25],
        }
    ).to_excel(manual_downloads_folder / "EPIAS_2024.xlsx", index=False)

    time_series = epias.download_and_extract_data()

    # The times mark the end of each hour.
    assert_demand(
        time_series,
        "Europe/Istanbul",
        {"2023-12-31 22:00": 30000.5, "2023-12-31 23:00": 29000.25},
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'EPI'"):
        epias.download_and_extract_data()
