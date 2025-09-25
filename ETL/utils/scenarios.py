# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module povides utility functions for the data retrieval for
    different future scenarios.
"""


def _get_years(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    available_years: list[int],
) -> list[int]:
    """
    Get the list of years based on the input parameters.

    Parameters
    ----------
    year : int | None
        The specific year for which the data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which the data is to be
        downloaded.
    end_year : int | None
        The end year of the range of years for which the data is to be
        downloaded.
    available_years : list[int]
        The list of available years for the data retrieval.

    Returns
    -------
    years : list[int]
        A list of years for which the data is to be downloaded.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    if year is not None:
        if start_year is not None or end_year is not None:
            raise ValueError(
                "If year is specified, start_year and end_year must be None."
            )
        if year not in available_years:
            raise ValueError(
                f"year must be one of the available years: {available_years}."
            )
        # Use the specified year.
        years = [year]
    elif start_year is not None and end_year is not None:
        if start_year > end_year:
            raise ValueError("start_year must be less than end_year.")
        if start_year not in available_years:
            raise ValueError(
                "start_year must be one of the available years: "
                f"{available_years}."
            )
        if end_year not in available_years:
            raise ValueError(
                "end_year must be one of the available years: "
                f"{available_years}."
            )
        # Use the range of years from start_year to end_year.
        years = [y for y in available_years if start_year <= y <= end_year]
    elif (start_year is not None and end_year is None) or (
        start_year is None and end_year is not None
    ):
        raise ValueError("Both start_year and end_year must be specified.")
    else:
        # Use all available years.
        years = available_years

    return years


def get_year_and_scenario_combinations(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    available_historical_years: list[int],
    available_future_years: list[int],
    scenario: str | None,
    available_scenarios: list[str],
) -> list[tuple[int, str | None]]:
    """
    Get the list of years and scenario combinations.

    Parameters
    ----------
    year : int | None
        The specific year for which the data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which the data is to be
        downloaded.
    end_year : int | None
        The end year of the range of years for which the data is to be
        downloaded.
    available_historical_years : list[int]
        The list of available historical years for the data retrieval.
    available_future_years : list[int]
        The list of available future years for the data retrieval.
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios : list[str]
        The list of available scenarios for the data retrieval.

    Returns
    -------
    year_scenario_list : list[tuple[int, str | None]]
        A list of tuples, where each tuple contains a year and an
        optional scenario.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Get the list of available years sorted without duplicates.
    available_years = sorted(
        list(set(available_historical_years + available_future_years))
    )

    # Get the list of years based on the input parameters.
    years = _get_years(year, start_year, end_year, available_years)

    # Normalize the scenario names to uppercase.
    available_scenarios = [
        scenario_key.upper() for scenario_key in available_scenarios
    ]

    if scenario is not None:
        if scenario.upper() not in available_scenarios:
            raise ValueError(
                "scenario must be one of the following: "
                f"{available_scenarios}."
            )
        # Use the specified scenario.
        scenarios = [scenario.upper()]
    else:
        # Use all available scenarios.
        scenarios = available_scenarios

    # Create a list of year and scenario combinations.
    year_scenario_list: list[tuple[int, str | None]] = []
    for year in years:
        if (
            year in available_historical_years
            and year in available_future_years
        ):
            # If the year is both historical and future, include both
            # options.
            year_scenario_list.append((year, None))
            for scenario in scenarios:
                year_scenario_list.append((year, scenario))
        elif year in available_historical_years:
            year_scenario_list.append((year, None))
        elif year in available_future_years:
            for scenario in scenarios:
                year_scenario_list.append((year, scenario))

    return year_scenario_list


def get_year_model_and_scenario_combinations(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    available_historical_years: list[int],
    available_future_years: list[int],
    model: str | None,
    scenario: str | None,
    available_scenarios_for_model: dict[str, list[str]],
) -> list[tuple[int, str | None, str | None]]:
    """
    Get the list of years, model, and scenario combinations.

    Parameters
    ----------
    year : int | None
        The specific year for which the data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which the data is to be
        downloaded.
    end_year : int | None
        The end year of the range of years for which the data is to be
        downloaded.
    last_year_of_historical_data : int
        The last year for which historical data is available.
    available_years : list[int]
        The list of available years for the data retrieval.
    model : str | None
        The specific cliamte model for which the data is to be
        downloaded.
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios : list[str]
        The list of available scenarios for the data retrieval.

    Returns
    -------
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        A list of tuples, where each tuple contains a year, an optional
        climate model, and an optional scenario.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Get the list of available years sorted without duplicates.
    available_years = sorted(
        list(set(available_historical_years + available_future_years))
    )

    # Get the list of years based on the input parameters.
    years = _get_years(year, start_year, end_year, available_years)

    # Normalize the model and scenario names to uppercase.
    available_scenarios_for_model = {
        model_key.upper(): [
            scenario_key.upper() for scenario_key in scenario_keys
        ]
        for model_key, scenario_keys in available_scenarios_for_model.items()
    }

    # Initialize the selected scenarios for the model.
    selected_scenarios_for_model = available_scenarios_for_model.copy()

    if model is not None:
        if model.upper() not in available_scenarios_for_model.keys():
            raise ValueError(
                "model must be one of the following: "
                f"{list(available_scenarios_for_model.keys())}."
            )
        # Use the specified model.
        selected_scenarios_for_model = {
            model.upper(): available_scenarios_for_model[model.upper()]
        }

    if scenario is not None:
        for model_key in selected_scenarios_for_model.keys():
            if scenario.upper() not in selected_scenarios_for_model[model_key]:
                raise ValueError(
                    "scenario must be one of the following for model "
                    f"{model_key}: {selected_scenarios_for_model[model_key]}."
                )
            # Use the specified scenario.
            selected_scenarios_for_model[model_key] = [scenario.upper()]

    # Create a list of year, model, and scenario combinations.
    year_model_scenario_list: list[tuple[int, str | None, str | None]] = []
    for year in years:
        if (
            year in available_historical_years
            and year in available_future_years
        ):
            # If the year is both historical and future, include both
            # options.
            year_model_scenario_list.append((year, None, None))
            for (
                model_key,
                scenario_keys,
            ) in selected_scenarios_for_model.items():
                for scenario_key in scenario_keys:
                    year_model_scenario_list.append(
                        (year, model_key, scenario_key)
                    )
        elif year in available_historical_years:
            year_model_scenario_list.append((year, None, None))
        elif year in available_future_years:
            for (
                model_key,
                scenario_keys,
            ) in selected_scenarios_for_model.items():
                for scenario_key in scenario_keys:
                    year_model_scenario_list.append(
                        (year, model_key, scenario_key)
                    )

    return year_model_scenario_list
