"""
License: AGPL-3.0.

Description:

    This script performs checks on the data data quality and
    availability, on the electricity demand data sources, and gathers
    the flags of the cleaned electricity demand into a report.
"""

from typing import Literal

from pydantic import Field

import checks.data_availability
import checks.data_sources
import checks.flags
import utils.config


class ConfigModel(utils.config.StrictSettings):
    """Settings of check.py."""

    check: Literal["data_availability", "data_sources", "flags"]
    data_sources: list[str] | None = None
    maximum_age_days: int = 60
    maximum_age_days_by_source: dict[str, int] = Field(default_factory=dict)
    time_limit_minutes: float = 15


def main(config: ConfigModel) -> None:
    """
    Run the check of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("checks")
    utils.config.log_configuration(config)

    if config.check == "data_availability":
        checks.data_availability.run_check()
    elif config.check == "data_sources":
        checks.data_sources.run_check(
            config.data_sources,
            config.maximum_age_days,
            config.maximum_age_days_by_source,
            config.time_limit_minutes,
        )
    else:
        checks.flags.run_check()


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "check",
            ConfigModel,
            "Perform checks on the data data quality and availability.",
        )
    )
