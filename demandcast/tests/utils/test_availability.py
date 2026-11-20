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
import utils.data_sources
import utils.paths


@pytest.fixture
def write_summary(tmp_path, monkeypatch):
    """
    Point the folder of the checks to a temporary folder.

    Returns
    -------
    Callable[[pandas.DataFrame], None]
        A function that writes a summary of the availability of the
        data there.
    """
    monkeypatch.setattr(utils.paths, "CHECKS_FOLDER", str(tmp_path))

    def write(summary: pd.DataFrame) -> None:
        """
        Write the summary of the availability of the data.

        Parameters
        ----------
        summary : pandas.DataFrame
            The flags of the data of each code, with the codes as
            index.
        """
        summary.to_csv(utils.paths.get_availability_summary_file())

    return write


def test_get_all_codes_with_all_data(write_summary):
    """
    Test the codes with all the data, read from the summary.

    A code needs all the data, or the electricity demand per capita
    with an area of more than 500 km².
    """
    write_summary(
        pd.DataFrame(
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
    )

    assert utils.availability.read_codes_with_all_data() == [
        "XY1",
        "XY2",
        "XY4",
    ]


def test_check_and_get_codes_with():
    """
    Test if the function check_and_get_codes_with works correctly.

    The codes are those of a data source, a code, a yaml file, or all
    the codes with all the data.
    """
    # Read codes belonging to a specific data source.
    entsoe_codes = utils.availability.check_and_get_codes_with(
        "electricity_demand_data", data_source="entsoe"
    )
    assert entsoe_codes == utils.data_sources.read_codes_in(
        data_source="entsoe"
    )
    assert "DEU" in entsoe_codes
    assert "USA_TEX" not in entsoe_codes

    # Check the validity of a specific code for a specific data source.
    assert utils.availability.check_and_get_codes_with(
        "electricity_demand_data", code="DEU", data_source="entsoe"
    ) == ["DEU"]

    # Read codes from a specified file path and check them.
    with (
        patch("utils.data_sources.read_codes_in") as mock_read_codes,
        patch("utils.data_sources.read_all_codes") as mock_read_all_codes,
    ):
        mock_read_codes.return_value = ["FRA", "USA_TEX", "DEU"]
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        dummy_codes = utils.availability.check_and_get_codes_with(
            "electricity_demand_data", file_path="dummy.yaml"
        )

        assert dummy_codes == ["FRA", "DEU"]

    # Read codes for which all data is available.
    with patch(
        "utils.availability.read_codes_with_all_data"
    ) as mock_get_all_codes:
        mock_get_all_codes.return_value = ["XYZ1", "XYZ2"]

        shape_codes = utils.availability.check_and_get_codes_with("all_data")

        assert shape_codes == ["XYZ1", "XYZ2"]


def test_check_and_get_codes_with_errors():
    """
    Test if the check_and_get_codes_with function handles errors.

    Invalid features, data sources and codes raise errors, and so does
    a file with none of the available codes.
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
        patch("utils.data_sources.read_all_codes") as mock_read_all_codes,
    ):
        mock_read_codes.return_value = ["USA_CAL", "USA_TEX"]
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        with pytest.raises(
            ValueError, match="None of the codes in the file are available"
        ):
            utils.availability.check_and_get_codes_with(
                "electricity_demand_data", file_path="dummy.yaml"
            )

    # Check if the function raises an error for invalid codes read from
    # a file, for the codes with all the data.
    with (
        patch("utils.data_sources.read_codes_in") as mock_read_codes,
        patch(
            "utils.availability.read_codes_with_all_data"
        ) as mock_read_all_codes,
    ):
        mock_read_codes.return_value = ["USA_CAL", "USA_TEX"]
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        with pytest.raises(
            ValueError, match="None of the codes in the file are available"
        ):
            utils.availability.check_and_get_codes_with(
                "all_data", file_path="dummy.yaml"
            )

    with patch("utils.data_sources.read_codes_in") as mock_read_codes:
        # Mock the return value of read_codes_in for two times, the
        # first time for electricity demand data, the second time
        # for the codes in the file.
        mock_read_codes.side_effect = [
            ["USA_CAL", "USA_TEX"],
            ["FRA", "DEU", "ITA"],
        ]

        with pytest.raises(
            ValueError, match="None of the codes in the file are available"
        ):
            utils.availability.check_and_get_codes_with(
                "electricity_demand_data",
                data_source="entsoe",
                file_path="dummy.yaml",
            )


def test_codes_with_historical_and_all_data(write_summary):
    """Test that the codes without projections have historical data."""
    columns = ["population", "electricity_demand_per_capita"]
    columns.append("gdp_ppp_per_capita")
    rows = {
        # All the data.
        "FRA": [True] * 6 + [False],
        # The historical data only, as Kosovo.
        "XKX": [True] * 3 + [False] * 3 + [False],
        # The electricity demand per capita of a large area.
        "USA_TX": [False, True, False, False, True, False, True],
        # No electricity demand per capita.
        "ABC": [True, False, True, True, False, True, True],
    }
    write_summary(
        pd.DataFrame.from_dict(
            rows,
            orient="index",
            columns=[f"historical_{column}" for column in columns]
            + [f"future_{column}" for column in columns]
            + ["area_greater_than_500_km2"],
        )
    )

    assert utils.availability.read_codes_with_all_data() == ["FRA", "USA_TX"]
    assert utils.availability.read_codes_with_historical_data() == [
        "FRA",
        "XKX",
        "USA_TX",
    ]
    assert utils.availability.check_and_get_codes_with(
        "historical_data", code="XKX"
    ) == ["XKX"]
    with pytest.raises(ValueError, match="is not associated with a data"):
        utils.availability.check_and_get_codes_with(
            "historical_data", data_source="entsoe"
        )


def test_flag_that_is_not_true_or_false(monkeypatch, tmp_path):
    """
    Test that a flag of the summary that is not True or False fails.

    An empty cell would otherwise be read as text, and any text counts
    as true.
    """
    (tmp_path / "data_availability_summary.csv").write_text(
        "entity_code,historical_population,"
        "historical_electricity_demand_per_capita,"
        "historical_gdp_ppp_per_capita,area_greater_than_500_km2\n"
        "XY1,True,True,True,True\n"
        "XY2,,True,True,True\n"
    )
    monkeypatch.setattr(utils.paths, "CHECKS_FOLDER", str(tmp_path))

    with pytest.raises(ValueError, match="historical_population"):
        utils.availability.read_codes_with_historical_data()
