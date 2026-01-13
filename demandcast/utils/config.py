# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module povides utility functions to read the configuration
    files of various scripts.
"""

import argparse
import logging
import os
from datetime import datetime

import yaml


def read_folders_structure() -> dict[str, str]:
    """
    Read the folders structure.

    This function reads the folders structure from a yaml file located
    in the 'utils' directory. The yaml file should contain a dictionary
    where keys are folder names and values are their paths relative to
    the root folder. The root folder is determined as the parent
    directory of the current file's directory.

    Returns
    -------
    folders_structure : dict[str, str]
        A dictionary containing the folders structure, where keys are
        folder names and values are their paths.
    """
    # Get the absolute path to the root folder.
    root_folder = os.path.normpath(
        os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
    )

    # Define the default path to the yaml file.
    folders_structure_file_path = os.path.join(
        root_folder, "config", "directories_config.yaml"
    )

    # Read the folders structure from the file.
    with open(folders_structure_file_path, "r") as file:
        folders_structure = yaml.safe_load(file)

    # Add the root folder to the folders structure.
    folders_structure["root_folder"] = root_folder

    # Iterate over the folders structure, concatenate the paths if
    # multiple folders are defined, and normalize the paths.
    for key, value in folders_structure.items():
        # Add the root folder to the path but skip the root folder key.
        if key != "root_folder":
            if isinstance(value, list):
                # If the value is a list, unpack the list.
                folders_structure[key] = os.path.join(root_folder, *value)
            else:
                folders_structure[key] = os.path.join(root_folder, value)

    return folders_structure


def read_configuration(
    script_name: str,
    script_description: str,
) -> dict:
    """
    Read a configuration file in yaml format.

    Parameters
    ----------
    script_name : str
        The name of the script for which the configuration is read.
    script_description : str
        A brief description of the script.

    Returns
    -------
    config : dict[str, Any]
        A dictionary containing the configuration parameters.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    """
    # Create a parser for the command line arguments.
    parser = argparse.ArgumentParser(description=script_description)

    # Add the argument for the config file path.
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=f"./config/{script_name}_config.yaml",
        help=(
            "The path to config file "
            f"(default: ./config/{script_name}_config.yaml)."
        ),
        required=False,
    )

    # Extract the config file path.
    config_file_path = parser.parse_args().config

    if not os.path.exists(config_file_path):
        raise FileNotFoundError(
            f"The configuration file '{config_file_path}' does not exist."
        )

    # Read the configuration file.
    with open(config_file_path, "r") as file:
        config = yaml.safe_load(file)

    return config


def set_up_logging(process: str) -> None:
    """
    Set up the logging configuration.

    Parameters
    ----------
    process : str
        The name of the process for which the logging is set up.
    """
    # Define the log file name.
    log_file_name = (
        process + "_" + datetime.now().strftime("%Y%m%d_%H%M") + ".log"
    )

    # Get the log files directory and create it if it does not exist.
    log_files_directory = read_folders_structure()["log_files_folder"]
    os.makedirs(log_files_directory, exist_ok=True)

    # Set up the logging configuration.
    logging.basicConfig(
        filename=os.path.join(log_files_directory, log_file_name),
        level=logging.INFO,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
