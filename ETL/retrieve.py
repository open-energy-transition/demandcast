# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads
"""

import argparse
import logging
import os
from datetime import datetime

import retrievals.annual_electricity_demand_per_capita
import retrievals.electricity_demand
import retrievals.gdp_ppp_per_capita
import retrievals.gridded_gdp_ppp
import retrievals.gridded_population
import retrievals.population
import retrievals.temperature
import retrievals.weather
import utils.directories
import utils.entities


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
    parser = argparse.ArgumentParser(description=("Download "))

    # Add the command line arguments.
    parser.add_argument(
        "variable",
        type=str,
        choices=[
            "electricity_demand",
            "annual_electricity_demand_per_capita",
            "population",
            "gridded_population",
            "gdp_ppp_per_capita",
            "gridded_gdp_ppp",
            "gridded_weather",
            "temperature",
        ],
        help=(""),
    )
    parser.add_argument(
        "-d",
        "--data_source",
        type=str,
        choices=utils.entities.read_data_sources(),
        help=(
            "The acronym of the data source as defined in the retrieval "
            'modules (example: "entsoe")'
        ),
        required=False,
    )
    parser.add_argument(
        "-wv",
        "--weather_variable",
        type=str,
        help="Variable of the weather data to be downloaded",
        default="2m_temperature",
        required=False,
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
        "-y",
        "--year",
        type=int,
        help="Year to be downloaded",
        required=False,
    )
    parser.add_argument(
        "-y_min",
        "--start-year",
        type=int,
        help="Start year for a range of years to download",
        required=False,
    )
    parser.add_argument(
        "-y_max",
        "--end-year",
        type=int,
        help="End year for a range of years to download (inclusive)",
        required=False,
    )
    parser.add_argument(
        "-fg",
        "--from_global_data",
        help=(
            "Global weather data is first downloaded and then extracted by "
            "country and subdivision codes."
        ),
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-s",
        "--scenario",
        type=str,
        help=(
            "The scenario to be used for the retrieval of the data. If not "
            "specified, all scenarios will be used."
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
        f"electricity_demand_from_{args.data_source}_"
        if args.variable == "electricity_demand"
        else ""
        f"{args.variable}_" + datetime.now().strftime("%Y%m%d_%H%M") + ".log"
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

    if args.variable == "electricity_demand":
        # Run the data retrieval for electricity demand.
        retrievals.electricity_demand.run_data_retrieval(
            args.data_source,
            args.code,
            args.file,
            args.upload_to_gcs,
            args.upload_to_zenodo,
            args.publish_to_zenodo,
            args.made_by_oet,
        )
    elif args.variable == "annual_electricity_demand_per_capita":
        # Run the data retrieval for annual electricity demand per
        # capita.
        retrievals.annual_electricity_demand_per_capita.run_data_retrieval(
            args.code,
            args.file,
            args.year,
            args.start_year,
            args.end_year,
            args.scenario,
        )
    elif args.variable == "population":
        # Run the data retrieval for the population.
        retrievals.population.run_data_retrieval(
            args.code,
            args.file,
            args.year,
            args.start_year,
            args.end_year,
            args.scenario,
        )
    elif args.variable == "gridded_population":
        # Run the data retrieval for the gridded population.
        retrievals.gridded_population.run_data_retrieval(
            args.code,
            args.file,
            args.year,
            args.start_year,
            args.end_year,
            args.scenario,
        )
    elif args.variable == "gdp_ppp_per_capita":
        # Run the data retrieval for the GDP PPP per capita.
        retrievals.gdp_ppp_per_capita.run_data_retrieval(
            args.code,
            args.file,
            args.year,
            args.start_year,
            args.end_year,
            args.scenario,
        )
    elif args.variable == "gridded_gdp_ppp":
        # Run the data retrieval for the gridded GDP PPP.
        retrievals.gridded_gdp_ppp.run_data_retrieval(
            args.code,
            args.file,
            args.year,
            args.start_year,
            args.end_year,
            args.scenario,
        )
    elif args.variable == "gridded_weather":
        # Run the data retrieval for weather.
        retrievals.weather.run_data_retrieval(
            args.from_global_data,
            args.weather_variable,
            args.year,
            args.start_year,
            args.end_year,
            args.code,
            args.file,
        )
    elif args.variable == "temperature":
        # Run the data retrieval for temperature.
        retrievals.temperature.run_temperature_calculation(
            args.code,
            args.file,
            args.year,
            args.start_year,
            args.end_year,
        )
