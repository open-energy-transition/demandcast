# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads hourly or sub-hourly electricity demand data
    from various data sources. Users can specify a data source and
    optionally provide a country or subdivision code to retrieve
    specific data. The retrieved data is cleaned and saved in a
    structured format for further analysis. The script also supports
    uploading the data to Google Cloud Storage (GCS) if a bucket name
    is provided.
"""

import argparse
import logging
import os
from datetime import datetime

import retrievals.electricity_demand
import utils.directories
import utils.entities
import utils.time_series
import utils.uploader


def _str_to_bool(argument: bool | str):
    """
    Convert a string or boolean argument to a boolean value.

    Parameters
    ----------
    argument : bool or str
        The argument to convert.

    Returns
    -------
    bool
        The converted boolean value.

    Raises
    ------
    argparse.ArgumentTypeError
        If the argument is not a valid boolean value.
    """
    if isinstance(argument, bool):
        return argument
    elif argument.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif argument.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


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
            "Download electricity demand data from the specified data source. "
            "You can specify the country or subdivision code or provide a "
            "file containing the list of codes.  If no code or file is "
            "provided, the data retrieval will be run for all the countries "
            "and subdivisions available on the data source website."
        )
    )

    # Add the command line arguments.
    parser.add_argument(
        "data_source",
        type=str,
        choices=utils.entities.read_data_sources(),
        help=(
            "The acronym of the data source as defined in the retrieval "
            'modules (example: "ENTSOE")'
        ),
    )
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
            "countries and subdivisions of interest."
        ),
        required=False,
    )
    parser.add_argument(
        "-g",
        "--upload_to_gcs",
        type=str,
        help=(
            "The bucket name of the Google Cloud Storage (GCS) to upload the "
            "data"
        ),
        required=False,
    )
    parser.add_argument(
        "-z",
        "--upload_to_zenodo",
        help="Whether to upload the data to Zenodo.",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-p",
        "--publish_to_zenodo",
        help="Whether to publish the data to Zenodo.",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-m",
        "--made_by_oet",
        type=_str_to_bool,
        help=(
            "Whether the data was retrieved or created by Open Energy "
            "Transition."
        ),
        required=True,
    )

    # Read the arguments from the command line.
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    # Read the command line arguments.
    args = read_command_line_arguments()

    # Set up the logging configuration.
    log_file_name = (
        f"electricity_data_from_{args.data_source}_"
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
    retrievals.electricity_demand.run_data_retrieval(
        args.code,
        args.data_source,
        args.file,
        args.upload_to_gcs,
        args.upload_to_zenodo,
        args.publish_to_zenodo,
        args.made_by_oet,
    )
