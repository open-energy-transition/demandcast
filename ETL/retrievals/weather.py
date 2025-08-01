# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module downloads weather data from the Copernicus Climate Data
    Store (CDS). It then extracts the weather data for the countries and
    subdivisions of interest and saves it into NetCDF files. The country
    and subdivision code can be specified or a list can be provided as a
    yaml file. If no file or code is provided, the module will use all
    available codes. The variable of the weather data can be specified
    as a command line argument. The default variable is 2m_temperature.
    The year of the weather data can be specified as a command line
    argument. If no year is provided, the module will use all the years
    of available electricity demand data.
"""

import logging
import os

import pandas
import utils.copernicus
import utils.directories
import utils.entities
import utils.geospatial
import utils.shapes
import xarray
from tqdm import tqdm


def run_data_retrieval(
    from_global_data: bool,
    variable: str,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    code: str | None,
    file: str | None,
) -> None:
    """
    Run the weather data retrieval.

    This function retrieves weather data from the Copernicus Climate
    Data Store (CDS) for the countries and subdivisions of interest.
    The data is saved into NetCDF files in the specified directory.

    Parameters
    ----------
    from_global_data : bool
        If True, the function retrieves global weather data for the
        specified variable and year(s).
    variable : str
        The variable of the weather data to be downloaded.
    year : int | None
        The year of the weather data to be downloaded.
    start_year : int | None
        The start year of the range of years to be downloaded.
    end_year : int | None
        The end year of the range of years to be downloaded.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The path to the file containing the list of codes of the
        countries and subdivisions of interest.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "weather_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    if from_global_data:
        # Get the list of codes of the countries and subdivisions.
        codes = utils.entities.check_and_get_codes()

        # Determine which years to process
        if year is not None:
            # If the year is provided, use it.
            years = [year]
        elif (
            start_year is not None
            and end_year is not None
            and start_year <= end_year
        ):
            years = list(range(start_year, end_year + 1))
        else:
            years = [pandas.Timestamp.now().year]

        # Process each year
        for year in years:
            logging.info(f"Retrieving global {variable} data for {year}.")

            # Define the full file path for the global ERA5 data.
            global_file_path = os.path.join(
                result_directory, f"{year}_{variable}.nc"
            )

            # Check if the global file does not exist
            # or if the year is the current year (to overwrite)
            if not os.path.exists(global_file_path) or (
                os.path.exists(global_file_path)
                and year == pandas.Timestamp.now().year
            ):
                logging.info(f"Downloading global data for the year {year}.")

                # Download the global ERA5 data from CDS.
                utils.copernicus.download_data(
                    year, variable, global_file_path
                )
            else:
                logging.info(
                    f"Global data for the year {year} already exists. Using existing file."
                )

                global_data = xarray.open_dataarray(global_file_path)

                # Harmonize the coordinates of the global data.
                global_data = utils.geospatial.harmonize_coords(global_data)

                # Process each country/subdivision.
                for code in tqdm(
                    codes, desc=f"Processing countries for {year}"
                ):
                    logging.info(
                        f"Processing {variable} data for {code} for year {year}."
                    )

                    try:
                        # Define the file path for the country-specific
                        # data.
                        country_file_path = os.path.join(
                            result_directory, f"{code}_{variable}_{year}.nc"
                        )

                        # Check if the country file already exists
                        # or if the year is the current year (to
                        # overwrite).
                        if not os.path.exists(country_file_path) or (
                            os.path.exists(country_file_path)
                            and year == pandas.Timestamp.now().year
                        ):
                            logging.info(
                                f"Extracting data for {code} for the year {year}."
                            )

                            # Get the shape of the country or
                            # subdivision.
                            entity_shape = utils.shapes.get_entity_shape(
                                code, make_plot=False
                            )

                            # Get the lateral bounds for the shape
                            entity_bounds = utils.shapes.get_entity_bounds(
                                entity_shape
                            )  # West, South, East, North

                            # Extract data for the country or
                            # subdivision.
                            country_data = global_data.sel(
                                x=slice(entity_bounds[0], entity_bounds[2]),
                                y=slice(entity_bounds[1], entity_bounds[3]),
                            )

                            # Save the country-specific data
                            country_data.to_netcdf(country_file_path)

                            logging.info(
                                f"{variable} data for {code} for year {year} "
                                "has been successfully extracted and saved."
                            )
                        else:
                            logging.info(
                                f"Data for {code} for year {year} already "
                                "exists. Skipping extraction."
                            )

                    except Exception as e:
                        logging.error(
                            f"Error processing global data for year {year}: "
                            f"{str(e)}"
                        )
                        continue

            logging.info(
                f"Processing of {variable} data for year {year} has been "
                "completed."
            )

    else:
        # Get the list of codes of the countries and subdivisions of
        # interest.
        codes = utils.entities.check_and_get_codes(code=code, file_path=file)

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            logging.info(f"Retrieving {variable} data for {code}.")

            if year is not None:
                # If the year is provided, use it.
                years = [year]
            else:
                # Get the years of available data for the country or
                # subdivision of interest.
                years = utils.entities.get_available_years(code)

            # Get the shape of the country or subdivision.
            entity_shape = utils.shapes.get_entity_shape(code)

            # Get the lateral bounds of the country or subdivision.
            entity_bounds = utils.shapes.get_entity_bounds(
                entity_shape
            )  # West, South, East, North

            # Loop over the years.
            for year in years:
                # Define the full file paths of the ERA5 data.
                file_path = os.path.join(
                    result_directory, f"{code}_{variable}_{year}.nc"
                )

                # Check if the file does not exist or if the year is the
                # current year.
                if not os.path.exists(file_path) or (
                    os.path.exists(file_path)
                    and year == pandas.Timestamp.now().year
                ):
                    logging.info(f"Retrieving data for the year {year}.")

                    # Download the ERA5 data from the Copernicus Climate
                    # Data Store (CDS).
                    utils.copernicus.download_data(
                        year, variable, file_path, bounds=entity_bounds
                    )

                else:
                    logging.info(
                        f"Data for the year {year} already exists. Skipping "
                        "download."
                    )

            logging.info(
                f"{variable} data for {code} has been successfully retrieved "
                "and saved."
            )
