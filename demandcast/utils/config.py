"""
License: AGPL-3.0.

Description:

    This module reads the configuration files of the scripts and the API
    keys, and sets up the logging. The paths of the folders and files
    are in utils/paths.py.
"""

import argparse
import logging
import os
from datetime import datetime

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, ValidationError

import utils.paths
import utils.raw_data


class StrictSettings(BaseModel):
    """
    Settings that reject the fields that they do not have.

    A misspelled setting, such as "start_yr" for "start_year", is an
    error instead of a setting that is silently left at its default.
    """

    model_config = ConfigDict(extra="forbid")


def read_api_key(variable: str, service: str) -> str:
    """
    Read an API key from the environment or the .env file.

    The environment variables are loaded first from the .env file in
    the root folder, if any, without overriding those already set.
    While saved responses are replayed, as with offline: true, a key
    that is not set gets a stand-in (see utils.raw_data.get_stand_in),
    since the saved requests have their keys hidden.

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
        If the key is not set or is empty, and the saved responses are
        not replayed.
    """
    load_dotenv(dotenv_path=utils.paths.ENV_FILE)

    # A secret that is not set on GitHub gives an empty key.
    api_key = os.getenv(variable)
    if not api_key and utils.raw_data.is_replaying():
        return utils.raw_data.get_stand_in(variable)
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
    Read the YAML configuration file given on the command line.

    The option -c/--config of the command line (sys.argv) gives the
    path of the file, by default <script_name>_config.yaml in the
    config folder of the code, whatever the current folder.

    Parameters
    ----------
    script_name : str
        The name of the script, which names its default configuration
        file.
    script_description : str
        A brief description of the script, for its help message.

    Returns
    -------
    config : dict
        The settings of the file, empty if the file is empty.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    """
    parser = argparse.ArgumentParser(description=script_description)

    default_path = utils.paths.get_config_file(f"{script_name}_config.yaml")
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=default_path,
        help=f"The path to config file (default: {default_path}).",
        required=False,
    )

    config_file_path = parser.parse_args().config

    if not os.path.exists(config_file_path):
        raise FileNotFoundError(
            f"The configuration file '{config_file_path}' does not exist."
        )

    with open(config_file_path, encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config or {}


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
        return config_model(**raw_config)
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
    Set up the logging to a file.

    The messages of level INFO and above go to a new file in the logs
    folder, named after the process and the local time.

    Parameters
    ----------
    process : str
        The name of the process for which the logging is set up.
    """
    log_file_name = (
        process
        + "_"
        + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        + ".log"
    )

    log_files_directory = utils.paths.get_logs_folder()
    os.makedirs(log_files_directory, exist_ok=True)

    logging.basicConfig(
        filename=os.path.join(log_files_directory, log_file_name),
        level=logging.INFO,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
