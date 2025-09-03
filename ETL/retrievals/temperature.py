# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes funtions to extract temperature data downloaded
    from the Copernicus Climate Data Store (CDS) for the most populous
    grid cells in a given country or subdivision. It calculates the
    average temperature and saves the results into CSV and Parquet
    files.
"""

import datetime
import logging
import os

import geopandas
import numpy
import pandas
import utils.directories
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray


def get_temperature_in_most_populous_cells(
    year: int,
    climate_model: str | None,
    climate_scenario: str | None,
    entity_shape: geopandas.GeoDataFrame,
    entity_time_zone: datetime.tzinfo,
    number_of_grid_cells: int = 1,
) -> pandas.Series:
    """
    Get the temperature data for the most populous grid cells.

    This function reads the temperature data downloaded from the
    Copernicus Climate Data Store (CDS) for the given year, model, and
    scenario. It then extracts the temperature data for the given year
    in local time and calculates the average temperature for the grid
    cells with the largest population in the given country or
    subdivision.

    Parameters
    ----------
    year : int
        The year of the temperature data.
    entity_shape : geopandas.GeoDataFrame
        The shape of the country or subdivision of interest.
    entity_time_zone : datetime.tzinfo
        Time zone of the country or subdivision of interest.
    number_of_grid_cells : int, optional
        The number of grid cells to consider.

    Returns
    -------
    pandas.Series
        Temperature data for the most populous grid cells.

    Raises
    ------
    ValueError
        If the scenario of the climate data is not provided when the
        year of the temperature data is in the future, or if the
        scenario is not valid.
    """
    # Read the temperature data downloaded from the Copernicus Climate
    # Data Store (CDS).
    temperature_data_directory = utils.directories.read_folders_structure()[
        "gridded_weather_folder"
    ]
    temperature_data = xarray.open_mfdataset(
        os.path.join(
            temperature_data_directory,
            f"{entity_shape.index[0]}_temperature_*"
            + (
                f"_{climate_model}_{climate_scenario}"
                if climate_model and climate_scenario
                else ""
            )
            + ".nc",
        ),
        engine="netcdf4",
    )

    # Harmonize the temperature data.
    temperature_data = utils.geospatial.harmonize_coords(temperature_data)

    # Extract the temperature data for the given year in local time.
    start_date = (
        pandas.Timestamp(str(year) + "-01-01 00:00:00", tz=entity_time_zone)
        .tz_convert("UTC")
        .tz_localize(None)
    )
    end_date = (
        pandas.Timestamp(str(year) + "-12-31 23:59:59", tz=entity_time_zone)
        .tz_convert("UTC")
        .tz_localize(None)
    )
    temperature_data = temperature_data.sel(
        valid_time=slice(start_date, end_date)
    )["t2m"].load()

    # Define the available years for the historical population data.
    available_historical_years = list(range(2000, 2021, 5))

    # Define the available years for the future population data.
    available_future_years = list(range(2025, 2101, 5))

    # Define the available scenarios for the population data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Define the available years for the population data.
    available_years = numpy.array(
        available_historical_years + available_future_years
    )

    # Find the year of the population data that is closest to the year
    # of the temperature data.
    population_year = available_years[
        numpy.abs(available_years - year).argmin()
    ]

    # Find the scenario of the population data if the year of the
    # population data is in the future.
    if population_year in available_future_years:
        if climate_scenario is None:
            raise ValueError(
                "The scenario of the climate data must be provided "
                "when the year of the temperature data is in the "
                "future."
            )
        else:
            population_scenario = None
            for scenario in available_scenarios:
                if scenario in climate_scenario:
                    population_scenario = scenario
                    break
            if population_scenario is None:
                raise ValueError(
                    "The scenario of the climate data is not valid. "
                    f"It must include one of the following: "
                    f"{', '.join(available_scenarios)}."
                )
    else:
        population_scenario = None

    # Read the population data of the country or subdivision of
    # interest.
    population_directory = utils.directories.read_folders_structure()[
        "gridded_population_folder"
    ]
    population = xarray.open_dataarray(
        os.path.join(
            population_directory,
            f"{entity_shape.index[0]}_0.25_deg_{population_year}"
            + (f"_{population_scenario}" if population_scenario else "")
            + ".nc",
        )
    )

    # Get the grid cells with the largest population in the given
    # country or subdivision.
    largest_population = utils.geospatial.get_largest_values_in_shape(
        entity_shape, population, number_of_grid_cells
    )

    # Fix roundig errors in the coordinates of the grid cells.
    x_coords = largest_population["x"].round(2).to_numpy()
    y_coords = largest_population["y"].round(2).to_numpy()
    temperature_data["x"] = temperature_data["x"].round(2)
    temperature_data["y"] = temperature_data["y"].round(2)

    # Get the temperature data for the grid cells with the largest
    # population.
    temperature_in_largest_population = temperature_data.sel(
        y=y_coords,
        x=x_coords,
    )

    # Calculate the average temperature for the grid cells with the
    # largest population.
    average_temperature_in_largest_population = (
        temperature_in_largest_population.mean(dim=("y", "x"))
    )

    # Convert the temperature data to a pandas Series and return it.
    return average_temperature_in_largest_population.to_series()


def build_temperature_database(
    temperature_time_series_top_1: pandas.Series,
    temperature_time_series_top_3: pandas.Series,
    entity_time_zone: datetime.tzinfo,
) -> pandas.DataFrame:
    """
    Build the temperature database for the given country or subdivision.

    This function takes the temperature time series for the most
    populous grid cells in a given country or subdivision and adds
    various statistics to it, such as monthly and annual averages,
    percentiles, and time-related features.

    Parameters
    ----------
    temperature_time_series_top_1 : pandas.Series
        The temperature time series for the most populous grid cell.
    temperature_time_series_top_3 : pandas.Series
        The temperature time series for the 3 most populous grid cells.
    entity_time_zone : datetime.tzinfo
        Time zone of the country or subdivision of interest.

    Returns
    -------
    temperature_database : pandas.DataFrame
        Temperature time series with added statistics.
    """
    # Create an empty DataFrame to store the temperature data.
    temperature_database = pandas.DataFrame(
        index=temperature_time_series_top_1.index
    )

    # Convert the temperature time series to the local time zone.
    temperature_time_series_top_1 = temperature_time_series_top_1.tz_localize(
        "UTC"
    ).tz_convert(entity_time_zone)
    temperature_time_series_top_3 = temperature_time_series_top_3.tz_localize(
        "UTC"
    ).tz_convert(entity_time_zone)

    # Get the montly average temperature.
    monthly_average_temperature = temperature_time_series_top_1.resample(
        "ME"
    ).mean()
    monthly_average_temperature.index = monthly_average_temperature.index.month

    # Get the rank of the monthly average temperature.
    monthly_average_temperature_rank = monthly_average_temperature.rank(
        ascending=False
    )

    # Map the monthly average temperature to the original temperature
    # time series.
    monthly_average_temperature = (
        temperature_time_series_top_1.index.month.map(
            monthly_average_temperature
        ).to_series()
    )
    monthly_average_temperature.index = temperature_time_series_top_1.index

    # Map the monthly average temperature rank to the original
    # temperature time series.
    monthly_average_temperature_rank = (
        temperature_time_series_top_1.index.month.map(
            monthly_average_temperature_rank
        ).to_series()
    )
    monthly_average_temperature_rank.index = (
        temperature_time_series_top_1.index
    )

    # Get the annual average temperature.
    annual_average_temperature = pandas.Series(
        temperature_time_series_top_1.resample("YE").mean().to_numpy()[0],
        index=temperature_time_series_top_1.index,
    )

    # Get the 5 and 95 percentiles of the temperature.
    temperature_5_percentile = pandas.Series(
        temperature_time_series_top_1.quantile(0.05),
        index=temperature_time_series_top_1.index,
    )
    temperature_95_percentile = pandas.Series(
        temperature_time_series_top_1.quantile(0.95),
        index=temperature_time_series_top_1.index,
    )

    # Add the hour of the day, day of the week, month of the year, and
    # year to the DataFrame.
    temperature_database["Local hour of the day"] = (
        temperature_time_series_top_1.index.hour
    )
    temperature_database["Local weekend indicator"] = (
        temperature_time_series_top_1.index.dayofweek >= 5
    ).astype(int)
    temperature_database["Local month of the year"] = (
        temperature_time_series_top_1.index.month
    )
    temperature_database["Local year"] = (
        temperature_time_series_top_1.index.year
    )

    # Add the temperature statistics to the temperature time series.
    temperature_database["Temperature - Top 1 (K)"] = (
        temperature_time_series_top_1.to_numpy()
    )
    temperature_database["Temperature - Top 3 (K)"] = (
        temperature_time_series_top_3.to_numpy()
    )
    temperature_database["Monthly average temperature - Top 1 (K)"] = (
        monthly_average_temperature.to_numpy()
    )
    temperature_database["Monthly average temperature rank - Top 1"] = (
        monthly_average_temperature_rank.to_numpy()
    )
    temperature_database["Annual average temperature - Top 1 (K)"] = (
        annual_average_temperature.to_numpy()
    )
    temperature_database["5 percentile temperature - Top 1 (K)"] = (
        temperature_5_percentile.to_numpy()
    )
    temperature_database["95 percentile temperature - Top 1 (K)"] = (
        temperature_95_percentile.to_numpy()
    )
    temperature_database.index.name = "Time (UTC)"

    return temperature_database


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    model: str | None,
    scenario: str | None,
) -> None:
    """
    Extract temperature data for the most populous grid cells.

    This function extracts temperature data downloaded from the
    Copernicus Climate Data Store (CDS) for tthe most populous grid
    cells in a given country or subdivision. It calculates the
    average temperature and saves the results into CSV and Parquet
    files.

    Parameters
    ----------
    code : str | None
        The ISO Alpha-2 code (example: "FR") or a combination of ISO
        Alpha-2 code and subdivision code (example: "US_CAL").
    file : str | None
        The path to the yaml file containing the list of codes of the
        countries and subdivisions of interest.
    year : int | None
        The year of the weather data from which the temperature data
        will be extracted.
    start_year : int | None
        The start year for a range of years to extract the temperature
        data.
    end_year : int | None
        The end year for a range of years to extract the temperature
        data (inclusive).
    model : str | None
        The model of the weather data.
    scenario : str | None
        The scenario of the weather data.
    """
    # Create a directory to store the weather data.
    result_directory = utils.directories.read_folders_structure()[
        "temperature_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Define the available years for the historical weather data.
    # Historical data is available from 1940 but it is not necessary to
    # go that far back for our purposes.
    available_historical_years = list(range(1990, pandas.Timestamp.now().year))

    # Define the available years for the future weather data.
    available_future_years = list(range(pandas.Timestamp.now().year + 1, 2101))

    # Define the available scenarios for the weather data.
    available_scenarios_for_model = {
        "CAMS-CSM1-0": [
            "SSP1-1.9",
            "SSP1-2.6",
            "SSP2-4.5",
            "SSP3-7.0",
            "SSP5-8.5",
        ],  # China
        "CESM2": ["SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5"],  # USA
        "CNRM-ESM2-1": [
            "SSP1-1.9",
            "SSP1-2.6",
            "SSP4-3.4",
            "SSP2-4.5",
            "SSP4-6.0",
            "SSP3-7.0",
            "SSP5-8.5",
        ],  # France
        "EC-Earth3-Veg-LR": [
            "SSP1-1.9",
            "SSP1-2.6",
            "SSP2-4.5",
            "SSP3-7.0",
            "SSP5-8.5",
        ],  # Europe
        "HadGEM3-GC31-LL": ["SSP1-2.6", "SSP2-4.5", "SSP5-8.5"],  # UK
        "MIROC-ES2L": [
            "SSP1-1.9",
            "SSP1-2.6",
            "SSP2-4.5",
            "SSP3-7.0",
            "SSP5-8.5",
        ],  # Japan
        "MPI-ESM1-2-LR": [
            "SSP1-2.6",
            "SSP2-4.5",
            "SSP3-7.0",
            "SSP5-8.5",
        ],  # Germany
    }

    # Get the list of year, model, and scenario combinations.
    year_model_scenario_list = (
        utils.scenarios.get_year_model_and_scenario_combinations(
            year,
            start_year,
            end_year,
            available_historical_years,
            available_future_years,
            model,
            scenario,
            available_scenarios_for_model,
        )
    )

    # Loop over the countries and subdivisions of interest.
    for code in codes:
        logging.info(f"Retrieving temperature data for {code}.")

        # Get the shape of the country or subdivision.
        entity_shape = utils.shapes.get_entity_shape(code, make_plot=False)

        # Get the time zone of the country or subdivision.
        entity_time_zone = utils.entities.get_time_zone(code)

        # Loop over the year, model, and scenario combinations.
        for year, model, scenario in year_model_scenario_list:
            logging.info(
                f"Extracting temperature data for year {year}"
                + (
                    f", model {model}, and scenario {scenario}."
                    if model and scenario
                    else "."
                )
            )

            # Define the file paths of the temperature time series.
            file_path_without_ext = os.path.join(
                result_directory,
                f"{code}_temperature_{year}"
                + (f"_{model}_{scenario}" if model and scenario else ""),
            )

            # Check if the file of temperature time series for the
            # given country or subdivision, year, model, and scenario
            # already exists.
            if not os.path.exists(
                file_path_without_ext + ".parquet"
            ) or not os.path.exists(file_path_without_ext + ".csv"):
                # Get the temperature data for the most populous grid
                # cell in the given country or subdivision.
                temperature_time_series_top_1 = (
                    get_temperature_in_most_populous_cells(
                        year,
                        model,
                        scenario,
                        entity_shape,
                        entity_time_zone,
                        number_of_grid_cells=1,
                    )
                )

                # Get the temperature data for the 3 most populous
                # grid cells in the given country or subdivision.
                temperature_time_series_top_3 = (
                    get_temperature_in_most_populous_cells(
                        year,
                        model,
                        scenario,
                        entity_shape,
                        entity_time_zone,
                        number_of_grid_cells=3,
                    )
                )

                # Add temperature statistics to the time series.
                temperature_database = build_temperature_database(
                    temperature_time_series_top_1,
                    temperature_time_series_top_3,
                    entity_time_zone,
                )

                # Save the temperature time series.
                temperature_database.to_parquet(
                    file_path_without_ext + ".parquet"
                )
                temperature_database.to_csv(file_path_without_ext + ".csv")

                logging.info(
                    f"Temperature time series for {code} has been "
                    "successfully extracted and saved."
                )
            else:
                logging.info(
                    f"Temperature time series for {code} already exists."
                )
