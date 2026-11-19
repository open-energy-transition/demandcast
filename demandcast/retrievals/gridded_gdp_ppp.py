"""
License: AGPL-3.0.

Description:

    This module downloads the global gridded GDP PPP of Zenodo, at a
    0.25-degree resolution, historical and for the SSP scenarios, and
    saves the grid of each country and subdivision of interest into
    NetCDF files.

    Source: https://zenodo.org/records/7898409
    Source: https://doi.org/10.1038/s41597-022-01300-x
"""

import logging
import os
import tempfile
from io import BytesIO

import py7zr
import requests
import xarray

import retrievals.gridded
import utils.catalogue
import utils.geospatial
import utils.paths


def _download_gdp_ppp(raw_directory: str) -> None:
    """
    Download GDP PPP data from Zenodo.

    Parameters
    ----------
    raw_directory : str
        The directory where the global GDP PPP data will be saved.

    Notes
    -----
    The archive is extracted into a temporary folder next to the
    directory, whose folder "025d" becomes the directory once complete,
    since the data is not downloaded again once the directory exists.
    """
    if not os.path.exists(raw_directory):
        logging.info("Downloading global gridded GDP PPP data from Zenodo.")

        url = "https://zenodo.org/records/7898409/files/GDP_025d%20(2000-2100).7z?download=1"

        response = requests.get(url, timeout=60)

        response.raise_for_status()

        os.makedirs(os.path.dirname(raw_directory), exist_ok=True)
        with (
            tempfile.TemporaryDirectory(
                dir=os.path.dirname(raw_directory)
            ) as temporary_folder,
            py7zr.SevenZipFile(BytesIO(response.content), mode="r") as archive,
        ):
            archive.extractall(path=temporary_folder)
            os.replace(os.path.join(temporary_folder, "025d"), raw_directory)

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
    file_path = os.path.join(
        raw_directory,
        f"GDP{year_scenario.lower()}.tif",
    )

    global_gdp_ppp = xarray.open_dataarray(file_path)

    global_gdp_ppp = utils.geospatial.harmonize_coords(global_gdp_ppp)

    return utils.geospatial.clean_raster(global_gdp_ppp, "gdp_ppp")


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract gridded GDP PPP data.

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
