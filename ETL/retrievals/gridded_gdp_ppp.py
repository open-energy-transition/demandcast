# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract GDP PPP data
    from a Zenodo repository. The GDP data is extracted for the
    countries and subdivisions of interest at a 0.25-degree resolution
    and saved into NetCDF files.

    Source: https://zenodo.org/records/7898409
    Source: https://doi.org/10.1038/s41597-022-01300-x
"""

import io
import logging
import os

import py7zr
import requests
import utils.directories
import utils.entities
import utils.figures
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray


def _download_gdp_ppp(result_directory: str) -> None:
    """
    Download GDP PPP data from Zenodo.

    Parameters
    ----------
    result_directory : str
        The directory where the GDP PPP data will be saved.
    """
    # Check if the file already exists.
    if not os.path.exists(os.path.join(result_directory, "downloads")):
        logging.info("Downloading GDP PPP data from Zenodo.")

        # Define the URL to download the GDP PPP data.
        url = "https://zenodo.org/records/7898409/files/GDP_025d%20(2000-2100).7z?download=1"  # noqa: W505

        # Fetch the data from the URL.
        response = requests.get(url)

        # Check if the request was successful.
        response.raise_for_status()

        # Extract all files from the 7z archive.
        with py7zr.SevenZipFile(
            io.BytesIO(response.content), mode="r"
        ) as archive:
            # List the contents of the archive.
            archive.extractall(path=result_directory)

        os.rename(
            os.path.join(result_directory, "025d"),
            os.path.join(result_directory, "downloads"),
        )
    else:
        logging.info("GDP PPP data already exists. Skipping download.")


def _read_gdp_ppp(
    result_directory: str, year_scenario: str
) -> xarray.DataArray:
    """
    Read the GDP PPP for the specified year and scenario.

    Parameters
    ----------
    result_directory : str
        The directory where the GDP PPP data is stored.
    year_scenario : str
        The year and SSP scenario for which the GDP data is to be read.

    Returns
    -------
    xarray.DataArray
        The GDP PPP data for the specified year and SSP.
    """
    # Define the file path of the GDP PPP data.
    file_path = os.path.join(
        result_directory,
        "downloads",
        f"GDP{year_scenario.lower()}.tif",
    )

    # Read the GDP PPP data.
    global_gdp_ppp = xarray.open_dataarray(file_path)

    # Harmonize the coordinates of the GDP PPP data.
    global_gdp_ppp = utils.geospatial.harmonize_coords(global_gdp_ppp)

    # Clean the dataset and return it.
    return utils.geospatial.clean_raster(global_gdp_ppp, "gdp_ppp")


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
):
    """
    Download and extract gridded GDP PPP data.

    This function downloads GDP PPP data from a Zenodo repository,
    extracts the data for the specified countries and subdivisions of
    interest at a 0.25-degree resolution, and saves the data into NetCDF
    files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the GDP PPP data to be retrieved.
    start_year : int | None
        The start year of the range of GDP PPP data to be
        retrieved.
    end_year : int | None
        The end year of the range of GDP PPP data to be
        retrieved.
    scenario : str | None
        The scenario of the GDP PPP data to be retrieved.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "gridded_gdp_ppp_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Download the GDP PPP data from Zenodo.
    _download_gdp_ppp(result_directory)

    # Define the available years for historical GDP data.
    available_historical_years = list(range(2000, 2021))

    # Define the available years for future GDP data.
    available_future_years = list(range(2025, 2101, 5))

    # Define the available scenarios for the GDP data.
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

    # Loop over the years and scenarios.
    for year, scenario in year_scenario_list:
        logging.info(
            f"Processing GDP PPP data for the year {year}"
            + (f" and scenario {scenario}." if scenario else ".")
        )

        # Define the year and scenario string for the file name.
        year_scenario = f"{year}_{scenario}" if scenario else str(year)

        # Read the GDP data for the specified year and SSP.
        global_gdp_ppp = _read_gdp_ppp(result_directory, year_scenario)

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            file_path = os.path.join(
                result_directory,
                f"{code}_0.25_deg_{year_scenario}.nc",
            )

            if not os.path.exists(file_path):
                logging.info(f"Extracting GDP PPP data for {code}.")

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    code, make_plot=False
                )

                # Get the lateral bounds of the country or subdivision
                # of interest.
                entity_bounds = utils.shapes.get_entity_bounds(
                    entity_shape
                )  # West, South, East, North

                # Select the GDP PPP data within the bounds of the
                # country or subdivision.
                gdp_ppp = global_gdp_ppp.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                # Save the GDP PPP data to a NetCDF file.
                gdp_ppp.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the GDP PPP data.
                    utils.figures.simple_plot(
                        gdp_ppp,
                        f"gdp_ppp_{code}_{year_scenario}",
                    )

                logging.info(
                    f"GDP PPP data for {code} has been "
                    "successfully extracted and saved."
                )

            else:
                logging.info(
                    f"GDP PPP data for {code} already exists. "
                    "Skipping extraction."
                )
