"""
License: AGPL-3.0.

Description:

    This script performs checks on the data data quality and
    availability, and on the electricity demand data sources.
"""

import logging

import checks.data_availability
import checks.data_sources
import utils.config
from pydantic import BaseModel, ValidationError


class ConfigModel(BaseModel):
    """Settings of check.py."""

    check: str
    data_sources: list[str] | None = None
    maximum_age_days: int = 60
    maximum_age_days_by_source: dict[str, int] = {}
    time_limit_minutes: float = 15


def _read_and_check_configuration() -> ConfigModel:
    """
    Read and check the configuration for checks.

    Returns
    -------
    ConfigModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """
    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "check",
        "Perform checks on the data data quality and availability.",
    )

    # Validate the configuration.
    try:
        config = ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e

    logging.info("Configuration validated successfully:")
    for field, value in config.model_dump().items():
        logging.info(f" - {field}: {value}")

    return config


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("checks")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Run the specified check.
    if config.check == "data_availability":
        checks.data_availability.run_check()
    elif config.check == "data_sources":
        checks.data_sources.run_check(
            config.data_sources,
            config.maximum_age_days,
            config.maximum_age_days_by_source,
            config.time_limit_minutes,
        )
