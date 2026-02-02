# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script performs checks on the data data quality and
    availability.
"""

import logging

import checks.data_availability
import utils.config
from pydantic import BaseModel, ValidationError


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for checks.

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
        check: str

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "check",
        "Perform checks on the data data quality and availability.",
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
    utils.config.set_up_logging("checks")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Run the specified check.
    if config.check == "data_availability":
        checks.data_availability.run_check()
