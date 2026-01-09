# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    population data the World Bank and future population data from the
    IAMC scenarios for the countries of interest. For subdivisions, the
    population data is calculated by aggregating gridded population
    data. The population data is saved into CSV and Parquet files.
"""

import logging
import os

import pandas
import utils.config
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.time_series
from tqdm import tqdm

import retrievals.socio_economic_data_sources.iiasa as iiasa
import retrievals.socio_economic_data_sources.world_bank as world_bank


def _extract_historical_population(
    code: str,
    global_historical_population: pandas.DataFrame,
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
    return (historical_population.reindex(used_historical_years)).set_axis(
        requested_historical_years,
    )


def _extract_future_population(
    code: str,
    global_future_population: pandas.DataFrame,
    future_years: list[int],
    available_future_years_of_gridded_data: list[int],
    available_historical_years_of_gridded_data: list[int],
    scenario: str,
) -> pandas.Series:
    """
    Extract the future population for the country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    global_future_population : pandas.DataFrame
        The global future population data.
    years_and_scenarios : dict[str, list[int] | dict[str, list[int]]]
        The years and scenarios dictionary for the country.
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
    result_directory = utils.config.read_folders_structure()[
        "population_folder"
    ]
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
    available_historical_years_of_gridded_data = list(range(2000, 2021, 5))
    available_future_years_of_gridded_data = list(range(2025, 2101, 5))

    # Define the available scenarios for the population data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Loop over the countries and subdivisions.
    for code in tqdm(codes, desc="Countries and subdivisions"):
        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(code)

        # Get the years and scenarios dictionary for the country or
        # subdivision of interest.
        (
            requested_historical_years,
            used_historical_years,
            future_years,
            scenarios,
        ) = utils.scenarios.get_years_and_scenarios(
            code,
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
        file_path_without_ext = os.path.join(result_directory, code)

        if requested_historical_years:
            if not os.path.exists(
                file_path_without_ext + ".parquet"
            ) or not os.path.exists(file_path_without_ext + ".csv"):
                logging.info(
                    f"Extracting historical population data for {code}."
                )

                # Extract the historical population data for the
                # country or subdivision of interest.
                historical_population = _extract_historical_population(
                    code,
                    global_historical_population,
                    requested_historical_years,
                    used_historical_years,
                    available_historical_years_of_gridded_data,
                )

                # Extract the historical population for the selected
                # years.
                selected_historical_population = historical_population.loc[
                    historical_population.index.isin(
                        requested_historical_years
                    )
                ]

                # Convert the historical population data from yearly to
                # hourly values.
                selected_historical_population = (
                    utils.time_series.convert_from_yearly_to_hourly(
                        selected_historical_population,
                        time_zone,
                    )
                )

                # Clean the time series.
                selected_historical_population = utils.time_series.clean_data(
                    selected_historical_population,
                    "Population",
                )

                # Save the historical population data to CSV and Parquet
                # files.
                selected_historical_population.to_frame().to_parquet(
                    file_path_without_ext + ".parquet",
                )
                selected_historical_population.to_csv(
                    file_path_without_ext + ".csv",
                )

                logging.info(
                    f"Historical population data for {code} has been "
                    "extracted and saved successfully."
                )

            else:
                logging.info(
                    f"Historical population data for {code} already "
                    "exists. Skipping extraction."
                )

        if future_years:
            for scenario in scenarios:
                if not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.parquet"
                ) or not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.csv"
                ):
                    logging.info(
                        f"Extracting future population data for "
                        f"{code} and scenario {scenario}."
                    )

                    # Extract the future population data for the country
                    # or subdivision of interest.
                    future_population = _extract_future_population(
                        code,
                        global_future_population,
                        future_years,
                        available_future_years_of_gridded_data,
                        available_historical_years_of_gridded_data,
                        scenario,
                    )

                    # Extract the future population for the selected
                    # years.
                    selected_future_population = future_population.loc[
                        future_population.index.isin(future_years)
                    ]

                    # Convert the future population data from yearly to
                    # hourly values.
                    selected_future_population = (
                        utils.time_series.convert_from_yearly_to_hourly(
                            selected_future_population,
                            time_zone,
                        )
                    )

                    # Clean the time series.
                    selected_future_population = utils.time_series.clean_data(
                        selected_future_population,
                        "Population",
                    )

                    # Save the future population data to CSV and Parquet
                    # files.
                    selected_future_population.to_frame().to_parquet(
                        f"{file_path_without_ext}_{scenario}.parquet",
                    )
                    selected_future_population.to_csv(
                        f"{file_path_without_ext}_{scenario}.csv",
                    )

                    logging.info(
                        f"Future population data for {code} and "
                        f"scenario {scenario} has been extracted "
                        "and saved successfully."
                    )

                else:
                    logging.info(
                        f"Future population data for {code} and "
                        f"scenario {scenario} already exists. "
                        "Skipping extraction."
                    )
