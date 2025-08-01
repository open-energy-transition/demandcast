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

import retrievals.weather
import utils.copernicus
import utils.directories
import utils.entities
import utils.geospatial
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
    retrievals.weather.run_data_retrieval(
        args.from_global_data,
        args.variable,
        args.year,
        args.start_year,
        args.end_year,
        args.code,
        args.file,
    )
