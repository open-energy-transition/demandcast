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

import retrievals.weather
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
    retrievals.weather.run_data_retrieval(
        args.from_global_data,
        args.variable,
        args.year,
        args.start_year,
        args.end_year,
        args.code,
        args.file,
    )
