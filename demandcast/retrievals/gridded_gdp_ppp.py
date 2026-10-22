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

import logging
import os
from io import BytesIO

import py7zr
import requests
import utils.catalogue
import utils.entities
import utils.figures
import utils.geospatial
import utils.paths
import utils.scenarios
import utils.shapes
import xarray
from tqdm import tqdm


def _download_gdp_ppp(raw_directory: str) -> None:
    """
    Download GDP PPP data from Zenodo.

    Parameters
    ----------
    raw_directory : str
        The directory where the global GDP PPP data will be saved.
    """
    # Check if the file already exists.
    if not os.path.exists(raw_directory):
        logging.info("Downloading global gridded GDP PPP data from Zenodo.")

        # Define the URL to download the GDP PPP data.
        url = "https://zenodo.org/records/7898409/files/GDP_025d%20(2000-2100).7z?download=1"

        # Fetch the data from the URL.
        response = requests.get(url, timeout=60)

        # Check if the request was successful.
        response.raise_for_status()

        # Extract all files from the 7z archive.
        with py7zr.SevenZipFile(
            BytesIO(response.content), mode="r"
        ) as archive:
            # List the contents of the archive.
            archive.extractall(path=os.path.dirname(raw_directory))

        os.rename(
            os.path.join(os.path.dirname(raw_directory), "025d"),
            raw_directory,
        )

        logging.info(
            "Global gridded GDP PPP data has been downloaded successfully."
        )
    else:
        logging.info(
            "Global gridded GDP PPP data already exists. Skipping download."
        )


def _read_gdp_ppp(raw_directory: str, year_scenario: str) -> xarray.DataArray:
    """
    Read the GDP PPP for the specified year and scenario.

    Parameters
    ----------
    raw_directory : str
        The directory where the global GDP PPP data is stored.
    year_scenario : str
        The year and SSP scenario for which the GDP data is to be read.

    Returns
    -------
    xarray.DataArray
        The GDP PPP data for the specified year and SSP.
    """
    # Define the file path of the GDP PPP data.
    file_path = os.path.join(
        raw_directory,
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
    # Get the directory to store the GDP data.
    result_directory = utils.paths.get_gridded_folder("gdp_ppp", "processed")
    os.makedirs(result_directory, exist_ok=True)

    # Download the GDP PPP data from Zenodo.
    raw_directory = utils.paths.get_gridded_folder("gdp_ppp", "raw")
    _download_gdp_ppp(raw_directory)

    # Get the list of year and scenario combinations.
    year_scenario_list = utils.scenarios.get_year_and_scenario_combinations(
        year,
        start_year,
        end_year,
        list(utils.catalogue.GRIDDED_GDP_PPP_YEARS),
        list(utils.catalogue.PROJECTION_YEARS),
        scenario,
        list(utils.catalogue.SSP_SCENARIOS),
    )

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )

    # Loop over the years and scenarios.
    for selected_year, selected_scenario in tqdm(
        year_scenario_list, desc="Years and scenarios"
    ):
        logging.info(
            f"Processing gridded GDP PPP data for the year {selected_year}"
            + (
                f" and scenario {selected_scenario}."
                if selected_scenario
                else "."
            )
        )

        # Define the year and scenario string for the file name.
        year_scenario = (
            f"{selected_year}_{selected_scenario}"
            if selected_scenario
            else str(selected_year)
        )

        # Read the GDP data for the specified year and SSP.
        global_gdp_ppp = _read_gdp_ppp(raw_directory, year_scenario)

        # Loop over the countries and subdivisions of interest.
        for entity_code in codes:
            # Define the file path of the GDP data for the country or
            # subdivision.
            file_path = os.path.join(
                result_directory,
                f"{entity_code}_0.25_deg_{year_scenario}.nc",
            )

            if not os.path.exists(file_path):
                logging.info(
                    f"Extracting gridded GDP PPP data for {entity_code}."
                )

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    entity_code, make_plot=False
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
                        f"gdp_ppp_{entity_code}_{year_scenario}",
                    )

                logging.info(
                    f"Gridded GDP PPP data for {entity_code} has been "
                    "successfully extracted and saved."
                )

            else:
                logging.info(
                    f"Gridded GDP PPP data for {entity_code} already exists. "
                    "Skipping extraction."
                )
