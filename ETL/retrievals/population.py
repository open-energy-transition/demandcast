# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module downloads population density data from SEDAC
    (Socioeconomic Data and Applications Center). It then extracts the
    population density data for the countries and subdivisions of
    interest, coarsens the data to a 0.25-degree resolution, and saves
    it into NetCDF files. The country and subdivision code can be
    specified or a list can be provided as a yaml file. If no file or
    code is provided, the script will use all available codes. The year
    of the population density data can be specified as a command line
    argument.

    Source: https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/browseui/#sedac-popdensity-yeargrid5yr-v4.11/
    Source: https://doi.org/10.6084/m9.figshare.19608594
    Source: https://doi.org/10.1038/s41597-022-01675-x
"""

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


def _download_historic_population(result_directory: str, year: int) -> None:
    """
    Download population data from SEDAC for historic years (2000-2020).

    Parameters
    ----------
    year : int
        The year of the population data to be downloaded.
    """
    assert year in list(range(2000, 2021, 5)), (
        "year must be one of the available years: "
        f"{list(range(2000, 2021, 5))}."
    )

    # Define the directory to save the population data.
    os.makedirs(
        os.path.join(result_directory, "downloaded_population"), exist_ok=True
    )

    # Define the file path for the population data.
    file_path = os.path.join(
        result_directory, "downloaded_population", f"{year}.tif"
    )

    if not os.path.exists(file_path):
        logging.info(
            f"Downloading population data from SEDAC for the year {year}."
        )

        # Define the URL of the population data.
        url = (
            "https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/"
            f"gpw_v4_population_density_rev11_{year}_30_sec_{year}.tif"
        )

        # Download the population data.
        response = requests.get(url)

        # Check if the request was successful.
        response.raise_for_status()

        # Save the response content.
        with open(file_path, "wb") as file:
            file.write(response.content)
    else:
        logging.info(
            f"Population data for the year {year} already exists. "
            "Skipping download."
        )


def _download_future_population(result_directory: str, scenario: str) -> None:
    """
    Download future population data from Figshare.

    Parameters
    ----------
    year : int
        The year of the population data to be downloaded.
    ssp : str
        The Shared Socioeconomic Pathway (SSP) scenario.
    """
    assert scenario in ["ssp1", "ssp2", "ssp3", "ssp4", "ssp5"], (
        "ssp must be one of the following: ['ssp1', 'ssp2', 'ssp3', "
        "'ssp4', 'ssp5']."
    )

    # Create the directory to save the population data if it does not
    # already exist.
    os.makedirs(
        os.path.join(result_directory, "downloaded_population"), exist_ok=True
    )

    # Define the folder name for the population data for the specified
    # SSP.
    folder_name = os.path.join(
        result_directory,
        "downloaded_population",
        scenario.upper(),
    )

    if not os.path.exists(folder_name):
        logging.info(
            "Downloading population data from Figshare for "
            f"{scenario.upper()}."
        )
        # Define the URL of the population data.
        match scenario:
            case "ssp1":
                url = "https://figshare.com/ndownloader/files/34829160"
            case "ssp2":
                url = "https://figshare.com/ndownloader/files/34829370"
            case "ssp3":
                url = "https://figshare.com/ndownloader/files/45894312"
            case "ssp4":
                url = "https://figshare.com/ndownloader/files/34829385"
            case "ssp5":
                url = "https://figshare.com/ndownloader/files/34829391"

        # Fetch the data from the URL.
        response = requests.get(url)

        # Check if the request was successful.
        response.raise_for_status()

        # Extract all population data from the response.
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            archive.extractall(
                path=os.path.join(result_directory, "downloaded_population")
            )

        if scenario == "ssp1":
            # Rename the extracted folder for SSP1 because of a typo.
            os.rename(
                os.path.join(
                    result_directory, "downloaded_population", "SPP1"
                ),
                os.path.join(
                    result_directory, "downloaded_population", "SSP1"
                ),
            )
    else:
        logging.info(
            f"Population data for {scenario.upper()} already exists. "
            "Skipping download."
        )


def _read_population(
    result_directory: str, year: int, scenario: str | None
) -> xarray.DataArray:
    """
    Read the population data for the specified year and scenario.

    Parameters
    ----------
    result_directory : str
        The directory where the population data is stored.
    year : int
        The year of the population data to be read.
    scenario : str | None
        The Shared Socioeconomic Pathway (SSP) scenario.

    Returns
    -------
    xarray.DataArray
        The population data for the specified year and scenario.
    """
    # Define the file path of the population data.
    if scenario is None:
        # For historic years, the file name is just the year.
        file_path = os.path.join(
            result_directory, "downloaded_population", f"{year}.tif"
        )
    else:
        # For future years, the file name includes the SSP scenario.
        file_path = os.path.join(
            result_directory,
            "downloaded_population",
            scenario,
            f"{scenario}_{year}.tif",
        )

    # Download the population data.
    global_population = xarray.open_dataarray(file_path, engine="rasterio")

    if scenario is not None:
        # For population data from SSP scenarios, the coordinates
        # need to be converted to standard longitude and latitude.
        global_population["x"] = (
            global_population["x"] - global_population["x"].min()
        ) / (global_population["x"].max() - global_population["x"].min()) * (
            360 - 30 / 3600
        ) - (180 - 30 / 3600)
        global_population["y"] = (
            global_population["y"] - global_population["y"].min()
        ) / (global_population["y"].max() - global_population["y"].min()) * (
            156 - 30 / 3600
        ) - (72 - 30 / 3600)

    # Harmonize the population data.
    global_population = utils.geospatial.harmonize_coords(global_population)

    # Clean the dataset.
    global_population = utils.geospatial.clean_raster(
        global_population, "population"
    )

    return global_population


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract the population data.

    This function downloads population data from SEDAC, extracts the
    population data for the countries and subdivisions of interest,
    coarsens the data to a 0.25-degree resolution, and saves it into
    NetCDF files.

    Parameters
    ----------
    year : int | None
        The year of the population data to be downloaded.
    start_year : int | None
        The start year of the range of population data to be
        downloaded.
    end_year : int | None
        The end year of the range of population data to be downloaded.
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The path to the file containing the list of codes of the
        countries and subdivisions of interest.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "population_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Define the available years for the historic population data.
    available_historical_years = list(range(2000, 2021, 5))

    # Define the available years for the future population data.
    available_future_years = list(range(2025, 2101, 5))

    # Define the available SSPs for the population data.
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
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Loop over the years.
    for year, scenario in year_scenario_list:
        logging.info(
            f"Processing population for the year {year}"
            + (f" and {scenario}." if scenario else ".")
        )

        if year <= 2020:
            # Download historic population data.
            _download_historic_population(result_directory, year)
        elif year >= 2025 and scenario is not None:
            # Download future population data.
            _download_future_population(result_directory, scenario)

        # Define the year and scenario string for the file name.
        year_scenario = f"{year}_{scenario}" if scenario else str(year)

        # Read the GDP data for the specified year and SSP.
        global_population = _read_population(result_directory, year, scenario)

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            file_path = os.path.join(
                result_directory, f"{code}_0.25_deg_{year_scenario}.nc"
            )

            if not os.path.exists(file_path):
                logging.info(f"Extracting population density data of {code}.")

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    code, make_plot=False
                )

                # Get the lateral bounds of the country or subdivision
                # of interest.
                entity_bounds = utils.shapes.get_entity_bounds(
                    entity_shape
                )  # West, South, East, North

                # Select the population density data in the bounding box
                # of the country or subdivision of interest.
                population = global_population.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                # Coarsen the population density data to the same
                # resolution as the weather data.
                population = utils.geospatial.coarsen(
                    population, entity_bounds
                )

                # Save the population density data.
                population.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the population density data.
                    utils.figures.simple_plot(
                        population,
                        f"population_density_{code}_{year_scenario}",
                    )

                logging.info(
                    f"Population density data for {code} has been "
                    "successfully extracted and saved."
                )

            else:
                logging.info(
                    f"Population density data for {code} already exists. "
                    "Skipping extraction."
                )
