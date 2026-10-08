"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of the annual electricity demand per capita.
"""

import os
from unittest.mock import patch

import pandas as pd
import retrievals.annual_electricity_demand_per_capita as annual_demand
import utils.config


def test_run_data_retrieval_of_future_scenario(tmp_path):
    """Test that future data is saved where assemble.py reads it."""
    folders = utils.config.read_folders_structure() | {
        "annual_electricity_demand_per_capita_folder": str(tmp_path)
    }
    historical_data = pd.DataFrame(
        {2020: [7000.0], 2021: [7100.0]}, index=["FRA"]
    )

    with (
        patch("utils.config.read_folders_structure", return_value=folders),
        patch.object(
            annual_demand, "get_historical_data", return_value=historical_data
        ),
        patch.object(annual_demand.iiasa, "read"),
        patch.object(
            annual_demand.iiasa,
            "extrapolate",
            return_value=pd.Series({2022: 7200.0}),
        ) as mock_extrapolate,
    ):
        # The second run finds the files and skips the retrieval.
        for __ in range(2):
            annual_demand.run_data_retrieval(
                code="FRA",
                file=None,
                year=2022,
                start_year=None,
                end_year=None,
                scenario="SSP2-45",
            )

    assert sorted(os.listdir(tmp_path)) == [
        "FRA_SSP2_45.csv",
        "FRA_SSP2_45.parquet",
    ]
    mock_extrapolate.assert_called_once()
