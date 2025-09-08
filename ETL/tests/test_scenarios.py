# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the scenario module in the ETL
    utility package.
"""

from unittest.mock import mock_open, patch

import pandas
import pytest
import utils.scenarios


def test_get_years():
    """
    Test the _get_years function with various input scenarios.

    This test checks the correct years are returned based on
    different combinations of year, start_year, and end_year inputs.
    """
    # Define available years for testing.
    available_years = [2018, 2019, 2020, 2021]

    # Test various scenarios.
    assert utils.scenarios._get_years(2019, None, None, available_years) == [
        2019
    ]
    assert utils.scenarios._get_years(None, 2019, 2020, available_years) == [
        2019,
        2020,
    ]
    assert (
        utils.scenarios._get_years(None, None, None, available_years)
        == available_years
    )


def test_get_years_errors():
    """
    Test the _get_years function for error handling with invalid inputs.

    This test checks that appropriate exceptions are raised for
    invalid combinations of year, start_year, and end_year inputs.
    """
    # Define available years for testing.
    available_years = [2018, 2019, 2020, 2021]

    # Both year and start_year/end_year provided.
    with pytest.raises(ValueError):
        utils.scenarios._get_years(2019, 2018, None, available_years)
    with pytest.raises(ValueError):
        utils.scenarios._get_years(2019, None, 2020, available_years)

    # Year not in available years.
    with pytest.raises(ValueError):
        utils.scenarios._get_years(2022, None, None, available_years)

    # start_year greater than end_year.
    with pytest.raises(ValueError):
        utils.scenarios._get_years(None, 2020, 2019, available_years)

    # Only one of start_year or end_year provided.
    with pytest.raises(ValueError):
        utils.scenarios._get_years(None, 2018, None, available_years)
    with pytest.raises(ValueError):
        utils.scenarios._get_years(None, None, 2019, available_years)

    # start_year or end_year out of available years range.
    with pytest.raises(ValueError):
        utils.scenarios._get_years(None, 2017, 2019, available_years)
    with pytest.raises(ValueError):
        utils.scenarios._get_years(None, 2018, 2022, available_years)


def test_get_year_and_scenario_combinations():
    """
    Test the get_year_and_scenario_combinations function.

    This test checks the correct (year, scenario) combinations are
    returned based on different combinations of year, start_year,
    end_year, and scenario inputs.
    """
    # Define available years and scenarios for testing.
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026]
    available_scenarios = ["S1", "S2"]

    # Test various input combinations.
    assert utils.scenarios.get_year_and_scenario_combinations(
        2024,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        available_scenarios,
    ) == [(2024, None)]
    assert utils.scenarios.get_year_and_scenario_combinations(
        None,
        2024,
        2025,
        available_historical_years,
        available_future_years,
        None,
        available_scenarios,
    ) == [(2024, None), (2025, None), (2025, "S1"), (2025, "S2")]
    assert utils.scenarios.get_year_and_scenario_combinations(
        None,
        None,
        None,
        available_historical_years,
        available_future_years,
        "S1",
        available_scenarios,
    ) == [(2024, None), (2025, None), (2025, "S1"), (2026, "S1")]
    assert utils.scenarios.get_year_and_scenario_combinations(
        None,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        available_scenarios,
    ) == [
        (2024, None),
        (2025, None),
        (2025, "S1"),
        (2025, "S2"),
        (2026, "S1"),
        (2026, "S2"),
    ]


def test_get_year_and_scenario_combinations_errors():
    """
    Test the get_year_and_scenario_combinations function for errors.

    This test checks that appropriate exceptions are raised for
    invalid combinations of year, start_year, end_year, and scenario
    inputs.
    """
    # Define available years and scenarios for testing.
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026]
    available_scenarios = ["S1", "S2"]

    # Both year and start_year/end_year provided.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            2025,
            2024,
            None,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            2025,
            None,
            2026,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )

    # Year not in available years.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            2023,
            None,
            None,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )

    # start_year greater than end_year.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            None,
            2025,
            2024,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )

    # Only one of start_year or end_year provided.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            None,
            2024,
            None,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            None,
            None,
            2025,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )

    # start_year or end_year out of available years range.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            None,
            2023,
            2025,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            None,
            2024,
            2027,
            available_historical_years,
            available_future_years,
            None,
            available_scenarios,
        )

    # Scenario not in available scenarios.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_and_scenario_combinations(
            None,
            None,
            None,
            available_historical_years,
            available_future_years,
            "S3",
            available_scenarios,
        )


def test_get_year_model_and_scenario_combinations():
    """
    Test the get_year_model_and_scenario_combinations function.

    This test checks the correct (year, model, scenario) combinations
    are returned based on different combinations of year, start_year,
    end_year, model, and scenario inputs.
    """
    # Define available years, models, and scenarios for testing.
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026]
    scenarios_for_model = {"M1": ["S1", "S2"], "M2": ["S2"]}

    # Test various input combinations.
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        2024,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        None,
        scenarios_for_model,
    ) == [(2024, None, None)]
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        None,
        2024,
        2025,
        available_historical_years,
        available_future_years,
        None,
        None,
        scenarios_for_model,
    ) == [
        (2024, None, None),
        (2025, None, None),
        (2025, "M1", "S1"),
        (2025, "M1", "S2"),
        (2025, "M2", "S2"),
    ]
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        None,
        None,
        None,
        available_historical_years,
        available_future_years,
        "M1",
        "S1",
        scenarios_for_model,
    ) == [
        (2024, None, None),
        (2025, None, None),
        (2025, "M1", "S1"),
        (2026, "M1", "S1"),
    ]
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        None,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        None,
        scenarios_for_model,
    ) == [
        (2024, None, None),
        (2025, None, None),
        (2025, "M1", "S1"),
        (2025, "M1", "S2"),
        (2025, "M2", "S2"),
        (2026, "M1", "S1"),
        (2026, "M1", "S2"),
        (2026, "M2", "S2"),
    ]


def test_get_year_model_and_scenario_combinations_errors():
    """
    Test get_year_model_and_scenario_combinations function for errors.

    This test checks that appropriate exceptions are raised for
    invalid combinations of year, start_year, end_year, model,
    and scenario inputs.
    """
    # Define available years, models, and scenarios for testing.
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026, 2027]
    scenarios_for_model = {"M1": ["S1", "S2"], "M2": ["S2"]}

    # Both year and start_year/end_year provided.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            2025,
            2024,
            None,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            2025,
            None,
            2026,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )

    # Year not in available years.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            2023,
            None,
            None,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )

    # start_year greater than end_year.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            2025,
            2024,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )

    # Only one of start_year or end_year provided.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            2024,
            None,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            None,
            2025,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )

    # start_year or end_year out of available years range.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            2023,
            2025,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            2024,
            2028,
            available_historical_years,
            available_future_years,
            None,
            None,
            scenarios_for_model,
        )

    # Model or scenario not in available models/scenarios.
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            None,
            None,
            available_historical_years,
            available_future_years,
            "M3",
            None,
            scenarios_for_model,
        )
    with pytest.raises(ValueError):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            None,
            None,
            available_historical_years,
            available_future_years,
            "M1",
            "S3",
            scenarios_for_model,
        )


def test_get_iam_region():
    """
    Test the get_iam_region function.

    This test checks that the correct IAM region is returned for
    valid country codes and that a ValueError is raised for invalid
    country codes.
    """
    # Define a sample yaml file content.
    sample_yaml = """
    CHN: R5.2ASIA
    USA: R5.2OECD
    """

    # Mock the open function to return the sample yaml content.
    with patch("builtins.open", mock_open(read_data=sample_yaml)):
        # Test valid country codes.
        assert utils.scenarios.get_iam_region("CHN") == "R5.2ASIA"
        assert utils.scenarios.get_iam_region("USA") == "R5.2OECD"

        # Test invalid country code.
        with pytest.raises(ValueError):
            utils.scenarios.get_iam_region("IND")


def test_calculate_values_from_growth_rate():
    """
    Test the calculate_values_from_growth_rate function.

    This test checks that the function correctly calculates future
    values based on a given last value and a series of growth rates
    for specified future years.
    """
    # Define test inputs.
    last_value = 100.0  # Value for the year 2020
    future_years = [2021, 2022, 2023]
    growth_rates = pandas.Series([5.0, 10.0], index=[2020, 2022])

    # Define the expected output calculated manually.
    expected_values = pandas.Series(
        [
            last_value * (1 + 5.0 / 100),  # 2021
            last_value * (1 + 5.0 / 100) ** 2,  # 2022
            last_value * (1 + 5.0 / 100) ** 2 * (1 + 10.0 / 100),  # 2023
        ],
        index=future_years,
    )

    # Call the function to test.
    calculated_values = utils.scenarios.calculate_values_from_growth_rate(
        last_value, future_years, growth_rates
    )

    # Assert that the calculated values match the expected values.
    pandas.testing.assert_series_equal(calculated_values, expected_values)
