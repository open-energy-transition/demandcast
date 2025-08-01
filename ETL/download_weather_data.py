# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads weather data from the Copernicus Climate Data
    Store (CDS). It then extracts the weather data for the countries and
    subdivisions of interest and saves it into NetCDF files. The country
    and subdivision code can be specified or a list can be provided as a
    yaml file. If no file or code is provided, the script will use all
    available codes. The variable of the weather data can be specified
    as a command line argument. The default variable is 2m_temperature.
    The year of the weather data can be specified as a command line
    argument. If no year is provided, the script will use all the years
    of available electricity demand data.
"""

import argparse
import logging
import os
from datetime import datetime

import pandas
import utils.copernicus
import utils.directories
import utils.entities
import utils.shapes


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
            "Download and process weather data from the Copernicus Climate "
            "Data Store (CDS). You can specify the country or subdivision "
            "code, provide a file containing the list of codes, or use all "
            "available codes. The variable and year of the weather data can "
            "also be specified."
        )
    )

    # Add the command line arguments.
    parser.add_argument(
        "-c",
        "--code",
        type=str,
        help=(
            'The ISO Alpha-2 code (example: "FR") or a combination of ISO '
            'Alpha-2 code and subdivision code (example: "US_CAL")'
        ),
        required=False,
    )
    parser.add_argument(
        "-f",
        "--file",
        type=str,
        help=(
            "The path to the yaml file containing the list of codes of the "
            "countries and subdivisions of interest"
        ),
        required=False,
    )
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
        help="Year of the weather data to be downloaded",
        required=False,
    )

    # Read the arguments from the command line.
    args = parser.parse_args()

    return args


def run_data_retrieval(args: argparse.Namespace) -> None:
    """
    Run the weather data retrieval.

    This function retrieves weather data from the Copernicus Climate
    Data Store (CDS) for the countries and subdivisions of interest.
    The data is saved into NetCDF files in the specified directory.

    Parameters
    ----------
    args : argparse.Namespace
        The command line arguments.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "weather_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(
        code=args.code, file_path=args.file
    )

    # Loop over the countries and subdivisions of interest.
    for code in codes:
        logging.info(f"Retrieving {args.variable} data for {code}.")

        if args.year is not None:
            # If the year is provided, use it.
            years = [args.year]
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
                result_directory, f"{code}_{args.variable}_{year}.nc"
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
                    year, args.variable, file_path, bounds=entity_bounds
                )

            else:
                logging.info(
                    f"Data for the year {year} already exists. Skipping "
                    "download."
                )

        logging.info(
            f"{args.variable} data for {code} has been successfully retrieved "
            "and saved."
        )


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Set up the logging configuration.
    log_file_name = (
        "weather_data_" + datetime.now().strftime("%Y%m%d_%H%M") + ".log"
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
