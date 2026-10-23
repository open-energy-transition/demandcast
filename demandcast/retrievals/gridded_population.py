"""
License: AGPL-3.0.

Description:

    This module includes functions to download population density from
    SEDAC for historical years (2000-2020) and population count from
    Figshare for future years (2025-2100) under different Shared
    Socioeconomic Pathways (SSPs). It then extracts the population data
    for the countries and subdivisions of interest at a 0.25-degree
    resolution, and saves it into NetCDF files.

    The archives of Figshare are downloaded from its download server,
    which the API of Figshare gives as their download URL: the links of
    its website, under figshare.com, now answer scripts with a challenge
    for bots instead of the file.

    Source: https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/browseui/#sedac-popdensity-yeargrid5yr-v4.11/
    Source: https://doi.org/10.6084/m9.figshare.19608594
    Source: https://doi.org/10.1038/s41597-022-01675-x
"""

import logging
import os
import zipfile
from typing import cast

import requests
import xarray

import retrievals.gridded
import utils.catalogue
import utils.geospatial
import utils.paths


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

    Raises
    ------
    ValueError
        If the year is not available.
    """
    if year not in utils.catalogue.GRIDDED_POPULATION_YEARS:
        raise ValueError(
            "year must be one of the available years: "
            f"{list(utils.catalogue.GRIDDED_POPULATION_YEARS)}."
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
        response = requests.get(url, timeout=60)

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


def _download_future_gridded_population(  # noqa: C901
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

    Raises
    ------
    ValueError
        If the scenario is not available.
    """
    if scenario not in utils.catalogue.SSP_SCENARIOS:
        raise ValueError(
            "ssp must be one of the following: "
            f"{list(utils.catalogue.SSP_SCENARIOS)}."
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
                url = "https://ndownloader.figshare.com/files/34829160"
            case "SSP2":
                url = "https://ndownloader.figshare.com/files/34829370"
            case "SSP3":
                url = "https://ndownloader.figshare.com/files/45894312"
            case "SSP4":
                url = "https://ndownloader.figshare.com/files/34829385"
            case "SSP5":
                url = "https://ndownloader.figshare.com/files/34829391"

        # Download the archive of about 2.5 GB into a file, in chunks,
        # and extract all population data from it.
        os.makedirs(downloaded_data_directory, exist_ok=True)
        archive_path = os.path.join(
            downloaded_data_directory, f"{scenario}.zip"
        )
        try:
            with requests.get(url, stream=True, timeout=60) as response:
                response.raise_for_status()
                with open(archive_path, "wb") as archive_file:
                    archive_file.writelines(
                        response.iter_content(chunk_size=1 << 20)
                    )
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(path=downloaded_data_directory)
        finally:
            if os.path.exists(archive_path):
                os.remove(archive_path)

        # Fix the folder name if necessary.
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
    raw_directory = utils.paths.get_gridded_folder("population", "raw")

    def get_global_grid(
        selected_year: int, selected_scenario: str | None
    ) -> xarray.DataArray:
        """
        Download, if needed, and read the global population of a year.

        Parameters
        ----------
        selected_year : int
            The year.
        selected_scenario : str | None
            The scenario, none for a historical year.

        Returns
        -------
        xarray.DataArray
            The population density of a historical year, or the
            population of a future year.
        """
        if selected_year <= 2020:
            _download_historical_gridded_population_density(
                raw_directory, selected_year
            )
        elif selected_year >= 2025 and selected_scenario is not None:
            _download_future_gridded_population(
                raw_directory, selected_scenario
            )
        return _read_population_dataset(
            raw_directory, selected_year, selected_scenario
        )

    def process(
        population: retrievals.gridded.Grid,
        bounds: retrievals.gridded.Bounds,
        selected_year: int,
    ) -> retrievals.gridded.Grid:
        """
        Get the population count at the resolution of the weather data.

        Parameters
        ----------
        population : retrievals.gridded.Grid
            The population density of a historical year, or the
            population of a future year, of a country or subdivision.
        bounds : retrievals.gridded.Bounds
            The bounds of the country or subdivision.
        selected_year : int
            The year.

        Returns
        -------
        retrievals.gridded.Grid
            The population, at 0.25 degrees.
        """
        population = cast(xarray.DataArray, population)
        if selected_year in utils.catalogue.GRIDDED_POPULATION_YEARS:
            # Convert the population density to population count.
            population = utils.geospatial.from_density_to_count(population)
        return utils.geospatial.coarsen(population, bounds)

    retrievals.gridded.run_retrieval(
        "population",
        "population",
        code,
        file,
        year,
        start_year,
        end_year,
        scenario,
        utils.catalogue.GRIDDED_POPULATION_YEARS,
        get_global_grid,
        process,
    )
