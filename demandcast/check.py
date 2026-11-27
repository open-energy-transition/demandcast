"""
License: AGPL-3.0.

Description:

    This script runs one of four checks, chosen by its settings: the
    socio-economic data available for each country and subdivision,
    the electricity demand data sources over the network, a report of
    the flags of the cleaned electricity demand, or the related
    entities: for the entities with data whose shapes overlap, the
    share of the people of each that live in the shared area.
"""

from typing import Literal

from pydantic import Field, model_validator

import checks.data_availability
import checks.data_sources
import checks.flags
import checks.related_entities
import utils.config


class ConfigModel(utils.config.StrictSettings):
    """Settings of check.py."""

    check: Literal[
        "data_availability", "data_sources", "flags", "related_entities"
    ]
    data_sources: list[str] | None = None
    maximum_age_days: int = 60
    maximum_age_days_by_source: dict[str, int] = Field(default_factory=dict)
    time_limit_minutes: float = 15
    skipped_data_sources: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_options_of_the_check(self) -> "ConfigModel":
        """
        Check that the options of the data sources are for their check.

        All the options but the check apply only to the check of the
        data sources, and must be empty or at their default otherwise.

        Returns
        -------
        ConfigModel
            The settings.

        Raises
        ------
        ValueError
            If an option is given for another check.
        """
        if self.check == "data_sources":
            return self
        for option, field in type(self).model_fields.items():
            value = getattr(self, option)
            if option != "check" and value not in (
                None,
                field.get_default(call_default_factory=True),
            ):
                raise ValueError(
                    f"The option {option} applies only to the check of the "
                    f"data sources, not to {self.check}: leave it empty."
                )
        return self


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
            config.skipped_data_sources,
        )
    elif config.check == "related_entities":
        checks.related_entities.run_check()
    else:
        checks.flags.run_check()


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "check",
            ConfigModel,
            "Check the data availability, the data sources, the flags "
            "or the related entities.",
        )
    )
