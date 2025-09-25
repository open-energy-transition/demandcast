# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download population density from
    SEDAC for historical years (2000-2020) and population count from
    Figshare for future years (2025-2100) under different Shared
    Socioeconomic Pathways (SSPs). It then extracts the population data
    for the countries and subdivisions of interest at a 0.25-degree
    resolution, and saves it into NetCDF files.

    Source: https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/browseui/#sedac-popdensity-yeargrid5yr-v4.11/
    Source: https://doi.org/10.6084/m9.figshare.19608594
    Source: https://doi.org/10.1038/s41597-022-01675-x
"""  # noqa: W505

import io
import logging
import os
import zipfile

import requests
import utils.directories
import utils.entities
import utils.figures
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray
from tqdm import tqdm


def _download_historical_gridded_population_density(
    downloaded_data_directory: str, year: int
) -> None:
    """
    Download historical population density data from SEDAC.

    Parameters
    ----------
    downloaded_data_directory : str
        The directory where the population density data will be saved.
    year : int
        The year of the population density data to be downloaded.
    """
    assert year in list(range(2000, 2021, 5)), (
        "year must be one of the available years: "
        f"{list(range(2000, 2021, 5))}."
    )

    # Define the file path for the population density data.
    file_path = os.path.join(downloaded_data_directory, f"{year}.tif")

    if not os.path.exists(file_path):
        logging.info(
            "Downloading global gridded population density data from SEDAC "
            f"for the year {year}."
        )

        # Define the URL of the population density data.
        url = (
            "https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/"
            f"gpw_v4_population_density_rev11_{year}_30_sec_{year}.tif"
        )

        # Download the population density data.
        response = requests.get(url)

        # Check if the request was successful.
        response.raise_for_status()

        # Save the response content.
        with open(file_path, "wb") as file:
            file.write(response.content)

        logging.info(
            f"Global gridded population density data for the year {year} has "
            "been downloaded successfully."
        )
    else:
        logging.info(
            f"Global gridded population density data for the year {year} "
            "already exists. Skipping download."
        )


def _download_future_gridded_population(
    downloaded_data_directory: str, scenario: str
) -> None:
    """
    Download future population data from Figshare.

    Parameters
    ----------
    downloaded_data_directory : str
        The directory where the population data will be saved.
    scenario : str
        The scenario of the population data to be downloaded.
    """
    assert scenario in ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"], (
        "ssp must be one of the following: ['SSP1', 'SSP2', 'SSP3', "
        "'SSP4', 'SSP5']."
    )

    # Define the folder name for the population data for the specified
    # scenario.
    folder_name = os.path.join(
        downloaded_data_directory,
        scenario,
    )

    if not os.path.exists(folder_name):
        logging.info(
            "Downloading global gridded population data from Figshare for "
            f"{scenario}."
        )
        # Define the URL of the population data.
        match scenario:
            case "SSP1":
                url = "https://figshare.com/ndownloader/files/34829160"
            case "SSP2":
                url = "https://figshare.com/ndownloader/files/34829370"
            case "SSP3":
                url = "https://figshare.com/ndownloader/files/45894312"
            case "SSP4":
                url = "https://figshare.com/ndownloader/files/34829385"
            case "SSP5":
                url = "https://figshare.com/ndownloader/files/34829391"

        # Fetch the data from the URL.
        response = requests.get(url)

        # Check if the request was successful.
        response.raise_for_status()

        # Extract all population data from the response.
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            archive.extractall(path=downloaded_data_directory)

        # Rename the extracted folders because of a typo.
        if scenario == "SSP1":
            os.rename(
                os.path.join(downloaded_data_directory, "SPP1"),
                os.path.join(downloaded_data_directory, "SSP1"),
            )
        elif scenario == "SSP2":
            os.rename(
                os.path.join(downloaded_data_directory, "SPP2"),
                os.path.join(downloaded_data_directory, "SSP2"),
            )
        elif scenario == "SSP4":
            os.rename(
                os.path.join(downloaded_data_directory, "SPP4"),
                os.path.join(downloaded_data_directory, "SSP4"),
            )
        elif scenario == "SSP5":
            os.rename(
                os.path.join(downloaded_data_directory, "SPP5"),
                os.path.join(downloaded_data_directory, "SSP5"),
            )

        logging.info(
            f"Global gridded population data for {scenario} has been "
            "downloaded successfully."
        )
    else:
        logging.info(
            f"Global gridded population data for {scenario} already exists. "
            "Skipping download."
        )


def _read_population_dataset(
    downloaded_data_directory: str, year: int, scenario: str | None
) -> xarray.DataArray:
    """
    Read the population dataset.

    The population dataset can be either for density in case of
    historical years or for count in case of future years.

    Parameters
    ----------
    downloaded_data_directory : str
        The directory where the population dataset is stored.
    year : int
        The year of the population dataset to be read.
    scenario : str | None
        The scenario of the population dataset to be read. If None,
        the historical population density data will be read.

    Returns
    -------
    xarray.DataArray
        The population data for the specified year and scenario.
    """
    # Define the file path of the population dataset.
    if scenario is None:
        # For historical years, the file name is just the year.
        file_path = os.path.join(downloaded_data_directory, f"{year}.tif")
    else:
        # For future years, the file name includes the scenario.
        file_path = os.path.join(
            downloaded_data_directory,
            scenario,
            f"{scenario}_{year}.tif",
        )

    # Download the population dataset.
    global_population_dataset = xarray.open_dataarray(
        file_path, engine="rasterio"
    )

    if scenario is not None:
        # For future population data, the coordinates need to be
        # converted to standard longitude and latitude.
        global_population_dataset["x"] = (
            global_population_dataset["x"]
            - global_population_dataset["x"].min()
        ) / (
            global_population_dataset["x"].max()
            - global_population_dataset["x"].min()
        ) * (360 - 30 / 3600) - (180 - 30 / 3600)
        global_population_dataset["y"] = (
            global_population_dataset["y"]
            - global_population_dataset["y"].min()
        ) / (
            global_population_dataset["y"].max()
            - global_population_dataset["y"].min()
        ) * (156 - 30 / 3600) - (72 - 30 / 3600)

    # Harmonize the population dataset.
    global_population_dataset = utils.geospatial.harmonize_coords(
        global_population_dataset
    )

    # Clean the dataset and return it.
    return utils.geospatial.clean_raster(
        global_population_dataset, "population"
    )


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract gridded population data.

    This function downloads population density data for historical
    years (2000-2020) from SEDAC and population count data for future
    years (2025-2100) from Figshare under different Shared
    Socioeconomic Pathways (SSPs). It then extracts the population
    data for the countries and subdivisions of interest at a
    0.25-degree resolution, and saves it into NetCDF files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The path to the file containing the list of codes of the
        countries and subdivisions of interest.
    year : int | None
        The year of the population data to be retrieved.
    start_year : int | None
        The start year of the range of population data to be retrieved.
    end_year : int | None
        The end year of the range of population data to be retrieved.
    scenario : str | None
        The scenario of the population data to be retrieved.
    """
    # Get the directory to store the population data.
    result_directory = utils.directories.read_folders_structure()[
        "gridded_population_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the directory to store the downloaded population data.
    downloaded_data_directory = os.path.join(result_directory, "downloads")
    os.makedirs(downloaded_data_directory, exist_ok=True)

    # Define the available years for the historical population data.
    available_historical_years = list(range(2000, 2021, 5))

    # Define the available years for the future population data.
    available_future_years = list(range(2025, 2101, 5))

    # Define the available scenarios for the population data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Get the list of year and scenario combinations.
    year_scenario_list = utils.scenarios.get_year_and_scenario_combinations(
        year,
        start_year,
        end_year,
        available_historical_years,
        available_future_years,
        scenario,
        available_scenarios,
    )

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "shape", code=code, file_path=file
    )

    # Loop over the years and scenarios.
    for year, scenario in tqdm(year_scenario_list, desc="Years and scenarios"):
        logging.info(
            f"Processing gridded population data for the year {year}"
            + (f" and scenario {scenario}." if scenario else ".")
        )

        if year <= 2020:
            # Download historical population density data.
            _download_historical_gridded_population_density(
                downloaded_data_directory, year
            )
        elif year >= 2025 and scenario is not None:
            # Download future population data.
            _download_future_gridded_population(
                downloaded_data_directory, scenario
            )

        # Define the year and scenario string for the file name.
        year_scenario = f"{year}_{scenario}" if scenario else str(year)

        # Read the population dataset for the specified year and
        # scenario.
        global_population_dataset = _read_population_dataset(
            downloaded_data_directory, year, scenario
        )

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population for the country or
            # subdivision.
            file_path = os.path.join(
                result_directory, f"{code}_0.25_deg_{year_scenario}.nc"
            )

            if not os.path.exists(file_path):
                logging.info(f"Extracting gridded population data for {code}.")

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    code, make_plot=False
                )

                # Get the lateral bounds of the country or subdivision
                # of interest.
                entity_bounds = utils.shapes.get_entity_bounds(
                    entity_shape
                )  # West, South, East, North

                # Select the population data within the bounds of the
                # country or subdivision.
                population_dataset = global_population_dataset.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                if year in available_historical_years:
                    # Convert the population density to population
                    # count.
                    population = utils.geospatial.from_density_to_count(
                        population_dataset
                    )
                else:
                    population = population_dataset

                # Coarsen the population to the same resolution as the
                # weather data.
                population = utils.geospatial.coarsen(
                    population, entity_bounds
                )

                # Save the population data to a NetCDF file.
                population.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the population data.
                    utils.figures.simple_plot(
                        population,
                        f"population_{code}_{year_scenario}",
                    )

                logging.info(
                    f"Gridde population data for {code} has been successfully "
                    "extracted and saved."
                )

            else:
                logging.info(
                    f"Gridde population data for {code} already exists. "
                    "Skipping extraction."
                )
