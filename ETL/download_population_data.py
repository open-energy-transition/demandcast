# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads population density data from SEDAC
    (Socioeconomic Data and Applications Center). It then extracts the
    population density data for the countries and subdivisions of
    interest, coarsens the data to a 0.25-degree resolution, and saves
    it into NetCDF files. The country and subdivision code can be
    specified or a list can be provided as a yaml file. If no file or
    code is provided, the script will use all available codes. The year
    of the population density data can be specified as a command line
    argument. The default year is 2020.
"""

import argparse
import logging
import os
from datetime import datetime

import retrievals.population
import utils.directories
import utils.entities
import utils.figures
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
            "Download and process population density data from SEDAC. You can "
            "specify the country or subdivision code, provide a file "
            "containing the list of codes, or use all available codes. The "
            "year of the population density data can also be specified."
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
        "-y",
        "--year",
        type=int,
        choices=[2000, 2005, 2010, 2015, 2020],
        help="Year of the population density data to be downloaded",
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
        "population_density_data_"
        + datetime.now().strftime("%Y%m%d_%H%M")
        + ".log"
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
    retrievals.population.run_data_retrieval(args.year, args.code, args.file)
