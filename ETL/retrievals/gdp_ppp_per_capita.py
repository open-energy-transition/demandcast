# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module downloads GPD data from a Zenodo repository. It then
    extracts the GDP data for the countries and subdivisions of interest
    at a 0.25-degree resolution, and saves it into NetCDF files. The
    year of the GPD data can be specified as a command line argument.

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


def run_data_retrieval(
    year: int | None,
    code: str | None,
    file: str | None,
):
    """
    Download and extract GDP data.

    This function downloads GDP data from a Zenodo repository, extracts
    the GDP data for the countries and subdivisions of interest at a
    0.25-degree resolution, and saves it into NetCDF files.

    Parameters
    ----------
    year : int | None
        The year of the GDP data to be downloaded.
    code : str | None
        The code of the country or subdivision. If None, all available
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "gdp_ppp_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    if year is not None:
        years = [year]
    else:
        years = list(range(2000, 2021))

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Loop over the years.
    for year in years:
        logging.info(f"Downloading GDP data for the year {year}.")

        # Fetch the GDP data from Zenodo.
        response = requests.get(
            "https://zenodo.org/records/7898409/files/"
            "GDP_025d%20(2000-2100).7z?download=1"
        )

        # Extract the archive from the response.
        with py7zr.SevenZipFile(
            io.BytesIO(response.content), mode="r"
        ) as archive:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract only the file we need to a temporary directory
                archive.extract(path=temp_dir, targets=[f"025d/GDP{year}.tif"])

                # Open the GDP data for the specified year
                tif_path = os.path.join(temp_dir, f"025d/GDP{year}.tif")
                global_gdp = xarray.open_dataarray(
                    tif_path,
                    engine="rasterio",
                )

        # Harmonize the GDP data.
        global_gdp = utils.geospatial.harmonize_coords(global_gdp)

        # Clean the dataset.
        global_gdp = utils.geospatial.clean_raster(global_gdp, "gdp")

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            file_path = os.path.join(
                result_directory, f"{code}_0.25_deg_{year}.nc"
            )

            if not os.path.exists(file_path):
                logging.info(f"Extracting GDP data of {code}.")

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
                gdp = global_gdp.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                # Save the GDP data.
                gdp.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the GDP data.
                    utils.figures.simple_plot(gdp, f"gdp_{code}_{year}")

                logging.info(
                    f"GDP data for {code} has been successfully extracted and "
                    "saved."
                )

            else:
                logging.info(
                    f"GDP data for {code} already exists. Skipping extraction."
                )
