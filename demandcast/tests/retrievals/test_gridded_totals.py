"""
License: AGPL-3.0.

Description:

    Tests for the totals of the gridded population and GDP PPP of a
    country or subdivision, with the gridded data mocked.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import retrievals.gridded_totals


def test_aggregate_gridded_data():
    """
    Test that missing gridded data is retrieved and summed.

    The grid of the year and scenario is retrieved when its file is
    missing, and its cells are summed within the shape of the code.
    """
    retrieval = MagicMock()
    with (
        patch.dict(retrievals.gridded_totals.RETRIEVALS, population=retrieval),
        patch("os.path.exists", return_value=False),
        patch("xarray.open_dataarray"),
        patch("utils.shapes.get_entity_shape"),
        patch(
            "utils.geospatial.get_total_in_shape", return_value=12345.6
        ) as get_total_in_shape,
    ):
        result = retrievals.gridded_totals._aggregate_gridded_data(
            "population", "XYZ", 2020, "SSP2"
        )

    assert result == 12345.6
    assert retrieval.run_data_retrieval.call_args.kwargs == {
        "code": "XYZ",
        "file": None,
        "year": 2020,
        "start_year": None,
        "end_year": None,
        "scenario": "SSP2",
    }
    assert get_total_in_shape.call_count == 1


def test_selected_years():
    """
    Test the selection of years for gridded data.

    This function tests the _select_years_of_gridded_data utility
    function to ensure it correctly selects the available years that
    match the requested years.
    """
    # Define available years and selected years for testing.
    available_years = [2000, 2005, 2010, 2015]
    selected_years = [2007, 2008]

    # Define the expected output.
    expected_years = [2005, 2010]

    # Call the function to test.
    result = retrievals.gridded_totals._select_years_of_gridded_data(
        available_years, selected_years
    )

    # Assert that the returned years match the expected years.
    assert result == expected_years


def test_get_total_value_from_gridded_data():
    """
    Test the aggregation to total value from gridded data.

    This function tests the get_total_value_from_gridded_data utility
    function to ensure it correctly aggregates values from a gridded
    dataset within a specified shape and time frame. It also checks that
    the function reteruns the years needed to cover the selected
    years. Lastly, it verifies that the values are linearly interpolated
    between the available years.
    """
    # Define test parameters.
    variable = "population"
    code = "XYZ"
    available_years = [2035, 2040, 2045, 2050]
    extra_available_years = 2030
    selected_years = [2037, 2038]
    scenario = "SSP2"

    with (
        patch(
            "retrievals.gridded_totals._aggregate_gridded_data"
        ) as mock_aggregate,
    ):
        # Mock the aggregation function to return a series of values.
        mock_aggregate.side_effect = [10000.0, 12000.0]

        # Call the function to test.
        result = retrievals.gridded_totals.get_total_value_from_gridded_data(
            variable,
            code,
            selected_years,
            available_years,
            last_available_historical_years_of_gridded_data=extra_available_years,
            scenario=scenario,
        )

    # Assert that the returned Series has the correct index and values.
    assert isinstance(result, pd.Series)
    assert list(result.index) == [2035, 2036, 2037, 2038, 2039, 2040]
    assert np.allclose(result.to_numpy(), np.linspace(10000, 12000, 6))

    # Repeat the test with the GDP PPP variable and other selected
    # years.
    variable = "gdp_ppp"
    selected_years = [2033, 2034]

    with (
        patch(
            "retrievals.gridded_totals._aggregate_gridded_data"
        ) as mock_aggregate,
    ):
        # Mock the aggregation function to return a series of values.
        mock_aggregate.side_effect = [50000.0, 70000.0]

        # Call the function to test.
        result = retrievals.gridded_totals.get_total_value_from_gridded_data(
            variable,
            code,
            selected_years,
            available_years,
            last_available_historical_years_of_gridded_data=extra_available_years,
            scenario=scenario,
        )


def test_get_total_value_from_gridded_data_errors():
    """
    Test error handling in get_total_value_from_gridded_data.

    This function tests the error handling of the
    get_total_value_from_gridded_data utility function to ensure it
    raises appropriate exceptions when given invalid input parameters.
    """
    variable = "population"
    code = "XYZ"
    available_years = [2000, 2005, 2010, 2015]
    selected_years = [2006, 2007]
    scenario = "SSP2"

    # Test for ValueError when an unsupported variable is provided.
    with pytest.raises(
        ValueError, match="must be either 'population' or 'gdp_ppp'"
    ):
        retrievals.gridded_totals.get_total_value_from_gridded_data(
            "variable_not_supported",
            code,
            selected_years,
            available_years,
        )

    # Test for ValueError when scenario is provided but not the last
    # available historical year.
    with pytest.raises(ValueError, match="If scenario is provided"):
        retrievals.gridded_totals.get_total_value_from_gridded_data(
            variable,
            code,
            selected_years,
            available_years,
            last_available_historical_years_of_gridded_data=None,
            scenario=scenario,
        )

    # Test for ValueError when the last available historical year is
    # provided but not the scenario.
    with pytest.raises(ValueError, match="scenario must also be provided"):
        retrievals.gridded_totals.get_total_value_from_gridded_data(
            variable,
            code,
            selected_years,
            available_years,
            last_available_historical_years_of_gridded_data=1995,
            scenario=None,
        )

    # Test for ValueError when the last available historical year is
    # greater or equal to the minimum available year.
    with pytest.raises(
        ValueError, match="must be less than the minimum available"
    ):
        retrievals.gridded_totals.get_total_value_from_gridded_data(
            variable,
            code,
            selected_years,
            available_years,
            last_available_historical_years_of_gridded_data=2020,
            scenario=scenario,
        )
