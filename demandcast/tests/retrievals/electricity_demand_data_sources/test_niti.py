"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NITI Aayog,
    from manually downloaded files.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import niti


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the hourly demand is read from the Excel files."""
    pd.DataFrame(
        {
            "Year": [2023, 2023],
            "Date": ["01-Jan 12AM", "01-Jan 1PM"],
            "Hourly Demand Met (in MW)": [150000.5, 180000.25],
        }
    ).to_excel(manual_downloads_folder / "NITI_2023.xlsx", index=False)

    time_series = niti.download_and_extract_data_for_request(None, "IND")

    # The times mark the end of each hour.
    assert_demand(
        time_series,
        "Asia/Kolkata",
        {"2022-12-31 19:30": 150000.5, "2023-01-01 08:30": 180000.25},
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'NIT'"):
        niti.download_and_extract_data_for_request(None, "IND")
