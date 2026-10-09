"""
License: AGPL-3.0.

Description:

    This module provides utility functions to read the configuration
    files of various scripts.
"""

import argparse
import logging
import os
from datetime import datetime
from typing import Any

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
    with open(folders_structure_file_path, encoding="utf-8") as file:
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
    config_overrides: dict[str, Any] | None = None,
    command_line: list[str] | None = None,
) -> dict:
    """
    Read a configuration file in yaml format.

    Parameters
    ----------
    script_name : str
        The name of the script for which the configuration is read.
    script_description : str
        A brief description of the script.
    config_overrides : dict[str, Any] or None, optional
        Configuration values that replace the ones read from the file.
        This lets a caller such as run_all.sh drive the script without
        writing a configuration file of its own. Keys that are not
        configuration fields of the script are left to the validation of
        the caller to reject, so that a typo fails loudly there rather
        than being silently ignored here.
    command_line : list[str] or None, optional
        The command line to read, without the name of the script. It
        defaults to the command line of the process, which a test that
        runs under pytest cannot control.

    Returns
    -------
    config : dict[str, Any]
        A dictionary containing the configuration parameters.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    ValueError
        If a configuration value is not given as KEY=VALUE.
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

    # Add the argument for the configuration values, which are given
    # as "key=value" pairs and can be repeated.
    parser.add_argument(
        "--set",
        type=str,
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "A configuration value that replaces the one of the file, "
            "given as KEY=VALUE. Can be repeated."
        ),
        required=False,
    )

    # Extract the config file path and the configuration values.
    arguments = parser.parse_args(command_line)
    config_file_path = arguments.config
    config_overrides = config_overrides or {}

    # Read the "key=value" pairs into a dictionary.
    for pair in arguments.set:
        key, separator, value = pair.partition("=")
        if not separator:
            raise ValueError(
                f"Invalid configuration value '{pair}': expected KEY=VALUE."
            )
        config_overrides[key] = value

    if not os.path.exists(config_file_path):
        raise FileNotFoundError(
            f"The configuration file '{config_file_path}' does not exist."
        )

    # Read the configuration file.
    with open(config_file_path, encoding="utf-8") as file:
        config = yaml.safe_load(file)

    # Apply the overrides last, so that they win over the file.
    if config_overrides:
        config.update(config_overrides)

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
        process
        + "_"
        + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        + ".log"
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
