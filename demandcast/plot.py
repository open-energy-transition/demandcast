"""
License: AGPL-3.0.

Description:

    This script plots figures of data availability, geographical
    coverage, and machine learning results, and the figures and numbers
    of the "Current state" page of the documentation.
"""

import os
from typing import Literal

from pydantic import model_validator

import figures.data_availability
import figures.map_of_available_entities
import figures.ml_results
import figures.status
import utils.config
import utils.paths


class ConfigModel(utils.config.StrictSettings):
    """Settings of plot.py."""

    figure: Literal[
        "data_availability",
        "map_of_available_entities",
        "ml_results",
        "status",
    ]
    version: str | None = None
    compare_with_version: str | None = None
    by_group: bool = False
    results: Literal["validation", "cross_validation"] = "validation"
    metric: Literal["WAPE", "MAPE"] = "WAPE"
    validation_results: str | None = None
    cross_validation_results: str | None = None

    @model_validator(mode="after")
    def _check_settings_of_figure(self) -> "ConfigModel":
        """
        Check the settings that each figure takes.

        Returns
        -------
        ConfigModel
            The settings.

        Raises
        ------
        ValueError
            If a setting is missing or does not apply to the figure.
        """
        if self.figure == "ml_results":
            if self.version is None:
                raise ValueError(
                    "The version must be provided when plotting the ML "
                    "results figure."
                )
            if self.by_group and self.compare_with_version is not None:
                raise ValueError(
                    "The variables 'by_group' and 'compare_with_version' "
                    "cannot be used together at the moment."
                )
        elif (
            self.version is not None
            or self.compare_with_version is not None
            or self.by_group
        ):
            raise ValueError(
                "The variables 'version', 'compare_with_version', and "
                "'by_group' must not be provided when plotting data "
                "availability, map of available entities or status figures."
            )
        if self.figure != "status" and (
            self.validation_results is not None
            or self.cross_validation_results is not None
        ):
            raise ValueError(
                "The variables 'validation_results' and "
                "'cross_validation_results' are only for the status figures."
            )
        return self


def main(config: ConfigModel) -> None:
    """
    Plot the figure of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("plotting")
    utils.config.log_configuration(config)

    figure_directory = utils.paths.get_results_folder("figures")
    os.makedirs(figure_directory, exist_ok=True)

    if config.figure == "data_availability":
        figures.data_availability.plot(figure_directory)
    elif config.figure == "map_of_available_entities":
        figures.map_of_available_entities.plot(figure_directory)
    elif config.figure == "status":
        figures.status.plot(
            figure_directory,
            results_files={
                "validation": config.validation_results,
                "cross_validation": config.cross_validation_results,
            },
        )
    else:
        figures.ml_results.plot(
            figure_directory,
            str(config.version),
            config.compare_with_version,
            config.by_group,
            utils.paths.get_results_folder(config.results),
            config.metric,
        )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "plot",
            ConfigModel,
            "Plot the specified figure for data availability and coverage.",
        )
    )
