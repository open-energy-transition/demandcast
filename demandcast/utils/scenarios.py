# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides utility functions for the data retrieval for
    different future scenarios.
"""

import pandas


def _normalize_scenarios(scenarios: list[str]) -> list[str]:
    """
    Normalize scenario names to uppercase.

    Parameters
    ----------
    scenarios : list[str]
        A list of scenario names.

    Returns
    -------
    list[str]
        A list of normalized scenario names in uppercase.
    """
    return [s.upper() for s in scenarios]


def _normalize_scenarios_for_model(
    scenarios_for_model: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Normalize model and scenario names to uppercase.

    Parameters
    ----------
    scenarios_for_model : dict[str, list[str]]
        A dictionary of scenarios for each climate model.

    Returns
    -------
    dict[str, list[str]]
        A dictionary of normalized model and scenario names in
        uppercase.
    """
    return {
        model.upper(): _normalize_scenarios(scenarios)
        for model, scenarios in scenarios_for_model.items()
    }


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


def _get_scenarios(
    scenario: str | None,
    available_scenarios: list[str],
) -> list[str]:
    """
    Get the list of scenarios based on the input parameters.

    Parameters
    ----------
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios : list[str]
        The list of available scenarios for the data retrieval.

    Returns
    -------
    scenarios : list[str]
        A list of scenarios for which the data is to be downloaded.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Normalize the scenario names to uppercase.
    available_scenarios = _normalize_scenarios(available_scenarios)

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

    return scenarios


def _get_scenarios_for_model(
    model: str | None,
    scenario: str | None,
    available_scenarios_for_model: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Get the list of scenarios for the specified model.

    Parameters
    ----------
    model : str | None
        The specific climate model for which the data is to be
        downloaded.
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios_for_model : dict[str, list[str]]
        The dictionary of available scenarios for each climate model.

    Returns
    -------
    scenarios_for_model : dict[str, list[str]]
        A dictionary of selected scenarios for each climate model.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Normalize the model and scenario names to uppercase.
    scenarios_for_model = _normalize_scenarios_for_model(
        available_scenarios_for_model
    )

    if model is not None:
        if model.upper() not in scenarios_for_model.keys():
            raise ValueError(
                "model must be one of the following: "
                f"{list(scenarios_for_model.keys())}."
            )
        # Use the specified model.
        scenarios_for_model = {
            model.upper(): scenarios_for_model[model.upper()]
        }

    if scenario is not None:
        for model_key, available_scenarios in scenarios_for_model.items():
            if scenario.upper() not in available_scenarios:
                raise ValueError(
                    "scenario must be one of the following for model "
                    f"{model_key}: {scenarios_for_model[model_key]}."
                )
            # Use the specified scenario.
            scenarios_for_model[model_key] = [scenario.upper()]

    return scenarios_for_model


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
    """
    # Get the list of available years sorted without duplicates.
    available_years = sorted(
        list(set(available_historical_years + available_future_years))
    )

    # Get the list of years and scenarios based on the input parameters.
    years = _get_years(year, start_year, end_year, available_years)
    scenarios = _get_scenarios(scenario, available_scenarios)

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
    """
    # Get the list of available years sorted without duplicates.
    available_years = sorted(
        list(set(available_historical_years + available_future_years))
    )

    # Get the list of years and scenarios based on the input parameters.
    years = _get_years(year, start_year, end_year, available_years)
    scenarios_for_model = _get_scenarios_for_model(
        model,
        scenario,
        available_scenarios_for_model,
    )

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
            ) in scenarios_for_model.items():
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
            ) in scenarios_for_model.items():
                for scenario_key in scenario_keys:
                    year_model_scenario_list.append(
                        (year, model_key, scenario_key)
                    )

    return year_model_scenario_list


def _extend_historical_years(available_years: list[int]) -> list[int]:
    """
    Extend historical years up to last year if needed.

    This is useful when the most recent historical year is earlier
    than last year, and we want to fill in the missing years up to
    last year. For example, if the most recent historical year is 2021
    and the current year is 2024, this function will add 2022 and
    2023 to the list of available years.

    Parameters
    ----------
    available_years : list[int]
        The list of available years.

    Returns
    -------
    list[int]
        The extended list of available years.
    """
    # Get the current year and the last historical year.
    current_year = pandas.Timestamp.now().year
    last_historical_year = available_years[-1]

    # If the last historical year is already last year or later,
    # return the available years as is.
    if last_historical_year >= current_year - 1:
        return available_years

    # Add years from last available to last year if needed.
    missing_years = list(range(last_historical_year + 1, current_year))
    return available_years + missing_years


def get_years_and_scenarios(
    iso_alpha_3_code: str,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
    available_scenarios: list[str],
    global_historical_data,
    available_historical_years_of_gridded_data: list[int],
) -> tuple[list[int], list[int], list[int], list[str]]:
    """
    Get the years and scenarios dictionary for a specific country.

    The function determines the requested historical years, used
    historical years, future years, and scenarios based on the input
    parameters and the available data. There may be differences between
    the requested historical years and the used historical years if, for
    example, the requested years for a country are between 2020 and 2024,
    but the available historical data for that country is only up to
    2023. In this case, the used historical years will be 2020 to 2023,
    and 2023 will be used for 2024.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.
    year : int | None
        The specific year for which the data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which the data is to be
        downloaded.
    end_year : int | None
        The end year of the range of years for which the data is to be
        downloaded.
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios : list[str]
        The list of available scenarios for the data retrieval.
    global_historical_gdp_ppp_per_capita : pd.DataFrame
        The global historical GDP PPP per capita data.
    available_historical_years_of_gridded_data : list[int]
        The list of available historical years for the gridded data.

    Returns
    -------
    tuple[list[int], list[int], list[int], list[str]]
        A tuple containing:
        - requested_historical_years: list[int]
            The list of requested historical years.
        - used_historical_years: list[int]
            The list of used historical years (after interpolation if
            needed).
        - future_years: list[int]
            The list of future years.
        - scenarios: list[str]
            The list of scenarios.
    """
    # Check if the ISO Alpha-3 code is in the historical data.
    if iso_alpha_3_code in global_historical_data.index:
        # Extract the historical data for the country.
        national_historical_data = (
            global_historical_data.loc[iso_alpha_3_code]
        ).dropna()

        # Get the years of available historical data.
        available_historical_years = national_historical_data.index.tolist()
    else:
        # Define the available years for historical data when
        # interpolating from gridded data.
        available_historical_years = list(
            range(
                available_historical_years_of_gridded_data[0],
                available_historical_years_of_gridded_data[-1] + 1,
            )
        )

    # Get the years of available historical data, extended if needed,
    # and the years of available future data.
    extended_available_historical_years = _extend_historical_years(
        available_historical_years
    )
    available_future_years = list(
        range(max(extended_available_historical_years) + 1, 2101)
    )

    # Get the list of available years sorted without duplicates.
    available_years = sorted(
        list(set(extended_available_historical_years + available_future_years))
    )

    # Get the list of requested years.
    all_requested_years = _get_years(
        year,
        start_year,
        end_year,
        available_years,
    )

    # Get the list of requested and used historical years.
    requested_historical_years = [
        y
        for y in all_requested_years
        if y in extended_available_historical_years
    ]
    used_historical_years = [
        y
        if y in available_historical_years
        else available_historical_years[-1]
        for y in requested_historical_years
    ]

    # Get the list of future years.
    future_years = [
        y for y in all_requested_years if y in available_future_years
    ]

    # Get scenarios for future data.
    scenarios = (
        _get_scenarios(scenario, available_scenarios) if future_years else []
    )

    return (
        requested_historical_years,
        used_historical_years,
        future_years,
        scenarios,
    )
