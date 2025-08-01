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
"""

import logging
import os

import utils.directories
import utils.entities
import utils.figures
import utils.geospatial
import utils.shapes
import xarray


def run_data_retrieval(
    year: int | None, code: str | None, file: str | None
) -> None:
    """
    Download and extract the population density data.

    This function downloads population density data from SEDAC,
    extracts the population density data for the countries and
    subdivisions of interest, coarsens the data to a 0.25-degree
    resolution, and saves it into NetCDF files.

    Parameters
    ----------
    year : int | None
        The year of the population density data to be downloaded.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The path to the file containing the list of codes of the
        countries and subdivisions of interest.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "population_density_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    if year is not None:
        years = [year]
    else:
        years = [2000, 2005, 2010, 2015, 2020]

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Loop over the years.
    for year in years:
        logging.info(
            f"Downloading population density data for the year {year}."
        )

        # Define the URL of the population density data.
        url = (
            "https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/"
            f"gpw_v4_population_density_rev11_{year}_30_sec_{year}.tif"
        )

        # Download the population density data.
        global_population_density = xarray.open_dataarray(
            url, engine="rasterio"
        )

        # Harmonize the population density data.
        global_population_density = utils.geospatial.harmonize_coords(
            global_population_density
        )

        # Clean the dataset.
        global_population_density = utils.geospatial.clean_raster(
            global_population_density, "population_density"
        )

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            file_path = os.path.join(
                result_directory, f"{code}_0.25_deg_{year}.nc"
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
                population_density = global_population_density.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                # Coarsen the population density data to the same
                # resolution as the weather data.
                population_density = utils.geospatial.coarsen(
                    population_density, entity_bounds
                )

                # Save the population density data.
                population_density.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the population density data.
                    utils.figures.simple_plot(
                        population_density,
                        f"population_density_{code}_{year}",
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
