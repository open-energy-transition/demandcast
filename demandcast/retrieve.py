# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script retrieves various types of data for specified countries
    and subdivisions. The data types include electricity demand,
    annual electricity demand per capita, population, gridded
    population, GDP PPP per capita, gridded GDP PPP, gridded weather
    data, and temperature data.
"""

import logging
from typing import Optional

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
from pydantic import BaseModel, ValidationError


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for data retrieval.

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
        variable: str
        electricity_data_source: Optional[str] = None
        code: Optional[str] = None
        file: Optional[str] = None
        year: Optional[int] = None
        start_year: Optional[int] = None
        end_year: Optional[int] = None
        scenario: Optional[str] = None
        weather_variable: Optional[str] = None
        climate_model: Optional[str] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "retrieve",
        "Retrieve the specified data for the specified countries and "
        "subdivisions.",
    )

    try:
        # Validate the configuration.
        return ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


if __name__ == "__main__":
    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Set up the logging configuration.
    utils.config.set_up_logging(
        f"retrieval_of_{config.variable}"
        + (
            f"_from_{config.electricity_data_source}"
            if config.variable == "electricity_demand"
            and config.electricity_data_source
            else ""
        )
    )

    logging.info("Configuration validated successfully:")
    for field, value in config.model_dump().items():
        logging.info(f" - {field}: {value}")

    if config.variable == "electricity_demand":
        if not config.electricity_data_source:
            raise ValueError(
                "The data source must be specified for the retrieval of "
                "electricity demand data."
            )

        if (
            config.electricity_data_source
            not in utils.entities.read_data_sources()
        ):
            raise ValueError(
                f"The specified data source '{config.electricity_data_source}' is not "
                "recognized. Valid data sources are: "
                f"{utils.entities.read_data_sources()}."
            )

        # Run the data retrieval for electricity demand.
        retrievals.electricity_demand.run_data_retrieval(
            config.electricity_data_source,
            config.code,
            config.file,
        )
    elif config.variable == "annual_electricity_demand_per_capita":
        # Run the data retrieval for annual electricity demand per
        # capita.
        retrievals.annual_electricity_demand_per_capita.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.scenario,
        )
    elif config.variable == "population":
        # Run the data retrieval for the population.
        retrievals.population.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.scenario,
        )
    elif config.variable == "gridded_population":
        # Run the data retrieval for the gridded population.
        retrievals.gridded_population.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.scenario,
        )
    elif config.variable == "gdp_ppp_per_capita":
        # Run the data retrieval for the GDP PPP per capita.
        retrievals.gdp_ppp_per_capita.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.scenario,
        )
    elif config.variable == "gridded_gdp_ppp":
        # Run the data retrieval for the gridded GDP PPP.
        retrievals.gridded_gdp_ppp.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.scenario,
        )
    elif config.variable == "gridded_weather":
        if not config.weather_variable:
            raise ValueError(
                "The weather variable must be specified for the "
                "retrieval of gridded weather data."
            )

        if config.weather_variable not in ["temperature"]:
            raise ValueError(
                f"The specified weather variable "
                f"'{config.weather_variable}' is not recognized. "
                "Only 'temperature' is currently supported."
            )

        # Run the data retrieval for weather.
        retrievals.gridded_weather.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.weather_variable,
            config.climate_model,
            config.scenario,
        )
    elif config.variable == "temperature":
        # Run the data retrieval for temperature.
        retrievals.temperature.run_data_retrieval(
            config.code,
            config.file,
            config.year,
            config.start_year,
            config.end_year,
            config.climate_model,
            config.scenario,
        )
