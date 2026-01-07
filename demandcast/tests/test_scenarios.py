# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the scenario module in the ETL
    utility package.
"""

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


def test_get_years_and_scenarios():
    """
    Test the get_years_and_scenarios function.

    This test checks the correct historical years, used historical
    years, future years, and scenarios are returned based on
    different combinations of year, start_year, end_year, and
    scenario inputs, along with historical data availability.
    """
    # Define a simple DataFrame to simulate historical data.
    data = pandas.DataFrame(
        {
            2020: [1],
            2021: [2],
            2022: [3],
            2023: [4],
            2024: [5],
        },
        index=["AAA"],
    ).T
    data.index.name = "Year"
    data = data.transpose()

    # Get years and scenarios.
    result = utils.scenarios.get_years_and_scenarios(
        iso_alpha_3_code="AAA",
        year=None,
        start_year=2021,
        end_year=2022,
        scenario=None,
        available_scenarios=["rcp45", "rcp85"],
        global_historical_data=data,
        available_historical_years_of_gridded_data=[2020, 2023],
    )

    assert result[0] == [2021, 2022]  # requested historical years
    assert result[1] == [2021, 2022]  # used historical years
    assert result[2] == []  # future years
    assert result[3] == []  # scenarios

    # Define another DataFrame to simulate historical data with missing
    # years.
    data = pandas.DataFrame(
        {
            2020: [1],
            2021: [2],
            2022: [3],
            2023: [4],
        },
        index=["AAA"],
    ).T
    data.index.name = "Year"
    data = data.transpose()

    # Get years and scenarios with missing historical years.
    result = utils.scenarios.get_years_and_scenarios(
        iso_alpha_3_code="AAA",
        year=None,
        start_year=2022,
        end_year=2024,
        scenario=None,
        available_scenarios=["rcp45", "rcp85"],
        global_historical_data=data,
        available_historical_years_of_gridded_data=[2020, 2023],
    )

    assert result[0] == [2022, 2023, 2024]  # requested historical years
    assert result[1] == [2022, 2023, 2023]  # used historical years
    assert result[2] == []  # future years
    assert result[3] == []  # scenarios

    # Define a DataFrame to simulate the use of gridded data.
    data = pandas.DataFrame(
        {
            2020: [1],
            2021: [2],
            2022: [3],
            2023: [4],
            2024: [5],
        },
        index=["AAA"],
    ).T
    data.index.name = "Year"
    data = data.transpose()

    # Get years and scenarios using gridded data.
    result = utils.scenarios.get_years_and_scenarios(
        iso_alpha_3_code="BBB",
        year=None,
        start_year=2021,
        end_year=2024,
        scenario=None,
        available_scenarios=["rcp45", "rcp85"],
        global_historical_data=data,
        available_historical_years_of_gridded_data=[2020, 2023],
    )

    assert result[0] == [2021, 2022, 2023, 2024]  # requested historical years
    assert result[1] == [2021, 2022, 2023, 2023]  # used historical years
    assert result[2] == []  # future years
    assert result[3] == []  # scenarios
