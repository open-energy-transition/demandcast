"""
License: AGPL-3.0.

Description:

    Tests for the codes of interest and the check of their data, in
    utils/availability.py.
"""

from unittest.mock import patch

import pandas as pd
import pytest

import utils.availability


def test_get_all_codes_with_all_data():
    """
    Test if the function _get_all_codes_with_all_data works correctly.

    This test checks if the function can read the available data summary
    from a CSV file and return a list of codes for which all data is
    available.
    """
    with (
        patch("pandas.read_csv") as mock_read_csv,
        patch("os.path.join") as mock_path_join,
    ):
        mock_path_join.return_value = "/checks/available_data_summary.csv"

        # Mock the return value of pandas.read_csv to return a sample
        # DataFrame.
        mock_read_csv.return_value = pd.DataFrame(
            {
                "historical_population": [True, True, True, False],
                "historical_electricity_demand_per_capita": [
                    True,
                    True,
                    False,
                    True,
                ],
                "historical_gdp_ppp_per_capita": [True, False, True, True],
                "future_population": [True, True, True, False],
                "future_electricity_demand_per_capita": [
                    True,
                    True,
                    False,
                    True,
                ],
                "future_gdp_ppp_per_capita": [True, False, True, True],
                "area_greater_than_500_km2": [True, True, True, True],
            },
            index=["XY1", "XY2", "XY3", "XY4"],
        )

        # Get all codes with all data available.
        all_data_codes = utils.availability.read_codes_with_all_data()

        # Check if the function returns a list of codes.
        assert isinstance(all_data_codes, list)

        # Check if the codes are read correctly.
        assert "XY1" in all_data_codes
        assert "XY2" in all_data_codes
        assert "XY3" not in all_data_codes
        assert "XY4" in all_data_codes


def test_check_and_get_codes_with():
    """
    Test if the function check_and_get_codes_with works correctly.

    This test checks if the function can read codes from a yaml file,
    from a specific data source, or from a specific code, and if it
    handles errors correctly.
    """
    # Read codes belonging to a specific data source.
    entsoe_codes = utils.availability.check_and_get_codes_with(
        "electricity_demand_data", data_source="entsoe"
    )
    assert isinstance(entsoe_codes, list)
    assert "FRA" in entsoe_codes
    assert "USA_TEX" not in entsoe_codes

    # Check the validity of a specific code for a specific data source.
    assert utils.availability.check_and_get_codes_with(
        "electricity_demand_data", code="FRA", data_source="entsoe"
    ) == ["FRA"]

    # Read codes from a specified file path and check them.
    with (
        patch("utils.data_sources.read_codes_in") as mock_read_codes,
        patch(
            "utils.data_sources.read_all_codes_with_electricity_demand_data"
        ) as mock_read_all_codes,
    ):
        # Mock the return value of read_codes_in to return codes from a
        # specific file.
        mock_read_codes.return_value = ["FRA", "DEU"]

        # Mock the return value of
        # read_all_codes_with_electricity_demand_data to return all
        # available codes with demand data.
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        # Check if the codes from the file are read correctly.
        dummy_codes = utils.availability.check_and_get_codes_with(
            "electricity_demand_data", file_path="dummy.yaml"
        )

        # Check if the codes for a specific file are read correctly.
        assert isinstance(dummy_codes, list)
        assert "FRA" in dummy_codes
        assert "USA_TEX" not in dummy_codes

    # Read codes for which all data is available.
    with patch(
        "utils.availability.read_codes_with_all_data"
    ) as mock_get_all_codes:
        # Mock the return value of _get_all_codes_with_all_data to
        # return a sample list of codes.
        mock_get_all_codes.return_value = ["XYZ1", "XYZ2"]

        # Get all codes with all data available.
        shape_codes = utils.availability.check_and_get_codes_with("all_data")

        # Check if the codes are read correctly.
        assert isinstance(shape_codes, list)
        assert "XYZ1" in shape_codes
        assert "XYZ2" in shape_codes
        assert "XYZ3" not in shape_codes


def test_check_and_get_codes_with_errors():
    """
    Test if the check_and_get_codes_with function handles errors.

    This test checks if the function raises errors for invalid codes,
    invalid data sources, and if the codes in the file do not match the
    expected codes.
    """
    # Check if the function raises an error for an invalid feature.
    with pytest.raises(ValueError, match="Invalid feature"):
        utils.availability.check_and_get_codes_with(
            "INVALID_FEATURE", code="FRA", data_source="entsoe"
        )

    # Check if the function raises an error when a data source is
    # provided for the "all_data" feature.
    with pytest.raises(
        ValueError, match="is not associated with a data source"
    ):
        utils.availability.check_and_get_codes_with(
            "all_data", code="FRA", data_source="entsoe"
        )

    # Check if the function raises an error for an invalid code.
    with pytest.raises(ValueError, match="is not available in data source"):
        utils.availability.check_and_get_codes_with(
            "electricity_demand_data",
            code="INVALID_CODE",
            data_source="entsoe",
        )
    with pytest.raises(ValueError, match="does not have all_data"):
        utils.availability.check_and_get_codes_with(
            "all_data",
            code="INVALID_CODE",
        )

    # Check if the function raises an error for invalid codes read from
    # a file.
    with (
        patch("utils.data_sources.read_codes_in") as mock_read_codes,
        patch(
            "utils.data_sources.read_all_codes_with_electricity_demand_data"
        ) as mock_read_all_codes,
    ):
        # Mock the return value of read_codes_in to return invalid
        # codes.
        mock_read_codes.return_value = ["USA_CAL", "USA_TEX"]

        # Mock the return value of
        # read_all_codes_with_electricity_demand_data
        # to return all available codes with demand data.
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        # Check if the function raises an error for invalid codes.
        with pytest.raises(
            ValueError, match="None of the codes in the file are available"
        ):
            utils.availability.check_and_get_codes_with(
                "electricity_demand_data", file_path="dummy.yaml"
            )

    # Check if the function raises an error for invalid codes read from
    # a file.
    with (
        patch("utils.data_sources.read_codes_in") as mock_read_codes,
        patch(
            "utils.availability.read_codes_with_all_data"
        ) as mock_read_all_codes,
    ):
        # Mock the return value of read_codes_in to return invalid
        # codes.
        mock_read_codes.return_value = ["USA_CAL", "USA_TEX"]

        # Mock the return value of
        # read_all_codes_with_electricity_demand_data
        # to return all available codes with demand data.
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        # Check if the function raises an error for invalid codes.
        with pytest.raises(
            ValueError, match="None of the codes in the file are available"
        ):
            utils.availability.check_and_get_codes_with(
                "all_data", file_path="dummy.yaml"
            )

    with patch("utils.data_sources.read_codes_in") as mock_read_codes:
        # Check if the function raises an error for invalid codes.
        # Mock the return value of read_codes_in for two times, the
        # first time for electricity demand data, the second time
        # for the codes in the file.
        mock_read_codes.side_effect = [
            ["USA_CAL", "USA_TEX"],
            ["FRA", "DEU", "ITA"],
        ]

        # Check if the function raises an error when the codes in
        # the file do not match the expected codes.
        with pytest.raises(
            ValueError, match="None of the codes in the file are available"
        ):
            utils.availability.check_and_get_codes_with(
                "electricity_demand_data",
                data_source="entsoe",
                file_path="dummy.yaml",
            )
