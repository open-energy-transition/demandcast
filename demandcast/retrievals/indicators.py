"""
License: AGPL-3.0.

Description:

    This module runs the steps that the retrievals of the indicators
    share: the population, the GDP PPP per capita and the annual
    electricity demand per capita.

    For each country or subdivision, a retrieval gives a request: the
    historical years, the future years and the scenarios to save, and
    the functions that extract their values. The values are saved as
    hourly values over the local years (see
    utils.time_series.save_yearly_values), in one file for the
    historical years, <code>, and one for each scenario,
    <code>_<scenario>, with the hyphens of the scenario replaced by
    underscores, which is the name that assemble.py reads.
"""

import dataclasses
import logging
import os
from collections.abc import Callable

import pandas as pd
from tqdm import tqdm

import utils.availability
import utils.paths
import utils.time_series
import utils.time_zones


@dataclasses.dataclass(frozen=True)
class Request:
    """
    The years and scenarios of a country or subdivision to save.

    Attributes
    ----------
    historical_years : list[int]
        The historical years, none if only projections are requested.
    future_years : list[int]
        The future years, none if only historical years are requested.
    scenarios : list[str]
        The scenarios of the future years.
    get_historical_values : Callable[[], pandas.Series]
        The function that gives the value of each historical year.
    get_future_values : Callable[[str], pandas.Series]
        The function that gives the value of each future year of a
        scenario.
    """

    historical_years: list[int]
    future_years: list[int]
    scenarios: list[str]
    get_historical_values: Callable[[], pd.Series]
    get_future_values: Callable[[str], pd.Series]


def get_file_path_without_extension(
    indicator: utils.paths.Indicator, code: str, scenario: str | None = None
) -> str:
    """
    Get the path of the file of an indicator, without its extension.

    Parameters
    ----------
    indicator : utils.paths.Indicator
        The indicator.
    code : str
        The code of the country or subdivision.
    scenario : str | None, optional
        The scenario, none for the historical years.

    Returns
    -------
    str
        The path, <code> or <code>_<scenario>, with the hyphens of the
        scenario replaced by underscores.
    """
    name = code if scenario is None else f"{code}_{scenario.replace('-', '_')}"
    return os.path.join(utils.paths.get_indicator_folder(indicator), name)


def run_retrieval(
    indicator: utils.paths.Indicator,
    column: str,
    description: str,
    code: str | None,
    file: str | None,
    get_request: Callable[[str], Request],
) -> None:
    """
    Save the requested years of an indicator of each entity.

    Parameters
    ----------
    indicator : utils.paths.Indicator
        The indicator, which names its folder.
    column : str
        The name of the column of the values.
    description : str
        The name of the indicator in the messages of the log.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    get_request : Callable[[str], Request]
        The function that gives the request of a country or
        subdivision.
    """
    os.makedirs(utils.paths.get_indicator_folder(indicator), exist_ok=True)

    codes = utils.availability.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )
    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        time_zone = utils.time_zones.get_time_zone(entity_code)
        request = get_request(entity_code)

        if request.historical_years:
            logging.info(
                f"Extracting the historical {description} of {entity_code}."
            )
            utils.time_series.save_yearly_values(
                request.get_historical_values(),
                request.historical_years,
                column,
                get_file_path_without_extension(indicator, entity_code),
                time_zone,
            )
            logging.info(
                f"The historical {description} of {entity_code} has been "
                "saved."
            )

        if request.future_years:
            for scenario in request.scenarios:
                logging.info(
                    f"Extracting the {description} of {entity_code} in "
                    f"scenario {scenario}."
                )
                utils.time_series.save_yearly_values(
                    request.get_future_values(scenario),
                    request.future_years,
                    column,
                    get_file_path_without_extension(
                        indicator, entity_code, scenario
                    ),
                    time_zone,
                )
                logging.info(
                    f"The {description} of {entity_code} in scenario "
                    f"{scenario} has been saved."
                )
