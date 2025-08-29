# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    population data the World Bank and future population data from the
    IAMC scenarios. The population data is extracted for the countries
    and subdivisions of interest and saved into CSV and Parquet files.

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
import xarray

import retrievals.gridded_population


def download_population_from_world_bank() -> pandas.DataFrame:
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


def extract_historical_population(
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


def _get_future_population(
    iso_alpha_3_code: str,
    scenario: str,
    future_years: list[int],
) -> pandas.Series:
    """
    Get the future electricity demand per capita.

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


def _get_population_from_gridded_data(
    code: str, year: int, scenario: str | None
) -> float:
    """
    Get the population from gridded data.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.
    year : int
        The year of the population data to be retrieved.
    scenario : str
        The scenario of the population data to be retrieved.

    Returns
    -------
    float
        The population for the given subdivision.
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

    # Get the shape of the subdivision.
    shape = utils.shapes.get_entity_shape(
        code, make_plot=True, remove_remote_islands=False
    )

    # Calculate the fraction of the grid cells that belong to the
    # subdivision.
    fractions = utils.geospatial.get_fraction_of_grid_cells_in_shape(
        shape, make_plot=True
    )

    # Multiply the population by the fractions and sum over all grid
    # cells to get the total population of the subdivision.
    return (gridded_population * fractions).sum().item()


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

    This function downloads historical population data from the World
    Bank and future population data from the IAMC scenarios, extracts
    the data for the countries and subdivisions of interest, and saves
    the data into CSV and Parquet files.

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
    world_bank_population = download_population_from_world_bank()

    # Get the list of codes of the countries and subdivisions.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Define the available scenarios for the population data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Loop over the countries and subdivisions.
    for code in codes:
        if "_" in code:
            # todo
            logging.warning(
                f"Population data for subdivisions is not yet supported. "
                f"Skipping {code}."
            )
        else:
            # Get the ISO Alpha-3 code of the country.
            iso_alpha_3_code = utils.entities.get_iso_alpha_3_code(code)

            # Extract the historical population for the country.
            historical_population = extract_historical_population(
                world_bank_population, iso_alpha_3_code
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

            # Define the file path of the population data of the country
            # or subdivision.
            file_path_without_ext = os.path.join(result_directory, code)

            # Get the selcted historical years.
            selected_historical_years = [
                year
                for year, scenario in year_scenario_list
                if scenario is None
            ]

            # Get the selected future years.
            selected_future_years = [
                year
                for year, scenario in year_scenario_list
                if scenario is not None
            ]

            # Get the selected scenarios.
            selected_scenarios = list(
                set(
                    [
                        scenario
                        for year, scenario in year_scenario_list
                        if scenario is not None
                    ]
                )
            )

            if (
                not os.path.exists(file_path_without_ext + ".parquet")
                or not os.path.exists(file_path_without_ext + ".csv")
            ) and selected_historical_years:
                logging.info(
                    f"Extracting historical population data for {code}."
                )

                # Extract the selected historical population data.
                selected_historical_population = historical_population.loc[
                    historical_population.index.isin(selected_historical_years)
                ]

                # Rename the index and the variable.
                selected_historical_population.index.name = "Year"
                selected_historical_population.name = "Population"

                # Save the historical population data to CSV and
                # Parquet files.
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

                        # Get the future population for the country and
                        # scenario of interest.
                        future_population = _get_future_population(
                            iso_alpha_3_code,
                            scenario,
                            available_future_years,
                        )

                        # Select the future population for the selected
                        # years.
                        selected_future_population = future_population.loc[
                            future_population.index.isin(selected_future_years)
                        ]

                        # Rename the index and the variable.
                        selected_future_population.index.name = "Year"
                        selected_future_population.name = "Population"

                        # Save the future population data to CSV and
                        # Parquet files.
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
