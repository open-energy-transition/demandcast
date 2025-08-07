# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module downloads GPD PPP per capita from a Zenodo repository.
    It then extracts the GDP data for the countries and subdivisions of
    interest at a 0.25-degree resolution, and saves it into NetCDF
    files.

    Source: https://zenodo.org/records/7898409
    Source: https://doi.org/10.1038/s41597-022-01300-x

"""

import io
import logging
import os
import tempfile

import py7zr
import requests
import utils.directories
import utils.entities
import utils.figures
import utils.geospatial
import utils.shapes
import xarray


def _get_year_and_ssp_combinations(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    ssp: int | None,
) -> list[str]:
    """
    Get the list of years and SSP combinations.

    Parameters
    ----------
    year : int | None
        The specific year for which GDP data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which GDP data is to be
        downloaded.
    end_year : int | None
        The end year of the range of years for which GDP data is to be
        downloaded.
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.

    Returns
    -------
    year_ssp : list[str]
        A list of strings representing the years and SSP combinations.
    """
    # Define the available years for the GDP data.
    available_years = list(range(2000, 2021)) + list(range(2025, 2101, 5))

    if year is not None:
        assert start_year is None and end_year is None, (
            "If year is specified, start_year and end_year must be None."
        )
        assert year in available_years, (
            f"year must be one of the available years: {available_years}."
        )
        # Use the specified year.
        years = [year]
    elif start_year is not None and end_year is not None:
        assert start_year < end_year, "start_year must be less than end_year."
        assert start_year in available_years, (
            "start_year must be one of the available years: "
            f"{available_years}."
        )
        assert end_year in available_years, (
            f"end_year must be one of the available years: {available_years}."
        )
        # Use the range of years from start_year to end_year.
        years = [y for y in available_years if start_year <= y <= end_year]
    else:
        # Use all available years.
        years = available_years

    # Define the available SSPs.
    available_ssps = [1, 2, 3, 4, 5]

    if ssp is not None:
        assert ssp in available_ssps, (
            f"ssp must be one of the following: {available_ssps}."
        )
        # Use the specified SSP.
        ssps = [ssp]
    else:
        # Use all available SSPs.
        ssps = available_ssps

    # Create a list of year and SSP combinations.
    year_ssp_list = []
    for year in years:
        if year <= 2020:
            # For years 2000-2020, no SSP is needed.
            year_ssp_list.append(f"{year}")
        elif year >= 2025:
            # For years 2025-2100, SSP is needed.
            for ssp in ssps:
                year_ssp_list.append(f"{year}_ssp{ssp}")

    return year_ssp_list


def _download_gdp_ppp_per_capita() -> requests.Response:
    """
    Download GDP PPP per capita data from Zenodo.

    Returns
    -------
    response : requests.Response
        The response object containing the GDP PPP per capita data.
    """
    logging.info("Downloading GDP PPP per capita data from Zenodo.")

    # Define the URL to download the GDP PPP per capita data.
    url = "https://zenodo.org/records/7898409/files/GDP_025d%20(2000-2100).7z?download=1"

    # Fetch the data from the URL.
    response = requests.get(url)

    # Check if the request was successful.
    response.raise_for_status()

    return response


def _extract_gdp_ppp_per_capita(
    response: requests.Response, year_ssp: str
) -> xarray.DataArray:
    """
    Extract GDP PPP per capita data for a specific year and SSP.

    Parameters
    ----------
    response : requests.Response
        The response object containing the GDP PPP per capita data.
    year_ssp : str
        The year and SSP combination for which GDP PPP per capita data
        is to be downloaded.

    Returns
    -------
    xarray.DataArray
        The GDP PPP per capita data for the specified year and SSP.
    """
    # Define the path to the GDP PPP per capita data file.
    relative_tif_path = f"025d/GDP{year_ssp}.tif"

    # Extract the archive from the response.
    with py7zr.SevenZipFile(io.BytesIO(response.content), mode="r") as archive:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract only the needed file to a temporary directory.
            archive.extract(path=temp_dir, targets=[relative_tif_path])

            # Open the GDP data for the specified year
            tif_path = os.path.join(temp_dir, relative_tif_path)
            global_gdp_ppp_per_capita = xarray.open_dataarray(
                tif_path,
                engine="rasterio",
            )

            # Harmonize the GDP data.
            global_gdp_ppp_per_capita = utils.geospatial.harmonize_coords(
                global_gdp_ppp_per_capita
            )

            # Clean the dataset.
            global_gdp_ppp_per_capita = utils.geospatial.clean_raster(
                global_gdp_ppp_per_capita, "gdp_ppp_per_capita"
            )

            return global_gdp_ppp_per_capita


def run_data_retrieval(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    ssp: int | None,
    code: str | None,
    file: str | None,
):
    """
    Download and extract GDP PPP per capita data.

    This function downloads GDP data from a Zenodo repository, extracts
    the GDP data for the countries and subdivisions of interest at a
    0.25-degree resolution, and saves it into NetCDF files.

    Parameters
    ----------
    year : int | None
        The year of the GDP PPP per capita data to be downloaded.
    start_year : int | None
        The start year of the range of GDP PPP per capita data to be
        downloaded.
    end_year : int | None
        The end year of the range of GDP PPP per capita data to be
        downloaded.
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "gdp_ppp_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of years and SSP combinations.
    year_ssp_list = _get_year_and_ssp_combinations(
        year, start_year, end_year, ssp
    )

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Get the GDP PPP per capita data from Zenodo.
    dataset = _download_gdp_ppp_per_capita()

    # Loop over the years.
    for year_ssp in year_ssp_list:
        logging.info(
            "Extracting GDP PPP per capita for "
            f"the year {year_ssp.split('_')[0]}"
            + (
                f" and SSP {year_ssp.split('_ssp')[1]}."
                if "ssp" in year_ssp
                else "."
            )
        )

        # Extract the GDP data for the specified year and SSP.
        global_gdp_ppp_per_capita = _extract_gdp_ppp_per_capita(
            dataset, year_ssp
        )

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            file_path = os.path.join(
                result_directory, f"{code}_0.25_deg_{year_ssp}.nc"
            )

            if not os.path.exists(file_path):
                logging.info(f"Extracting GDP PPP per capita for {code}.")

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    code, make_plot=False
                )

                # Get the lateral bounds of the country or subdivision
                # of interest.
                entity_bounds = utils.shapes.get_entity_bounds(
                    entity_shape
                )  # West, South, East, North

                # Select the GDP data for the country or subdivision of
                # interest.
                gdp_ppp_per_capita = global_gdp_ppp_per_capita.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                # Save the GDP data.
                gdp_ppp_per_capita.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the GDP data.
                    utils.figures.simple_plot(
                        gdp_ppp_per_capita, f"gdp_{code}_{year_ssp}"
                    )

                logging.info(
                    f"GDP PPP per capita for {code} has been "
                    "successfully extracted and saved."
                )

            else:
                logging.info(
                    f"GDP PPP per capita for {code} already exists. "
                    "Skipping extraction."
                )
