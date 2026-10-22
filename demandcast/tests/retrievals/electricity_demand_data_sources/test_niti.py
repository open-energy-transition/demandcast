"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NITI Aayog,
    from manually downloaded files.
"""

import pandas as pd
import pytest
import utils.data_sources
from retrievals.electricity_demand_data_sources import niti


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


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
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
            "Uttarakhand": {"01-Jan 12am": 1800.0, "01-Jan 1pm": 2000.25},
            "West Bengal": {"01-Jan 12am": 7000.5},
        },
    )
    # A file of the demand of India, with the year in its first column,
    # is left out.
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
        {"2023-12-31 19:30": 1800.0, "2024-01-01 08:30": 2000.25},
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'NIT'"):
        niti.download_and_extract_data_for_request(None, "IND_KA")


def test_subdivisions_match_the_entities():
    """Test that each subdivision of the YAML file has its states."""
    codes = utils.data_sources.read_codes_in(data_source="niti")

    assert sorted(codes) == sorted(niti.SUBDIVISIONS)
    states = [state for names in niti.SUBDIVISIONS.values() for state in names]
    assert len(states) == len(set(states)) == 34


def test_files_are_read_once(manual_downloads_folder, monkeypatch):
    """Test that the files are read once, until they change."""
    reads = []
    read_manual_files = niti.utils.fetcher.read_manual_files

    def count_reads(*args, **kwargs):
        reads.append(kwargs["prefix"])
        return read_manual_files(*args, **kwargs)

    monkeypatch.setattr(niti.utils.fetcher, "read_manual_files", count_reads)
    _write_states_file(
        manual_downloads_folder / "NITI_2024_Assam_Bihar.xlsx",
        {"Assam": {"01-Jan 12am": 1400.0}, "Bihar": {"01-Jan 12am": 4800.0}},
    )

    niti.download_and_extract_data_for_request(None, "IND_AS")
    niti.download_and_extract_data_for_request(None, "IND_BR")
    assert len(reads) == 1

    # A new file is read with the others.
    _write_states_file(
        manual_downloads_folder / "NITI_2024_Goa_Gujarat.xlsx",
        {"Goa": {"01-Jan 12am": 480.0}, "Gujarat": {"01-Jan 12am": 17000.0}},
    )
    assert niti.download_and_extract_data_for_request(
        None, "IND_GA"
    ).tolist() == [480.0]
    assert len(reads) == 2
