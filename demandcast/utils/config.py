"""
License: AGPL-3.0.

Description:

    This module provides utility functions to read the configuration
    files of the scripts, the API keys and to set up the logging. The
    paths of the folders and files are in utils/paths.py.
"""

import argparse
import logging
import os
from datetime import datetime

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

import utils.paths


def read_api_key(variable: str, service: str) -> str:
    """
    Read an API key from the environment or the .env file.

    The environment variables are loaded first from the .env file in
    the root folder, if any, without overriding those already set.

    Parameters
    ----------
    variable : str
        The name of the environment variable of the key.
    service : str
        The name of the service of the key, for the error message.

    Returns
    -------
    str
        The API key.

    Raises
    ------
    ValueError
        If the key is not set or is empty.
    """
    load_dotenv(dotenv_path=utils.paths.ENV_FILE)

    # A secret that is not set on GitHub gives an empty key.
    api_key = os.getenv(variable)
    if not api_key:
        raise ValueError(
            f"The {service} API key is not set. Please set the {variable} "
            "environment variable."
        )
    return api_key


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
    with open(config_file_path, encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config


def read_and_check_configuration[ConfigModelT: BaseModel](
    script_name: str,
    config_model: type[ConfigModelT],
    script_description: str = "",
) -> ConfigModelT:
    """
    Read the configuration file of a script and validate it.

    Parameters
    ----------
    script_name : str
        The name of the script, which names its default configuration
        file.
    config_model : type[ConfigModelT]
        The Pydantic model of the settings of the script.
    script_description : str, optional
        A brief description of the script, for its help message.

    Returns
    -------
    ConfigModelT
        The validated settings.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """
    raw_config = read_configuration(script_name, script_description)
    try:
        # An empty file has no settings.
        return config_model(**(raw_config or {}))
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


def log_configuration(config: BaseModel) -> None:
    """
    Log the validated settings of a script.

    Parameters
    ----------
    config : pydantic.BaseModel
        The settings.
    """
    logging.info("Configuration validated successfully:")
    for field, value in config.model_dump().items():
        logging.info(f" - {field}: {value}")


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
    log_files_directory = utils.paths.get_logs_folder()
    os.makedirs(log_files_directory, exist_ok=True)

    # Set up the logging configuration.
    logging.basicConfig(
        filename=os.path.join(log_files_directory, log_file_name),
        level=logging.INFO,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
