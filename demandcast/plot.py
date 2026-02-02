# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script plots figures of data availability, geographical
    coverage, and machine learning results.
"""

import logging
import os
from typing import Optional

import figures.data_availability
import figures.map_of_available_entities
import figures.ml_results
import utils.config
from pydantic import BaseModel, ValidationError


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for plotting.

    Returns
    -------
    BaseModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        figure: str
        version: Optional[str] = None
        compare_with_version: Optional[str] = None
        by_group: bool = False

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "plot",
        "Plot the specified figure for data availability and coverage.",
    )

    try:
        # Validate the configuration.
        config = ConfigModel(**raw_config)

        logging.info("Configuration validated successfully:")
        for field, value in config.model_dump().items():
            logging.info(f" - {field}: {value}")

        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("plotting")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Create a directory to store the figures.
    figure_directory = utils.config.read_folders_structure()["figures_folder"]
    os.makedirs(figure_directory, exist_ok=True)

    # Plot the specified figure.
    if (
        config.figure == "data_availability"
        or config.figure == "map_of_available_entities"
    ):
        # Make sure that other arguments are not provided.
        if (
            config.version is not None
            or config.compare_with_version is not None
            or config.by_group
        ):
            raise ValueError(
                "The variables 'version', 'compare_with_version', and "
                "'by_group' must not be provided when plotting data "
                "availability or map of available entities figures."
            )

        if config.figure == "data_availability":
            figures.data_availability.plot(figure_directory)
        elif config.figure == "map_of_available_entities":
            figures.map_of_available_entities.plot(figure_directory)

    elif config.figure == "ml_results":
        # Make sure that the version argument is provided.
        if config.version is None:
            raise ValueError(
                "The argument --version must be provided when plotting "
                "the ML results figure."
            )

        figures.ml_results.plot(
            figure_directory,
            config.version,
            config.compare_with_version,
            config.by_group,
        )
