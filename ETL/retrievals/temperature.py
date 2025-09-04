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

import numpy
import pandas
import utils.directories
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray

import retrievals.gridded_population
import retrievals.gridded_weather


def _load_gridded_temperature_data(
    code: str,
    year: int,
    available_climate_years: list[int],
    climate_model: str | None,
    climate_scenario: str | None,
) -> xarray.DataArray:
    """
    Load the gridded temperature data.

    This function reads the temperature data downloaded from the
    Copernicus Climate Data Store (CDS) for the given year, model,
    and scenario. It loads the data for the given year as well as for
    the previous and next year to account for time zone differences
    when extracting the temperature data for the given year in local
    time.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the temperature data.
    available_climate_years : list[int]
        The list of available years for the climate data.
    climate_model : str | None
        The model of the climate data.
    climate_scenario : str | None
        The scenario of the climate data.

    Returns
    -------
    xarray.DataArray
        The gridded temperature data.

    Raises
    ------
    ValueError
        If the temperature variable is not found in the dataset.
    """
    # Define the directory where the temperature data is stored.
    temperature_data_directory = utils.directories.read_folders_structure()[
        "gridded_weather_folder"
    ]

    # Define the years of interest (the given year, the previous
    # year, and the next year).
    years_of_interest = [year - 1, year, year + 1]
    years_of_interest = [
        y for y in years_of_interest if y in available_climate_years
    ]

    # Define the file path of the temperature data for the given year,
    # model, and scenario as well as for the previous and next year.
    # This is done to account for time zone differences when
    # extracting the temperature data for the given year in local
    # time.
    temperature_data_file_paths = [
        os.path.join(
            temperature_data_directory,
            f"{code}_temperature_{y}"
            + (
                f"_{climate_model}_{climate_scenario.replace('-', '_').replace('.', '_')}"
                if climate_model and climate_scenario
                else ""
            )
            + ".nc",
        )
        for y in years_of_interest
    ]

    # Check if the temperature data files do not exist and download if
    # necessary. For the current year and historical data, we
    # re-download the data to account for possible updates in the
    # reanalysis data.
    for file_path, y in zip(temperature_data_file_paths, years_of_interest):
        if not os.path.exists(file_path) or (
            os.path.exists(file_path)
            and y == pandas.Timestamp.now().year
            and climate_model is None
            and climate_scenario is None
        ):
            # Download the gridded temperature data.
            retrievals.gridded_weather.run_data_retrieval(
                code=code,
                file=None,
                year=y,
                start_year=None,
                end_year=None,
                variable="temperature",
                model=climate_model,
                scenario=climate_scenario,
            )

    # Read the temperature data.
    temperature_data = xarray.open_mfdataset(temperature_data_file_paths)

    # Extract the temperature variable.
    if "t2m" in temperature_data:
        temperature_data = temperature_data["t2m"]
    elif "tas" in temperature_data:
        temperature_data = temperature_data["tas"]
    else:
        raise ValueError(
            "The temperature variable is not found in the dataset. "
            "It must be either 't2m' or 'tas'."
        )

    # Harmonize the temperature data and return it.
    return utils.geospatial.harmonize_coords(temperature_data)


def _load_gridded_population_data(
    code: str,
    year: int,
    climate_scenario: str | None,
) -> xarray.DataArray:
    """
    Load the gridded population data.

    This function reads the gridded population data for the given
    year. It finds the year of the population data that is closest to
    the year of the temperature data and downloads the population data
    if it is not already available.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the temperature data.
    climate_scenario : str | None
        The scenario of the climate data.

    Returns
    -------
    xarray.DataArray
        The gridded population data.

    Raises
    ------
    ValueError
        If the scenario of the climate data is not valid.
    """
    # Define the available years for the historical population data.
    available_historical_population_years = numpy.arange(2000, 2021, 5)

    # Define the available years for the future population data.
    available_future_population_years = numpy.arange(2025, 2101, 5)

    # Define the available scenarios for the population data.
    available_population_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Find the year of the population data that is closest to the year
    # of the temperature data.
    if climate_scenario is None:
        population_year = available_historical_population_years[
            numpy.abs(available_historical_population_years - year).argmin()
        ]
    else:
        population_year = available_future_population_years[
            numpy.abs(available_future_population_years - year).argmin()
        ]

    # Find the scenario of the population data if the year of the
    # population data is in the future.
    if climate_scenario is not None:
        population_scenario = None
        for scenario in available_population_scenarios:
            if scenario in climate_scenario:
                population_scenario = scenario
                break
        if population_scenario is None:
            raise ValueError(
                "The scenario of the climate data is not valid. "
                f"It must include one of the following: "
                f"{', '.join(available_population_scenarios)}."
            )
    else:
        population_scenario = None

    # # Define the directory where the population data is stored.
    population_data_directory = utils.directories.read_folders_structure()[
        "gridded_population_folder"
    ]

    # Define the file path of the population data.
    population_data_file_path = os.path.join(
        population_data_directory,
        f"{code}_0.25_deg_{population_year}"
        + (f"_{population_scenario}" if population_scenario else "")
        + ".nc",
    )

    # Check if the population data file does not exist and download if
    # necessary.
    if not os.path.exists(population_data_file_path):
        # Download the gridded population data.
        retrievals.gridded_population.run_data_retrieval(
            code=code,
            file=None,
            year=population_year,
            start_year=None,
            end_year=None,
            scenario=population_scenario,
        )

    # Read the population data.
    population_data = xarray.open_dataarray(population_data_file_path)

    # Harmonize the population data and return it.
    return utils.geospatial.harmonize_coords(population_data)


def _extract_temperature_in_most_populous_cells(
    temperature_data: xarray.DataArray,
    most_populous_grid_cells: xarray.DataArray,
) -> xarray.DataArray:
    """
    Extract the temperature data for the most populous grid cells.

    Parameters
    ----------
    temperature_data : xarray.DataArray
        The gridded temperature data.
    most_populous_grid_cells : xarray.DataArray
        The grid cells with the largest population in the given
        country or subdivision.

    Returns
    -------
    xarray.DataArray
        The temperature data for the most populous grid cells.
    """
    # Extract the x and y coordinates of the grid cells with the
    # largest population.
    x_coords = most_populous_grid_cells["x"].to_numpy()
    y_coords = most_populous_grid_cells["y"].to_numpy()

    # Find the closest grid cell in the temperature data to each of
    # the grid cells with the largest population.
    selected_x_coords = numpy.array(
        [
            temperature_data["x"]
            .sel(
                x=temperature_data["x"].to_numpy()[
                    numpy.abs(temperature_data["x"].to_numpy() - x).argmin()
                ]
            )
            .to_numpy()
            for x in x_coords
        ]
    )
    selected_y_coords = numpy.array(
        [
            temperature_data["y"]
            .sel(
                y=temperature_data["y"].to_numpy()[
                    numpy.abs(temperature_data["y"].to_numpy() - y).argmin()
                ]
            )
            .to_numpy()
            for y in y_coords
        ]
    )

    # Extract the temperature data for the grid cells with the largest
    # population.
    return temperature_data.sel(y=selected_y_coords, x=selected_x_coords)


def _extract_temperature_in_local_year(
    temperature_data: xarray.DataArray,
    year: int,
    entity_time_zone: datetime.tzinfo,
    projections: bool,
) -> xarray.DataArray:
    """
    Extract the temperature data for the given year in local time.

    Parameters
    ----------
    temperature_data : xarray.DataArray
        The gridded temperature data.
    year : int
        The year of the temperature data.
    entity_time_zone : datetime.tzinfo
        Time zone of the country or subdivision of interest.
    projections : bool
        Whether the temperature data is from a climate model (True)
        or from reanalysis data (False).

    Returns
    -------
    xarray.DataArray
        The temperature data for the given year in local time.
    """
    if projections:
        # Add 12 hours to the time coordinate to center the daily data
        # on noon.
        temperature_data["time"] = temperature_data["time"] + pandas.Timedelta(
            hours=12
        )

        # Upsample the daily data to hourly data using linear
        # interpolation.
        temperature_data = temperature_data.resample(time="1h").interpolate()

    # Define the start and end date for the given year in local time.
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

    # Extract the temperature data for the given year in local time.
    return temperature_data.sel(time=slice(start_date, end_date))


def _get_temperature_in_most_populous_cells(
    code: str,
    year: int,
    available_climate_years: list[int],
    climate_model: str | None,
    climate_scenario: str | None,
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
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the temperature data.
    available_climate_years : list[int]
        The list of available years for the climate data.
    climate_model : str | None
        The model of the climate data.
    climate_scenario : str | None
        The scenario of the climate data.
    entity_time_zone : datetime.tzinfo
        Time zone of the country or subdivision of interest.
    number_of_grid_cells : int, optional
        The number of grid cells to consider.

    Returns
    -------
    pandas.Series
        Temperature data for the most populous grid cells.
    """
    # Load the gridded temperature data.
    temperature_data = _load_gridded_temperature_data(
        code,
        year,
        available_climate_years,
        climate_model,
        climate_scenario,
    )

    # Harmonize the time coordinate of the temperature data.
    if climate_model is None:
        # Reanalysis data has a time coordinate named "valid_time".
        temperature_data = temperature_data.rename({"valid_time": "time"})
    elif climate_model:
        # Climate model data has a time type of cftime.DatetimeNoLeap.
        # Convert it to datetime64.
        temperature_data["time"] = (
            temperature_data["time"]
            .to_index()
            .to_datetimeindex(time_unit="ns")
        )

    # Load the population data.
    population_data = _load_gridded_population_data(
        code,
        year,
        climate_scenario,
    )

    # Get the shape of the country or subdivision.
    entity_shape = utils.shapes.get_entity_shape(code, make_plot=False)

    # Get the grid cells with the largest population in the given
    # country or subdivision.
    most_populous_grid_cells = utils.geospatial.get_largest_values_in_shape(
        entity_shape, population_data, number_of_grid_cells
    )

    # Extract the temperature data for the most populous grid cells.
    temperature_in_most_populous_grid_cells = (
        _extract_temperature_in_most_populous_cells(
            temperature_data, most_populous_grid_cells
        )
    )

    # Extract the temperature data for the given year in local time.
    temperature_in_most_populous_grid_cells = (
        _extract_temperature_in_local_year(
            temperature_in_most_populous_grid_cells,
            year,
            entity_time_zone,
            (climate_model is not None),
        )
    )

    # Calculate the average temperature for the grid cells with the
    # largest population.
    average_temperature_in_most_populous_grid_cells = (
        temperature_in_most_populous_grid_cells.mean(dim=("y", "x"))
    )

    # Convert the temperature data to a pandas Series and return it.
    return average_temperature_in_most_populous_grid_cells.to_series()


def _build_temperature_database(
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
    available_historical_years = list(
        range(1990, pandas.Timestamp.now().year + 1)
    )

    # Define the available years for the future weather data.
    available_future_years = list(range(pandas.Timestamp.now().year, 2101))

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
                f"{code}_{year}"
                + (
                    f"_{model}_{scenario.replace('-', '_').replace('.', '_')}"
                    if model and scenario
                    else ""
                ),
            )

            # Check if the file of temperature time series for the
            # given country or subdivision, year, model, and scenario
            # already exists. For the current year and historical
            # data, we re-extract the temperature data to account for
            # possible updates in the reanalysis data.
            if (
                not os.path.exists(file_path_without_ext + ".parquet")
                or not os.path.exists(file_path_without_ext + ".csv")
            ) or (
                os.path.exists(file_path_without_ext + ".parquet")
                and os.path.exists(file_path_without_ext + ".csv")
                and year == pandas.Timestamp.now().year
                and model is None
                and scenario is None
            ):
                # Get the temperature data for the most populous grid
                # cell in the given country or subdivision.
                temperature_time_series_top_1 = (
                    _get_temperature_in_most_populous_cells(
                        code,
                        year,
                        available_future_years
                        if model and scenario
                        else available_historical_years,
                        model,
                        scenario,
                        entity_time_zone,
                        number_of_grid_cells=1,
                    )
                )

                # Get the temperature data for the 3 most populous
                # grid cells in the given country or subdivision.
                temperature_time_series_top_3 = (
                    _get_temperature_in_most_populous_cells(
                        code,
                        year,
                        available_future_years
                        if model and scenario
                        else available_historical_years,
                        model,
                        scenario,
                        entity_time_zone,
                        number_of_grid_cells=3,
                    )
                )

                # Add temperature statistics to the time series.
                temperature_database = _build_temperature_database(
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
