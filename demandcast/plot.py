"""
License: AGPL-3.0.

Description:

    This script plots figures of data availability, geographical
    coverage, and machine learning results.
"""

import os
from typing import Literal

import figures.data_availability
import figures.map_of_available_entities
import figures.ml_results
import utils.config
from pydantic import BaseModel, model_validator


class ConfigModel(BaseModel):
    """Settings of plot.py."""

    figure: Literal[
        "data_availability", "map_of_available_entities", "ml_results"
    ]
    version: str | None = None
    compare_with_version: str | None = None
    by_group: bool = False

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
        elif (
            self.version is not None
            or self.compare_with_version is not None
            or self.by_group
        ):
            raise ValueError(
                "The variables 'version', 'compare_with_version', and "
                "'by_group' must not be provided when plotting data "
                "availability or map of available entities figures."
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

    # Create a directory to store the figures.
    figure_directory = utils.config.read_folders_structure()["figures_folder"]
    os.makedirs(figure_directory, exist_ok=True)

    if config.figure == "data_availability":
        figures.data_availability.plot(figure_directory)
    elif config.figure == "map_of_available_entities":
        figures.map_of_available_entities.plot(figure_directory)
    else:
        figures.ml_results.plot(
            figure_directory,
            str(config.version),
            config.compare_with_version,
            config.by_group,
        )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "plot",
            ConfigModel,
            "Plot the specified figure for data availability and coverage.",
        )
    )
