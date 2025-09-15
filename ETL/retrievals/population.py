# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    population data the World Bank and future population data from the
    IAMC scenarios for the countries of interest. For subdivisions, the
    population data is calculated by aggregating gridded population
    data. The population data is saved into CSV and Parquet files.

    Source: https://data.worldbank.org/indicator/SP.POP.TOTL
    Source: https://tntcat.iiasa.ac.at/SspDb
"""

import logging
import os
import zipfile
from io import BytesIO

import pandas
import requests
import utils.directories
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.shapes
import utils.time_series
import xarray

import retrievals.gridded_population


def download_historical_population_from_world_bank() -> pandas.DataFrame:
    """
    Download historical population data from the World Bank.

    Returns
    -------
    pandas.DataFrame
        The historical population data from the World Bank.
    """
    logging.info("Downloading population data from the World Bank.")

    # Define the URL to download the population data.
    url = (
        "https://api.worldbank.org/v2/en/indicator/"
        "SP.POP.TOTL?downloadformat=csv"
    )

    # Fetch the data from the World Bank.
    response = requests.get(url)

    # Extract the archive from the response.
    with zipfile.ZipFile(BytesIO(response.content), "r") as archive:
        # Get the name of data file in the archive. It is the file that
        # does not start with "Metadata" and ends with ".csv".
        world_bank_file_name = [
            name
            for name in archive.namelist()
            if not name.startswith("Metadata") and name.endswith(".csv")
        ][0]

        # Extract and return the population from the archive.
        return pandas.read_csv(archive.open(world_bank_file_name), skiprows=4)


def extract_historical_population_from_world_bank(
    world_bank_population: pandas.DataFrame,
    iso_alpha_3_code: str,
) -> pandas.Series:
    """
    Extract the historical population.

    Parameters
    ----------
    world_bank_population : pandas.DataFrame
        The historical population data from the World Bank.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country or subdivision of interest.

    Returns
    -------
    pandas.Series
        The historical population for the given country or subdivision.
    """
    # Extract the population for the given country or subdivision.
    world_bank_population = (
        world_bank_population[
            world_bank_population["Country Code"] == iso_alpha_3_code
        ]
        .iloc[
            0,
            world_bank_population.columns.str.isdigit(),
        ]
        .dropna()
    )

    # Convert the index and the values to integers.
    world_bank_population.index = world_bank_population.index.astype(int)
    world_bank_population = world_bank_population.astype(int)

    return world_bank_population


def _get_future_population_from_iiasa(
    iso_alpha_3_code: str,
    scenario: str,
    future_years: list[int],
) -> pandas.Series:
    """
    Get the future population from the IIASA dataset.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.
    scenario : str
        The scenario of interest.
    future_years : list[int]
        The list of future years where the population data is
        interpolated.

    Returns
    -------
    pandas.Series
        The future population.

    Raises
    ------
    ValueError
        If there is not exactly one row for the region and scenario in
        the population data.
    """
    # Define the file path of the future population data.
    file_path = os.path.join(
        utils.directories.read_folders_structure()["population_folder"],
        "manual_downloads",
        "IAM_population.xlsx",
    )

    # Read the future population data.
    population = pandas.read_excel(
        file_path,
        sheet_name="data",
        index_col=0,
    )

    # Extract the population for the country and scenario of interest.
    population = population[
        (population["Region"] == iso_alpha_3_code)
        & (population["Scenario"] == scenario)
    ]

    # Check that there is only one row.
    if len(population) != 1:
        raise ValueError(
            f"Expected one row for country {iso_alpha_3_code} and scenario "
            f"{scenario}, but got {len(population)}."
        )

    # Convert to a Series with years as index by selecting only the
    # columns that are digits and dropping NaN values.
    population = population.iloc[
        0,
        population.columns.astype(str).str.isdigit(),
    ].dropna()

    # Reindex to one year frequency to cover all future years. The
    # missing years will be filled by linear interpolation.
    population = (
        population.astype(float)
        .reindex(
            list(range(population.index.min(), population.index.max() + 1))
        )
        .interpolate()
    )

    # Multiply by 1e6 to convert from millions to individuals and round
    # to the nearest integer.
    population = (population * 1e6).round().astype(int)

    # Select and return only the future years of interest.
    return population.loc[population.index.isin(future_years)]


def _calculate_population_from_gridded_data(
    code: str, year: int, scenario: str | None
) -> float:
    """
    Calculate the population by aggregating gridded data.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the population data to be retrieved.
    scenario : str
        The scenario of the population data to be retrieved.

    Returns
    -------
    float
        The population for the given country or subdivision.
    """
    # Define the available years and scenarios for the gridded
    # population data.

    # Define the path to the gridded population data.
    gridded_population_path = os.path.join(
        utils.directories.read_folders_structure()[
            "gridded_population_folder"
        ],
        f"{code}_0.25_deg_{year}"
        + (f"_{scenario}" if scenario else "")
        + ".nc",
    )

    if not os.path.exists(gridded_population_path):
        # Run the data retrieval for the gridded population.
        retrievals.gridded_population.run_data_retrieval(
            code=code,
            file=None,
            year=year,
            start_year=None,
            end_year=None,
            scenario=scenario,
        )

    # Read the gridded population data.
    gridded_population = xarray.open_dataarray(gridded_population_path)

    # Get the shape of the country or subdivision.
    shape = utils.shapes.get_entity_shape(
        code, make_plot=False, remove_remote_islands=False
    )

    # Calculate the fraction of the grid cells that belong to the
    # country or subdivision.
    fractions = utils.geospatial.get_fraction_of_grid_cells_in_shape(
        shape, make_plot=False
    )

    # Multiply the population by the fractions and sum over all grid
    # cells to get the total population of the country or subdivision.
    return (gridded_population * fractions).sum().item()


def _select_years_of_gridded_data(
    available_years_of_gridded_data: list[int],
    selected_years: list[int],
) -> list[int]:
    """
    Select the years of gridded data.

    The function selects the years of gridded data that cover the
    selected years of population data.

    Parameters
    ----------
    available_years_of_gridded_data : list[int]
        The available years of gridded data.
    selected_years : list[int]
        The selected years of population data.

    Returns
    -------
    list[int]
        The selected years of gridded data.
    """
    # Get the first year of available gridded data that is less than
    # or equal to the minimum selected year.
    first_selected_year_of_gridded_data = max(
        [
            year
            for year in available_years_of_gridded_data
            if year <= min(selected_years)
        ]
    )

    # Get the last year of available gridded data that is greater than
    # or equal to the maximum selected year.
    last_selected_year_of_gridded_data = min(
        [
            year
            for year in available_years_of_gridded_data
            if year >= max(selected_years)
        ]
    )

    # Select and return the years of gridded data that cover the
    # selected years of population data.
    return [
        year
        for year in available_years_of_gridded_data
        if first_selected_year_of_gridded_data
        <= year
        <= last_selected_year_of_gridded_data
    ]


def _get_historical_population_from_gridded_data(
    code: str,
    selected_historical_years: list[int],
    available_historical_years_of_gridded_data: list[int],
) -> pandas.Series:
    """
    Get the historical population from gridded data.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.
    selected_historical_years : list[int]
        The selected historical years of population data.
    available_historical_years_of_gridded_data : list[int]
        The available historical years of gridded data.

    Returns
    -------
    pandas.Series
        The historical population for the given subdivision.
    """
    # Get years of available historical gridded data that cover the
    # selected historical years.
    selected_historical_years_of_gridded_data = _select_years_of_gridded_data(
        available_historical_years_of_gridded_data,
        selected_historical_years,
    )

    # Extract the historical population for the subdivision.
    population_list = [
        _calculate_population_from_gridded_data(code, year, scenario=None)
        for year in selected_historical_years_of_gridded_data
    ]

    # Construct a Series with the historical population data.
    historical_population = pandas.Series(
        data=population_list,
        index=selected_historical_years_of_gridded_data,
    )
    historical_population.index.name = "Year"
    historical_population.name = "Population"

    # Interpolate to the selected historical years and return it.
    return historical_population.reindex(
        list(
            range(
                historical_population.index.min(),
                historical_population.index.max() + 1,
            )
        )
    ).interpolate()


def _get_future_population_from_gridded_data(
    code: str,
    selected_future_years: list[int],
    available_future_years_of_gridded_data: list[int],
    last_available_historical_years_of_gridded_data: int,
    scenario: str,
) -> pandas.Series:
    """
    Get the future population from gridded data.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.
    selected_future_years : list[int]
        The selected future years of population data.
    available_future_years_of_gridded_data : list[int]
        The available future years of gridded data.
    last_available_historical_years_of_gridded_data : int
        The last available historical year of gridded data.
    scenario : str
        The scenario of the population data to be retrieved.

    Returns
    -------
    pandas.Series
        The future population for the given subdivision and scenario.
    """
    # Get years of available future gridded data that cover the selected
    # future years. Add the last year of historical gridded data to
    # ensure continuity.
    selected_future_years_of_gridded_data = _select_years_of_gridded_data(
        [last_available_historical_years_of_gridded_data]
        + available_future_years_of_gridded_data,
        selected_future_years,
    )

    # Extract the future population for the subdivision and scenario of
    # interest. Include the last year of historical gridded data to
    # ensure continuity, if needed.
    population_list = [
        _calculate_population_from_gridded_data(code, year, scenario=scenario)
        if year in available_future_years_of_gridded_data
        else _calculate_population_from_gridded_data(code, year, scenario=None)
        for year in selected_future_years_of_gridded_data
    ]

    # Construct a Series with the future population data.
    future_population = pandas.Series(
        data=population_list,
        index=selected_future_years_of_gridded_data,
    )
    future_population.index.name = "Year"
    future_population.name = "Population"

    # Interpolate to the selected future years and return it.
    return future_population.reindex(
        list(
            range(
                future_population.index.min(),
                future_population.index.max() + 1,
            )
        )
    ).interpolate()


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
    result_directory = utils.directories.read_folders_structure()[
        "population_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Download the historical population data from the World Bank.
    world_bank_population = download_historical_population_from_world_bank()

    # Get the list of codes of the countries and subdivisions.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Define the available years for gridded population data.
    available_historical_years_of_gridded_data = list(range(2000, 2021, 5))
    available_future_years_of_gridded_data = list(range(2025, 2101, 5))

    # Define the available scenarios for the population data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Loop over the countries and subdivisions.
    for code in codes:
        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(code)

        # Check if the code is a subdivision (contains an underscore).
        if "_" in code:
            # Define the available years for the population data when
            # interpolating from gridded data.
            available_historical_years = list(range(2000, 2021))
            available_future_years = list(range(2021, 2101))
        else:
            # Get the ISO Alpha-3 code of the country.
            iso_alpha_3_code = utils.entities.get_iso_alpha_3_code(code)

            # Extract the historical population for the country.
            historical_population = (
                extract_historical_population_from_world_bank(
                    world_bank_population, iso_alpha_3_code
                )
            )

            # Get the years of available historical data.
            available_historical_years = historical_population.index.tolist()

            # Get the years of available future data.
            available_future_years = list(
                range(max(available_historical_years) + 1, 2101)
            )

        # Get the list of year and scenario combinations.
        year_scenario_list = (
            utils.scenarios.get_year_and_scenario_combinations(
                year,
                start_year,
                end_year,
                available_historical_years,
                available_future_years,
                scenario,
                available_scenarios,
            )
        )

        # Get the selcted historical years.
        selected_historical_years = list(
            set(
                [
                    year
                    for year, scenario in year_scenario_list
                    if scenario is None
                ]
            )
        )

        # Get the selected future years.
        selected_future_years = list(
            set(
                [
                    year
                    for year, scenario in year_scenario_list
                    if scenario is not None
                ]
            )
        )

        # Get the selected scenarios.
        selected_scenarios = list(
            set(
                [
                    scenario
                    for __, scenario in year_scenario_list
                    if scenario is not None
                ]
            )
        )

        # Define the file path of the population data of the
        # subdivision.
        file_path_without_ext = os.path.join(result_directory, code)

        if (
            not os.path.exists(file_path_without_ext + ".parquet")
            or not os.path.exists(file_path_without_ext + ".csv")
        ) and selected_historical_years:
            logging.info(f"Extracting historical population data for {code}.")

            # Get the historical population for the country or
            # subdivision of interest.
            if "_" in code:
                historical_population = (
                    _get_historical_population_from_gridded_data(
                        code,
                        selected_historical_years,
                        available_historical_years_of_gridded_data,
                    )
                )
            else:
                historical_population = (
                    extract_historical_population_from_world_bank(
                        world_bank_population, iso_alpha_3_code
                    )
                )

            # Extract the selected historical years.
            selected_historical_population = historical_population.loc[
                historical_population.index.isin(selected_historical_years)
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

        if selected_future_years:
            for scenario in selected_scenarios:
                if not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.parquet"
                ) or not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.csv"
                ):
                    logging.info(
                        f"Extracting future population data for "
                        f"{code} and scenario {scenario}."
                    )
                    # Get the future population for the country or
                    # subdivision and scenario of interest.
                    if "_" in code:
                        future_population = (
                            _get_future_population_from_gridded_data(
                                code,
                                selected_future_years,
                                available_future_years_of_gridded_data,
                                available_historical_years_of_gridded_data[-1],
                                scenario,
                            )
                        )
                    else:
                        future_population = _get_future_population_from_iiasa(
                            iso_alpha_3_code,
                            scenario,
                            available_future_years,
                        )

                    # Extract only the selected future years.
                    selected_future_population = future_population.loc[
                        future_population.index.isin(selected_future_years)
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
