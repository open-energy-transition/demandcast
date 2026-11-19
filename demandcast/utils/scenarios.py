"""
License: AGPL-3.0.

Description:

    This module selects the years, scenarios and climate models of the
    data that a retrieval script downloads, from its settings and the
    years and scenarios that are available.
"""

import logging

import pandas as pd

import utils.catalogue


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
    Get the years of the data to download.

    The years are the given year, or the available years from the
    start year to the end year, both included, or all the available
    years if no year is given.

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
        If the year is given with a start or end year, if the year is
        not available, if only one of the start and end years is given,
        or if the start year is after the end year.

    Notes
    -----
    A start or end year that is not available only gives a warning:
    the range keeps the available years within it.
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
        years = [year]
    elif start_year is not None and end_year is not None:
        if start_year > end_year:
            raise ValueError("start_year must be less than end_year.")
        if start_year not in available_years:
            logging.warning(
                "start_year is less than the earliest available year, "
                f"which is {available_years[0]}."
            )
        if end_year not in available_years:
            logging.warning(
                "end_year is greater than the latest available year, "
                f"which is {available_years[-1]}."
            )
        years = [y for y in available_years if start_year <= y <= end_year]
    elif (start_year is not None and end_year is None) or (
        start_year is None and end_year is not None
    ):
        raise ValueError("Both start_year and end_year must be specified.")
    else:
        years = available_years

    return years


def _get_scenarios(
    scenario: str | None,
    available_scenarios: list[str],
) -> list[str]:
    """
    Get the scenarios of the data to download.

    The scenarios are the given one, or all the available ones, in
    uppercase.

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
        If the scenario is not available.
    """
    available_scenarios = _normalize_scenarios(available_scenarios)

    if scenario is not None:
        if scenario.upper() not in available_scenarios:
            raise ValueError(
                "scenario must be one of the following: "
                f"{available_scenarios}."
            )
        scenarios = [scenario.upper()]
    else:
        scenarios = available_scenarios

    return scenarios


def _get_scenarios_for_model(
    model: str | None,
    scenario: str | None,
    available_scenarios_for_model: dict[str, list[str]],
) -> dict[str, list[str]]:
    """
    Get the scenarios of each climate model of the data to download.

    The models are the given one, or all the available ones, each with
    the given scenario, or all its available ones, in uppercase.

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
        If the model is not available, or the scenario is not available
        for one of the selected models.
    """
    scenarios_for_model = _normalize_scenarios_for_model(
        available_scenarios_for_model
    )

    if model is not None:
        if model.upper() not in scenarios_for_model:
            raise ValueError(
                "model must be one of the following: "
                f"{list(scenarios_for_model.keys())}."
            )
        scenarios_for_model = {
            model.upper(): scenarios_for_model[model.upper()]
        }

    if scenario is not None:
        for model_key, available_scenarios in scenarios_for_model.items():
            if scenario.upper() not in available_scenarios:
                raise ValueError(
                    "scenario must be one of the following for model "
                    f"{model_key}: {available_scenarios}."
                )
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

    A historical year has no scenario, and a future year comes with
    each scenario. A year that is both comes once without a scenario
    and once with each scenario.

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
    available_years = sorted(
        set(available_historical_years + available_future_years)
    )

    years = _get_years(year, start_year, end_year, available_years)
    scenarios = _get_scenarios(scenario, available_scenarios)

    year_scenario_list: list[tuple[int, str | None]] = []
    for selected_year in years:
        if (
            selected_year in available_historical_years
            and selected_year in available_future_years
        ):
            year_scenario_list.append((selected_year, None))
            year_scenario_list.extend(
                (selected_year, scenario) for scenario in scenarios
            )
        elif selected_year in available_historical_years:
            year_scenario_list.append((selected_year, None))
        elif selected_year in available_future_years:
            year_scenario_list.extend(
                (selected_year, scenario) for scenario in scenarios
            )

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

    A historical year has no model and no scenario, and a future year
    comes with each scenario of each model. A year that is both comes
    once without them and once with each of them.

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
    model : str | None
        The specific climate model for which the data is to be
        downloaded.
    scenario : str | None
        The specific scenario for which the data is to be downloaded.
    available_scenarios_for_model : dict[str, list[str]]
        The available scenarios for each climate model.

    Returns
    -------
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        A list of tuples, where each tuple contains a year, an optional
        climate model, and an optional scenario.
    """
    available_years = sorted(
        set(available_historical_years + available_future_years)
    )

    years = _get_years(year, start_year, end_year, available_years)
    scenarios_for_model = _get_scenarios_for_model(
        model,
        scenario,
        available_scenarios_for_model,
    )

    year_model_scenario_list: list[tuple[int, str | None, str | None]] = []
    for selected_year in years:
        if (
            selected_year in available_historical_years
            and selected_year in available_future_years
        ):
            year_model_scenario_list.append((selected_year, None, None))
            for (
                model_key,
                scenario_keys,
            ) in scenarios_for_model.items():
                year_model_scenario_list.extend(
                    (selected_year, model_key, scenario_key)
                    for scenario_key in scenario_keys
                )
        elif selected_year in available_historical_years:
            year_model_scenario_list.append((selected_year, None, None))
        elif selected_year in available_future_years:
            for (
                model_key,
                scenario_keys,
            ) in scenarios_for_model.items():
                year_model_scenario_list.extend(
                    (selected_year, model_key, scenario_key)
                    for scenario_key in scenario_keys
                )

    return year_model_scenario_list


def _extend_historical_years(available_years: list[int]) -> list[int]:
    """
    Extend historical years up to last year if needed.

    The years after the last available one, up to last year, are added:
    if the last available year is 2021 and the current year is 2024,
    2022 and 2023 are added.

    Parameters
    ----------
    available_years : list[int]
        The list of available years.

    Returns
    -------
    list[int]
        The extended list of available years.
    """
    current_year = pd.Timestamp.now().year
    last_historical_year = available_years[-1]

    if last_historical_year >= current_year - 1:
        return available_years

    missing_years = list(range(last_historical_year + 1, current_year))
    return available_years + missing_years


def _get_years_with_data(
    global_historical_data: pd.DataFrame, code: str
) -> list[int]:
    """
    Get the years with data of a country or subdivision.

    Parameters
    ----------
    global_historical_data : pandas.DataFrame
        The historical data, with a row for each code and a column for
        each year.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    list[int]
        The years whose value is not missing, in order.
    """
    return sorted(
        int(year)
        for year in pd.Series(global_historical_data.loc[code]).dropna().index
    )


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
    Get the years and scenarios of a country or subdivision.

    The used historical years can differ from the requested ones: if the
    requested years of a country are 2020 to 2024, and its historical
    data ends in 2023, the used historical years are 2020 to 2023, and
    2023 is used for 2024. A year without data between two years with
    data, such as a gap of the World Bank, uses the year before it with
    data, with a warning.

    The historical years of a subdivision are those of the gridded data,
    and, if its country has historical data, also the years of the
    country before them, for which the first year of the gridded data is
    used: the data of the subdivision then follows its country.

    Parameters
    ----------
    iso_alpha_3_code : str
        The code of the country or subdivision.
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
    global_historical_data : pandas.DataFrame
        The historical data, with a row for each code and a column for
        each year.
    available_historical_years_of_gridded_data : list[int]
        The list of available historical years for the gridded data.

    Returns
    -------
    tuple[list[int], list[int], list[int], list[str]]
        A tuple containing:
        - requested_historical_years: list[int]
            The list of requested historical years.
        - used_historical_years: list[int]
            The year whose data is used for each requested historical
            year.
        - future_years: list[int]
            The list of future years.
        - scenarios: list[str]
            The list of scenarios.
    """
    if iso_alpha_3_code in global_historical_data.index:
        years_with_data = _get_years_with_data(
            global_historical_data, iso_alpha_3_code
        )
    else:
        # Interpolate the years between those of the gridded data.
        years_with_data = list(
            range(
                available_historical_years_of_gridded_data[0],
                available_historical_years_of_gridded_data[-1] + 1,
            )
        )
    available_historical_years = list(
        range(years_with_data[0], years_with_data[-1] + 1)
    )
    country_code = iso_alpha_3_code.split("_", maxsplit=1)[0]
    earlier_years: list[int] = []
    if (
        iso_alpha_3_code not in global_historical_data.index
        and country_code in global_historical_data.index
    ):
        earlier_years = list(
            range(
                _get_years_with_data(global_historical_data, country_code)[0],
                available_historical_years[0],
            )
        )

    extended_available_historical_years = earlier_years + (
        _extend_historical_years(available_historical_years)
    )
    available_future_years = list(
        range(
            max(extended_available_historical_years) + 1,
            utils.catalogue.LAST_PROJECTION_YEAR + 1,
        )
    )

    available_years = sorted(
        set(extended_available_historical_years + available_future_years)
    )

    all_requested_years = _get_years(
        year,
        start_year,
        end_year,
        available_years,
    )

    requested_historical_years = [
        y
        for y in all_requested_years
        if y in extended_available_historical_years
    ]
    used_historical_years = [
        max(
            (with_data for with_data in years_with_data if with_data <= y),
            default=years_with_data[0],
        )
        for y in requested_historical_years
    ]
    gap_years = [
        y
        for y in requested_historical_years
        if years_with_data[0] < y < years_with_data[-1]
        and y not in years_with_data
    ]
    if gap_years:
        logging.warning(
            f"The historical data of {iso_alpha_3_code} has no value in "
            f"{gap_years}, which take the value of the year before them "
            "with data."
        )

    future_years = [
        y for y in all_requested_years if y in available_future_years
    ]

    scenarios = (
        _get_scenarios(scenario, available_scenarios) if future_years else []
    )

    return (
        requested_historical_years,
        used_historical_years,
        future_years,
        scenarios,
    )
