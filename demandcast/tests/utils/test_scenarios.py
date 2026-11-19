"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the scenario module.
"""

import pandas as pd
import pytest

import utils.scenarios


def test_get_years():
    """
    Test the _get_years function with various input scenarios.

    The inputs are combinations of year, start_year and end_year.
    """
    available_years = [2018, 2019, 2020, 2021]

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

    Invalid combinations of year, start_year and end_year raise errors.
    """
    available_years = [2018, 2019, 2020, 2021]

    # Both year and start_year/end_year provided.
    with pytest.raises(
        ValueError, match="start_year and end_year must be None"
    ):
        utils.scenarios._get_years(2019, 2018, None, available_years)
    with pytest.raises(
        ValueError, match="start_year and end_year must be None"
    ):
        utils.scenarios._get_years(2019, None, 2020, available_years)

    # Year not in available years.
    with pytest.raises(
        ValueError, match="year must be one of the available years"
    ):
        utils.scenarios._get_years(2022, None, None, available_years)

    # start_year greater than end_year.
    with pytest.raises(
        ValueError, match="start_year must not be after end_year"
    ):
        utils.scenarios._get_years(None, 2020, 2019, available_years)

    # Only one of start_year or end_year provided.
    with pytest.raises(
        ValueError, match="Both start_year and end_year must be specified"
    ):
        utils.scenarios._get_years(None, 2018, None, available_years)
    with pytest.raises(
        ValueError, match="Both start_year and end_year must be specified"
    ):
        utils.scenarios._get_years(None, None, 2019, available_years)

    # start_year or end_year out of available years range. This only
    # raises a warning in the logger.
    utils.scenarios._get_years(None, 2017, 2019, available_years)
    utils.scenarios._get_years(None, 2018, 2022, available_years)


def test_get_year_model_and_scenario_combinations_without_models():
    """
    Test get_year_model_and_scenario_combinations without models.

    The inputs are combinations of year, start_year, end_year and
    scenario, with a list of scenarios and no climate models.
    """
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026]
    available_scenarios = ["S1", "S2"]

    assert utils.scenarios.get_year_model_and_scenario_combinations(
        2024,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        None,
        available_scenarios,
    ) == [(2024, None, None)]
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        None,
        2024,
        2025,
        available_historical_years,
        available_future_years,
        None,
        None,
        available_scenarios,
    ) == [
        (2024, None, None),
        (2025, None, None),
        (2025, None, "S1"),
        (2025, None, "S2"),
    ]
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        None,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        "S1",
        available_scenarios,
    ) == [
        (2024, None, None),
        (2025, None, None),
        (2025, None, "S1"),
        (2026, None, "S1"),
    ]
    assert utils.scenarios.get_year_model_and_scenario_combinations(
        None,
        None,
        None,
        available_historical_years,
        available_future_years,
        None,
        None,
        available_scenarios,
    ) == [
        (2024, None, None),
        (2025, None, None),
        (2025, None, "S1"),
        (2025, None, "S2"),
        (2026, None, "S1"),
        (2026, None, "S2"),
    ]


def test_get_year_model_and_scenario_combinations_without_models_errors():
    """
    Test get_year_model_and_scenario_combinations errors without models.

    A scenario that is not available, or a model given for data without
    climate models, raise errors.
    """
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026]
    available_scenarios = ["S1", "S2"]

    with pytest.raises(
        ValueError, match="scenario must be one of the following"
    ):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            None,
            None,
            available_historical_years,
            available_future_years,
            None,
            "S3",
            available_scenarios,
        )
    with pytest.raises(ValueError, match="model must be None"):
        utils.scenarios.get_year_model_and_scenario_combinations(
            None,
            None,
            None,
            available_historical_years,
            available_future_years,
            "M1",
            None,
            available_scenarios,
        )


def test_get_year_model_and_scenario_combinations():
    """
    Test the get_year_model_and_scenario_combinations function.

    The inputs are combinations of year, start_year, end_year, model
    and scenario.
    """
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026]
    scenarios_for_model = {"M1": ["S1", "S2"], "M2": ["S2"]}

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

    Invalid combinations of year, start_year, end_year, model and
    scenario raise errors.
    """
    available_historical_years = [2024, 2025]
    available_future_years = [2025, 2026, 2027]
    scenarios_for_model = {"M1": ["S1", "S2"], "M2": ["S2"]}

    # Both year and start_year/end_year provided.
    with pytest.raises(
        ValueError, match="start_year and end_year must be None"
    ):
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
    with pytest.raises(
        ValueError, match="start_year and end_year must be None"
    ):
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
    with pytest.raises(
        ValueError, match="year must be one of the available years"
    ):
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
    with pytest.raises(
        ValueError, match="start_year must not be after end_year"
    ):
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
    with pytest.raises(
        ValueError, match="Both start_year and end_year must be specified"
    ):
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
    with pytest.raises(
        ValueError, match="Both start_year and end_year must be specified"
    ):
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

    # start_year or end_year out of available years range. This only
    # raises a warning in the logger.
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
    with pytest.raises(ValueError, match="model must be one of the following"):
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
    with pytest.raises(
        ValueError, match="scenario must be one of the following for model"
    ):
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


def test_years_without_data_between_years_with_data(caplog):
    """
    Test that a year without data uses the year before it with data.

    The data of the country misses 2015, which is requested and uses
    2014, with a warning. A subdivision has the years of its country
    before its gridded data, also those without data, which use the
    first year of the gridded data.
    """
    data = pd.DataFrame(
        {2013: [1.0], 2014: [2.0], 2015: [None], 2016: [4.0], 2017: [5.0]},
        index=["AAA"],
    )

    requested, used, future, _ = utils.scenarios.get_years_and_scenarios(
        iso_alpha_3_code="AAA",
        year=None,
        start_year=2013,
        end_year=2017,
        scenario=None,
        available_scenarios=["SSP2"],
        global_historical_data=data,
        available_historical_years_of_gridded_data=[2016, 2017],
    )

    assert requested == [2013, 2014, 2015, 2016, 2017]
    assert used == [2013, 2014, 2014, 2016, 2017]
    assert future == []
    assert "AAA has no value in [2015]" in caplog.text

    requested, used, _, _ = utils.scenarios.get_years_and_scenarios(
        iso_alpha_3_code="AAA_BB",
        year=None,
        start_year=2013,
        end_year=2017,
        scenario=None,
        available_scenarios=["SSP2"],
        global_historical_data=data,
        available_historical_years_of_gridded_data=[2016, 2017],
    )

    assert requested == [2013, 2014, 2015, 2016, 2017]
    assert used == [2016, 2016, 2016, 2016, 2017]


def test_get_years_and_scenarios():
    """
    Test the get_years_and_scenarios function.

    The requested and used historical years, the future years and the
    scenarios depend on the requested years and on the years of the
    historical data.
    """
    data = pd.DataFrame(
        {
            2020: [1],
            2021: [2],
            2022: [3],
            2023: [4],
            2024: [5],
        },
        index=["AAA"],
    )

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
    data = pd.DataFrame(
        {
            2020: [1],
            2021: [2],
            2022: [3],
            2023: [4],
        },
        index=["AAA"],
    )

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

    data = pd.DataFrame(
        {
            2020: [1],
            2021: [2],
            2022: [3],
            2023: [4],
            2024: [5],
        },
        index=["AAA"],
    )

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

    # Define a simple DataFrame to simulate historical data up to the
    # current year - 1.
    data = pd.DataFrame()
    for year in range(2021, pd.Timestamp.now().year):
        data[year] = [year - 2000]
    data.index = ["AAA"]

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


def test_years_of_a_subdivision_before_the_gridded_data():
    """
    Test that a subdivision has the years of its country before them.

    The years before the gridded data use its first year, and the
    country has no year before 1998.
    """
    national = pd.DataFrame(
        {year: [1.0] for year in range(1998, 2024)}, index=["CAN"]
    )

    requested, used, _, _ = utils.scenarios.get_years_and_scenarios(
        "CAN_ON", None, 1995, 2002, None, [], national, [2000, 2005, 2010]
    )

    assert requested == list(range(1998, 2003))
    assert used == [2000, 2000, 2000, 2001, 2002]

    # A subdivision of a country without data has the gridded years.
    requested, used, _, _ = utils.scenarios.get_years_and_scenarios(
        "XYZ_A", None, 1995, 2002, None, [], national, [2000, 2005, 2010]
    )
    assert requested == [2000, 2001, 2002]
