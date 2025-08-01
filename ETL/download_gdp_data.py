# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads GPD data from a Zenodo repository. It then
    extracts the GDP data for the countries and subdivisions of interest
    at a 0.25-degree resolution, and saves it into NetCDF files. The
    year of the GPD data can be specified as a command line argument.
    The default year is 2020.

    Source: https://zenodo.org/records/7898409
    Source: https://doi.org/10.1038/s41597-022-01300-x

"""

import argparse
import logging
import os
from datetime import datetime

import retrievals.gdp
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
            "Download and process GPD data from a Zenodo repository. You can "
            "specify the country or subdivision code, provide a file "
            "containing the list of codes, or use all available codes. The "
            "year of the GDP data can also be specified."
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
        choices=list(range(2000, 2021)),
        help="Year of the GDP data to be downloaded",
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
        "gdp_data_" + datetime.now().strftime("%Y%m%d_%H%M") + ".log"
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
    retrievals.gdp.run_data_retrieval(args.year, args.code, args.file)
