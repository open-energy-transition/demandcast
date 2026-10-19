"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NITI Aayog,
    from manually downloaded files.
"""

import pandas as pd
import pytest
import utils.entities
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


def _write_states_file(file_path, demand_by_state):
    """
    Write a file of the states in the format of NITI Aayog.

    The first column has the state and the year, the rows are the
    hours, and a disclaimer is below the data.
    """
    rows = [
        {
            "State": f"{state} - 2024",
            "Date": date,
            "Hourly Demand Met (in MW)": demand,
        }
        for state, demand_by_date in demand_by_state.items()
        for date, demand in demand_by_date.items()
    ]
    rows.append({"State": "Copyright © 2026, NITI Aayog"})
    pd.DataFrame(rows).to_excel(file_path, index=False)


def test_download_and_extract_data_of_states(
    manual_downloads_folder, assert_demand
):
    """Test that the subdivisions sum their states, with all of them."""
    _write_states_file(
        manual_downloads_folder / "NITI_2024_DVC_Jharkhand.xlsx",
        {
            "DVC": {"01-Jan 12am": 3000.0, "01-Jan 1am": 2900.0},
            "Jharkhand": {"01-Jan 12am": 1500.0, "01-Jan 1am": 1400.0},
        },
    )
    _write_states_file(
        manual_downloads_folder / "NITI_2024_Uttarakhand_West-Bengal.xlsx",
        {
            "Uttarakhand": {"01-Jan 12am": 1800.0},
            "West Bengal": {"01-Jan 12am": 7000.5},
        },
    )
    pd.DataFrame(
        {
            "Year": [2024],
            "Date": ["01-Jan 12am"],
            "Hourly Demand Met (in MW)": [150000.5],
        }
    ).to_excel(manual_downloads_folder / "NITI_2024.xlsx", index=False)

    # The hour without West Bengal is left out, and the times mark the
    # end of each hour in India (UTC+5:30).
    assert_demand(
        niti.download_and_extract_data_for_request(None, "IND_JHWB"),
        "Asia/Kolkata",
        {"2023-12-31 19:30": 11500.5},
    )
    assert_demand(
        niti.download_and_extract_data_for_request(None, "IND_UT"),
        "Asia/Kolkata",
        {"2023-12-31 19:30": 1800.0},
    )
    # The files of the states are not read for India.
    assert_demand(
        niti.download_and_extract_data_for_request(None, "IND"),
        "Asia/Kolkata",
        {"2023-12-31 19:30": 150000.5},
    )


def test_subdivisions_match_the_entities():
    """Test that each subdivision of the YAML file has its states."""
    codes = utils.entities.read_codes_in(data_source="niti")

    assert sorted(code for code in codes if code != "IND") == sorted(
        niti.SUBDIVISIONS
    )
    states = [state for names in niti.SUBDIVISIONS.values() for state in names]
    assert len(states) == len(set(states)) == 34
