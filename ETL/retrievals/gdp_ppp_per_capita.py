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


def _get_years(
    year: int | None, start_year: int | None, end_year: int | None
) -> list[int]:
    """
    Get the list of years for which GDP data will be downloaded.

    Parameters
    ----------
    year : int | None
        The specific year for which GDP data is requested.
    start_year : int | None
        The start year of the range of GDP data to be downloaded.
    end_year : int | None
        The end year of the range of GDP data to be downloaded.

    Returns
    -------
    list[int]
        A list of years for which GDP data will be downloaded.
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
            f"start_year must be one of the available years: {available_years}."
        )
        assert end_year in available_years, (
            f"end_year must be one of the available years: {available_years}."
        )
        # Use the range of years from start_year to end_year.
        years = [y for y in available_years if start_year <= y <= end_year]
    else:
        # Use all available years.
        years = available_years

    return years


def _get_gdp_ppp_per_capita(year: int, ssp: int | None) -> xarray.DataArray:
    """
    Download GDP PPP per capita data.

    Parameters
    ----------
    year : int
        The year of the GDP PPP per capita data to be downloaded.
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.

    Returns
    -------
    xarray.DataArray
        The GDP PPP per capita data for the specified year and SSP.
    """
    # Define the path to the GDP PPP per capita data file.
    if year in list(range(2000, 2021)):
        relative_tif_path = f"025d/GDP{year}.tif"
    elif year in list(range(2025, 2101, 5)):
        assert ssp is not None, (
            "If year is in the range 2025-2100, ssp must be specified."
        )
        assert ssp in [1, 2, 3, 4, 5], (
            "ssp must be one of the following: 1, 2, 3, 4, 5."
        )
        relative_tif_path = f"025d/GDP{year}_ssp{ssp}.tif"

    # Define the URL for the GDP data.
    url = (
        "https://zenodo.org/records/7898409/files/"
        "GDP_025d%20(2000-2100).7z?download=1"
    )

    # Download the GDP PPP per capita.
    response = requests.get(url)
    response.raise_for_status()

    # Extract the archive from the response.
    with py7zr.SevenZipFile(io.BytesIO(response.content), mode="r") as archive:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract only the needed file to a temporary directory.
            archive.extract(path=temp_dir, targets=[relative_tif_path])

            # Open the GDP data for the specified year
            tif_path = os.path.join(temp_dir, relative_tif_path)
            global_gdp = xarray.open_dataarray(
                tif_path,
                engine="rasterio",
            )

        return global_gdp


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
        The code of the country or subdivision. If None, all available
        codes will be used.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "gdp_ppp_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of years for which GDP data will be downloaded.
    years = _get_years(year, start_year, end_year)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Loop over the years.
    for year in years:
        logging.info(f"Downloading GDP PPP per capita for the year {year}.")

        # Get the GDP data for the specified year and SSP.
        global_gdp_ppp_per_capita = _get_gdp_ppp_per_capita(year, ssp)

        # Harmonize the GDP data.
        global_gdp_ppp_per_capita = utils.geospatial.harmonize_coords(
            global_gdp_ppp_per_capita
        )

        # Clean the dataset.
        global_gdp_ppp_per_capita = utils.geospatial.clean_raster(
            global_gdp_ppp_per_capita, "gdp_ppp_per_capita"
        )

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            if year in list(range(2000, 2021)):
                file_path = os.path.join(
                    result_directory, f"{code}_0.25_deg_{year}.nc"
                )
            elif year in list(range(2025, 2101, 5)):
                file_path = os.path.join(
                    result_directory,
                    f"{code}_0.25_deg_{year}_ssp{ssp}.nc",
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
                    if year in list(range(2000, 2021)):
                        figure_name = f"gdp_{code}_{year}"
                    elif year in list(range(2025, 2101, 5)):
                        figure_name = f"gdp_{code}_{year}_ssp{ssp}"
                    # Make a plot of the GDP data.
                    utils.figures.simple_plot(gdp_ppp_per_capita, figure_name)

                logging.info(
                    f"GDP PPP per capita for {code} has been "
                    "successfully extracted and saved."
                )

            else:
                logging.info(
                    f"GDP PPP per capita for {code} already exists. "
                    "Skipping extraction."
                )
