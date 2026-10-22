"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    population data the World Bank and future population data from the
    IAMC scenarios for the countries of interest. For subdivisions, the
    population data is calculated by aggregating gridded population
    data. The population data is saved into CSV and Parquet files.

    The gridded population of the past (Gridded Population of the World,
    version 4.11, of SEDAC) ends in 2020, and version 5 is not released
    yet. The population of a subdivision after 2020 is that of 2020
    times the growth of the population of its country since 2020, from
    the World Bank, until its last year: the subdivision is assumed to
    grow as its country.
"""

import logging
import os

import pandas as pd
import utils.catalogue
import utils.entities
import utils.geospatial
import utils.paths
import utils.scenarios
import utils.time_series
from tqdm import tqdm

from retrievals.socio_economic_data_sources import iiasa, world_bank


def _extract_historical_population(
    code: str,
    global_historical_population: pd.DataFrame,
    requested_historical_years: list[int],
    used_historical_years: list[int],
    available_historical_years_of_gridded_data: list[int],
):
    # Check if code is in the historical population data. If not, it
    # means that it is a subdivision or a country not included in the
    # World Bank data.
    if code in global_historical_population.index:
        # Get the historical population from the World Bank data.
        historical_population = (
            global_historical_population.loc[code]
        ).dropna()
    else:
        # Extract the historical population for the country or
        # subdivision by aggregating gridded data.
        historical_population = (
            utils.geospatial.get_total_value_from_gridded_data(
                "population",
                code,
                used_historical_years,
                available_historical_years_of_gridded_data,
            )
        )

    # Map the requested historical years to the used (available)
    # historical years.
    historical_population = (
        historical_population.reindex(used_historical_years)
    ).set_axis(requested_historical_years)

    # Grow the population of a subdivision after the gridded data as its
    # country, until the last year of the country.
    country_code = code.split("_", maxsplit=1)[0]
    if (
        code not in global_historical_population.index
        and country_code in global_historical_population.index
    ):
        national_population = pd.Series(
            global_historical_population.loc[country_code]
        ).dropna()
        growth = (
            national_population.reindex(
                requested_historical_years, method="ffill"
            ).to_numpy()
            / national_population.reindex(
                used_historical_years, method="ffill"
            ).to_numpy()
        )
        historical_population = historical_population * growth

    return historical_population


def _extract_future_population(
    code: str,
    global_future_population: pd.DataFrame,
    future_years: list[int],
    available_future_years_of_gridded_data: list[int],
    available_historical_years_of_gridded_data: list[int],
    scenario: str,
) -> pd.Series:
    """
    Extract the future population for the country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    global_future_population : pandas.DataFrame
        The global future population data.
    future_years : list[int]
        The future years of interest.
    available_future_years_of_gridded_data : list[int]
        The available future years for gridded data.
    available_historical_years_of_gridded_data : list[int]
        The available historical years for gridded data.
    scenario : str
        The scenario of the future population data.

    Returns
    -------
    pandas.Series
        The future population for the country or subdivision.
    """
    # Check if code is in the future population data. If so, it means
    # that it is an ISO Alpha-3 code of a country.
    if code in global_future_population.index:
        # Get the future population from the IIASA data.
        future_population = iiasa.extract_and_interpolate(
            global_future_population,
            code,
            scenario,
        )
    else:
        # Extract the future population for the country or subdivision
        # by aggregating gridded data.
        future_population = utils.geospatial.get_total_value_from_gridded_data(
            "population",
            code,
            future_years,
            available_future_years_of_gridded_data,
            available_historical_years_of_gridded_data[-1],
            scenario,
        )

    return future_population


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract population data.

    This function downloads and extracts historical population data
    from the World Bank and future population data from the IAMC
    scenarios for the countries of interest. For subdivisions, the
    population data is calculated by aggregating gridded population
    data. The population data is saved into CSV and Parquet files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the electricity demand per capita data to be
        retrieved.
    start_year : int | None
        The start year of the range of electricity demand per capita
        data to be retrieved.
    end_year : int | None
        The end year of the range of electricity demand per capita
        data to be retrieved.
    scenario : str | None
        The scenario of the electricity demand per capita data to be
        retrieved.
    """
    # Get the directory to store the population data.
    result_directory = utils.paths.get_indicator_folder("population")
    os.makedirs(result_directory, exist_ok=True)

    # Download the historical population data.
    global_historical_population = world_bank.download("population")

    # Read the future population data.
    global_future_population = iiasa.read("population")

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )

    # Define the available years for gridded population data.
    available_historical_years_of_gridded_data = list(
        utils.catalogue.GRIDDED_POPULATION_YEARS
    )
    available_future_years_of_gridded_data = list(
        utils.catalogue.PROJECTION_YEARS
    )

    # Define the available scenarios for the population data.
    available_scenarios = list(utils.catalogue.SSP_SCENARIOS)

    # Loop over the countries and subdivisions.
    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(entity_code)

        # Get the years and scenarios dictionary for the country or
        # subdivision of interest.
        (
            requested_historical_years,
            used_historical_years,
            future_years,
            scenarios,
        ) = utils.scenarios.get_years_and_scenarios(
            entity_code,
            year,
            start_year,
            end_year,
            scenario,
            available_scenarios,
            global_historical_population,
            available_historical_years_of_gridded_data,
        )

        # Define the file path of the population data of the
        # subdivision.
        file_path_without_ext = os.path.join(result_directory, entity_code)

        if requested_historical_years:
            logging.info(
                f"Extracting historical population data for {entity_code}."
            )

            # Extract the historical population data for the
            # country or subdivision of interest.
            historical_population = _extract_historical_population(
                entity_code,
                global_historical_population,
                requested_historical_years,
                used_historical_years,
                available_historical_years_of_gridded_data,
            )

            # Save the selected years as hourly values.
            utils.time_series.save_yearly_values(
                historical_population,
                requested_historical_years,
                "Population",
                file_path_without_ext,
                time_zone,
            )

            logging.info(
                f"Historical population data for {entity_code} has been "
                "extracted and saved successfully."
            )

        if future_years:
            for selected_scenario in scenarios:
                logging.info(
                    f"Extracting future population data for "
                    f"{entity_code} and scenario {selected_scenario}."
                )

                # Extract the future population data for the country
                # or subdivision of interest.
                future_population = _extract_future_population(
                    entity_code,
                    global_future_population,
                    future_years,
                    available_future_years_of_gridded_data,
                    available_historical_years_of_gridded_data,
                    selected_scenario,
                )

                # Save the selected years as hourly values.
                utils.time_series.save_yearly_values(
                    future_population,
                    future_years,
                    "Population",
                    f"{file_path_without_ext}_{selected_scenario}",
                    time_zone,
                )

                logging.info(
                    f"Future population data for {entity_code} and "
                    f"scenario {selected_scenario} has been extracted "
                    "and saved successfully."
                )
