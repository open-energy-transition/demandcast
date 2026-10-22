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
import utils.geospatial
import utils.paths
import xarray

import retrievals.gridded


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
    # Download the GDP PPP data from Zenodo.
    raw_directory = utils.paths.get_gridded_folder("gdp_ppp", "raw")
    os.makedirs(os.path.dirname(raw_directory), exist_ok=True)
    _download_gdp_ppp(raw_directory)

    retrievals.gridded.run_retrieval(
        "gdp_ppp",
        "GDP PPP",
        code,
        file,
        year,
        start_year,
        end_year,
        scenario,
        utils.catalogue.GRIDDED_GDP_PPP_YEARS,
        lambda selected_year, selected_scenario: _read_gdp_ppp(
            raw_directory,
            f"{selected_year}_{selected_scenario}"
            if selected_scenario
            else str(selected_year),
        ),
        lambda gdp_ppp, _bounds, _year: gdp_ppp,
    )
