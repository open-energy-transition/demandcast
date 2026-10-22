"""
License: AGPL-3.0.

Description:

    This script retrieves various types of data for specified countries
    and subdivisions. The data types include electricity demand,
    annual electricity demand per capita, population, gridded
    population, GDP PPP per capita, gridded GDP PPP, gridded weather
    data, and temperature data.
"""

from collections.abc import Callable
from types import ModuleType
from typing import Literal

import retrievals.annual_electricity_demand_per_capita
import retrievals.electricity_demand
import retrievals.gdp_ppp_per_capita
import retrievals.gridded_gdp_ppp
import retrievals.gridded_population
import retrievals.gridded_weather
import retrievals.population
import retrievals.temperature
import utils.config
import utils.entities
from pydantic import BaseModel, field_validator, model_validator


class ConfigModel(BaseModel):
    """Settings of retrieve.py."""

    variable: Literal[
        "electricity_demand",
        "annual_electricity_demand_per_capita",
        "population",
        "gridded_population",
        "gdp_ppp_per_capita",
        "gridded_gdp_ppp",
        "gridded_weather",
        "temperature",
    ]
    electricity_data_source: str | None = None
    code: str | None = None
    file: str | None = None
    year: int | None = None
    start_year: int | None = None
    end_year: int | None = None
    scenario: str | None = None
    weather_variable: Literal["temperature"] | None = None
    climate_model: str | None = None
    offline: bool = False

    @field_validator("electricity_data_source")
    @classmethod
    def _check_data_source(cls, data_source: str | None) -> str | None:
        """
        Check that the data source of electricity demand exists.

        Parameters
        ----------
        data_source : str | None
            The data source.

        Returns
        -------
        str | None
            The data source.

        Raises
        ------
        ValueError
            If the data source does not exist.
        """
        if data_source is not None:
            data_sources = utils.entities.read_data_sources()
            if data_source not in data_sources:
                raise ValueError(
                    f"The data source '{data_source}' is not recognized. "
                    f"Valid data sources are: {data_sources}."
                )
        return data_source

    @model_validator(mode="after")
    def _check_required_settings(self) -> "ConfigModel":
        """
        Check the settings that some variables require.

        Returns
        -------
        ConfigModel
            The settings.

        Raises
        ------
        ValueError
            If a required setting is missing.
        """
        if (
            self.variable == "electricity_demand"
            and not self.electricity_data_source
        ):
            raise ValueError(
                "The data source must be specified for the retrieval of "
                "electricity demand data."
            )
        if self.variable == "gridded_weather" and not self.weather_variable:
            raise ValueError(
                "The weather variable must be specified for the "
                "retrieval of gridded weather data."
            )
        return self


def _retrieve_by_scenario(
    module: ModuleType,
) -> Callable[[ConfigModel], None]:
    """
    Get the retrieval of a variable given by years and scenarios.

    Parameters
    ----------
    module : types.ModuleType
        The retrieval module of the variable.

    Returns
    -------
    Callable[[ConfigModel], None]
        The function that runs the retrieval with the settings.
    """
    return lambda config: module.run_data_retrieval(
        config.code,
        config.file,
        config.year,
        config.start_year,
        config.end_year,
        config.scenario,
    )


# The retrieval of each variable, with the settings that it takes.
RETRIEVALS: dict[str, Callable[[ConfigModel], None]] = {
    "electricity_demand": (
        lambda config: retrievals.electricity_demand.run_data_retrieval(
            str(config.electricity_data_source),
            config.code,
            config.file,
            offline=config.offline,
        )
    ),
    "annual_electricity_demand_per_capita": _retrieve_by_scenario(
        retrievals.annual_electricity_demand_per_capita
    ),
    "population": _retrieve_by_scenario(retrievals.population),
    "gridded_population": _retrieve_by_scenario(retrievals.gridded_population),
    "gdp_ppp_per_capita": _retrieve_by_scenario(retrievals.gdp_ppp_per_capita),
    "gridded_gdp_ppp": _retrieve_by_scenario(retrievals.gridded_gdp_ppp),
    "gridded_weather": (
        lambda config: retrievals.gridded_weather.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            str(config.weather_variable),
            config.climate_model,
            config.scenario,
        )
    ),
    "temperature": (
        lambda config: retrievals.temperature.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.climate_model,
            config.scenario,
        )
    ),
}


def main(config: ConfigModel) -> None:
    """
    Retrieve the data of the variable of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging(
        f"retrieval_of_{config.variable}"
        + (
            f"_from_{config.electricity_data_source}"
            if config.variable == "electricity_demand"
            else ""
        )
    )
    utils.config.log_configuration(config)

    RETRIEVALS[config.variable](config)


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "retrieve",
            ConfigModel,
            "Retrieve the specified data for the specified countries and "
            "subdivisions.",
        )
    )
