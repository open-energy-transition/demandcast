# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads global weather data from the
    Copernicus Climate Data Store (CDS) for entire years,
    then processes it to create country-specific files.
    It extracts the variable, default is 2m_temperature,
    for all countries and subdivisions of interest,
    and saves it into separate NetCDF files.
    The variable of the weather data can be specified,
    along with the specific year or range of years.
    If no year is provided, the script will use the current year.
"""

import argparse
import logging
import os
from datetime import datetime

import pandas
import utils.copernicus
import utils.directories
import utils.entities
import utils.geospatial
import utils.shapes
import xarray
from tqdm import tqdm


def read_command_line_arguments() -> argparse.Namespace:
    """
    Create a parser for the command line arguments and read them.

    Returns
    -------
    args : argparse.Namespace
        The command line arguments.
    """
    # Create a parser for the command line arguments.
    parser = argparse.ArgumentParser(
        description=(
            "Download global weather data for entire years from the Copernicus Climate "
            "Data Store (CDS), then process it to create country-specific files. "
            "You can specify a single year, a range of years, or use the current year "
            "by default. The variable of the weather data can also be specified."
        )
    )

    # Add the command line arguments.
    parser.add_argument(
        "-v",
        "--variable",
        type=str,
        help="Variable of the weather data to be downloaded",
        default="2m_temperature",
        required=False,
    )
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        help="Specific year of the weather data to be downloaded",
        required=False,
    )
    parser.add_argument(
        "-y1",
        "--start-year",
        type=int,
        help="Start year for a range of years to download",
        required=False,
    )
    parser.add_argument(
        "-y2",
        "--end-year",
        type=int,
        help="End year for a range of years to download (inclusive)",
        required=False,
    )

    # Read the arguments from the command line.
    args = parser.parse_args()

    return args


def run_data_retrieval(args: argparse.Namespace) -> None:
    """
    Run the weather data retrieval.

    This function retrieves global weather data from the
    Copernicus Climate Data Store (CDS) for entire years,
    then processes it to create country-specific files for
    all countries and subdivisions of interest.
    The data is saved into NetCDF files in the specified directory.

    Parameters
    ----------
    args : argparse.Namespace
        The command line arguments.
    """
    # Get the directory to store the weather data.
    result_directory = utils.directories.read_folders_structure()[
        "weather_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions.
    codes = utils.entities.check_and_get_codes()

    # Determine which years to process
    if args.year is not None:
        # If the year is provided, use it.
        years = [args.year]
    elif (
        args.start_year is not None
        and args.end_year is not None
        and args.start_year <= args.end_year
    ):
        years = list(range(args.start_year, args.end_year + 1))
    else:
        years = [pandas.Timestamp.now().year]

    # Process each year
    for year in years:
        logging.info(f"Retrieving global {args.variable} data for {year}.")

        # Define the full file path for the global ERA5 data.
        global_file_path = os.path.join(
            result_directory, f"{year}_{args.variable}.nc"
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
                year, args.variable, global_file_path
            )
        else:
            logging.info(
                f"Global data for the year {year} already exists. Using existing file."
            )

            global_data = xarray.open_dataarray(global_file_path)

            # Harmonize the coordinates of the global data.
            global_data = utils.geospatial.harmonize_coords(global_data)

            # Process each country/subdivision
            for code in tqdm(codes, desc=f"Processing countries for {year}"):
                logging.info(
                    f"Processing {args.variable} data for {code} for year {year}."
                )

                try:
                    # Define the file path for the country-specific data
                    country_file_path = os.path.join(
                        result_directory, f"{code}_{args.variable}_{year}.nc"
                    )

                    # Check if the country file already exists
                    # or if the year is the current year (to overwrite)
                    if not os.path.exists(country_file_path) or (
                        os.path.exists(country_file_path)
                        and year == pandas.Timestamp.now().year
                    ):
                        logging.info(
                            f"Extracting data for {code} for the year {year}."
                        )

                        # Get the shape of the country or subdivision
                        entity_shape = utils.shapes.get_entity_shape(
                            code, make_plot=False
                        )

                        # Get the lateral bounds for the shape
                        entity_bounds = utils.shapes.get_entity_bounds(
                            entity_shape
                        )  # West, South, East, North

                        # Extract data for the country or subdivision
                        country_data = global_data.sel(
                            x=slice(entity_bounds[0], entity_bounds[2]),
                            y=slice(entity_bounds[1], entity_bounds[3]),
                        )

                        # Save the country-specific data
                        country_data.to_netcdf(country_file_path)

                        logging.info(
                            f"{args.variable} data for {code} for year {year} has been successfully extracted and saved."
                        )
                    else:
                        logging.info(
                            f"Data for {code} for year {year} already exists. Skipping extraction."
                        )

                except Exception as e:
                    logging.error(
                        f"Error processing global data for year {year}: {str(e)}"
                    )
                    continue

        logging.info(
            f"Processing of {args.variable} data for year {year} has been completed."
        )


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Set up the logging configuration.
    log_file_name = (
        "weather_years_" + datetime.now().strftime("%Y%m%d_%H%M") + ".log"
    )
    log_files_directory = utils.directories.read_folders_structure()[
        "log_files_folder"
    ]
    os.makedirs(log_files_directory, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_files_directory, log_file_name),
        level=logging.INFO,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Run the data retrieval.
    run_data_retrieval(args)
