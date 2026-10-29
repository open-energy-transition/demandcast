"""
License: AGPL-3.0.

Description:

    This module includes functions to extract temperature data
    downloaded from the Copernicus Climate Data Store (CDS) for the most
    populous grid cells in a given country or subdivision. It calculates
    the average temperature and saves the results into CSV and Parquet
    files.

    The temperature of the reanalysis comes from one of three sources of
    the same ERA5 data (the reanalysis_source of retrieve.py):

    - points (by default): the hourly series of the points of ERA5
      closest to the most populous cells, from the time series of the
      CDS (see retrievals/era5_points.py), a few MB for all the years.
    - cds or arco: the grids of the countries and subdivisions, from the
      CDS or from ARCO-ERA5 (see retrievals/gridded_weather.py), about
      5 GB a year for all of them.

    The cells of the gridded population are on the points of ERA5, so
    the three sources give the same cells and values. The projections
    of the climate models come from the grids of the CDS.

    Each row is an hour, at its end in UTC, like the electricity demand,
    which is the mean demand of the hour. Its temperature is the mean of
    the instantaneous temperatures at the start and at the end of the
    hour, and its local hour, day, month and year are those of its
    start, so that the hour from 23:00 to midnight on a Friday is on a
    Friday and that before midnight on January 1 in the year before.

    Each Parquet file records the version of the processing that made it
    (PROCESSING_VERSION), which changes when the extraction changes what
    it gives for the same weather, such as the choice of the cells. A
    file of another version, or without one, is extracted again, from
    the weather already downloaded: the reanalysis is not downloaded
    again, and neither are the projections.
"""

import datetime
import logging
import os

import numpy as np
import pandas as pd
import xarray
from tqdm import tqdm

import retrievals.era5_points
import retrievals.gridded_population
import retrievals.gridded_weather
import utils.availability
import utils.catalogue
import utils.geospatial
import utils.paths
import utils.scenarios
import utils.shapes
import utils.time_series
import utils.time_zones

# The version of the processing of the temperature files. Version 1
# ranks the cells by their population inside the shape of the country
# or subdivision.
PROCESSING_VERSION = 1

# The key of the attributes of a temperature file with its processing.
PROCESSING_KEY = "demandcast_temperature"

# The sources of the temperature of the reanalysis.
REANALYSIS_SOURCES = ("points", *retrievals.gridded_weather.SOURCES)


def _load_gridded_temperature_data(
    code: str,
    year: int,
    available_climate_years: list[int],
    climate_model: str | None,
    climate_scenario: str | None,
    source: str = "cds",
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
        The list of available years for the climate data. The
        reanalysis is read until the current year, whose first hours
        end the last complete year west of UTC.
    climate_model : str | None
        The model of the climate data.
    climate_scenario : str | None
        The scenario of the climate data.
    source : str, optional
        The source of the gridded reanalysis data, "cds" or "arco".

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
    temperature_data_directory = utils.paths.get_gridded_folder(
        "weather", "processed"
    )

    # Define the years of interest (the given year, the previous
    # year, and the next year).
    years_of_interest = [year - 1, year, year + 1]
    if climate_model is None:
        available_climate_years = [
            *available_climate_years,
            pd.Timestamp.now().year,
        ]
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
            retrievals.gridded_weather.get_file_name(
                "temperature", y, climate_model, climate_scenario, code
            )
            + ".nc",
        )
        for y in years_of_interest
    ]

    # Download the temperature data if it does not exist, or if the
    # reanalysis data may have been updated since.
    for file_path, y in zip(
        temperature_data_file_paths, years_of_interest, strict=True
    ):
        if not retrievals.gridded_weather.is_outdated(
            file_path, y, climate_model, climate_scenario
        ):
            continue
        # Download the gridded temperature data: the reanalysis of the
        # year, even the current one, or the projections.
        if climate_model is None:
            retrievals.gridded_weather.retrieve_reanalysis(
                code, y, "temperature", source
            )
        else:
            retrievals.gridded_weather.run_data_retrieval(
                code=code,
                file=None,
                year=y,
                start_year=None,
                end_year=None,
                variable="temperature",
                model=climate_model,
                scenario=climate_scenario,
                source=source,
            )

    # Read the temperature data.
    dataset = xarray.open_mfdataset(temperature_data_file_paths)

    # Extract the temperature variable.
    if "t2m" in dataset:
        temperature_data = dataset["t2m"]
    elif "tas" in dataset:
        temperature_data = dataset["tas"]
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

    """
    # Define the available years for the historical and future
    # population data.
    available_historical_population_years = np.array(
        utils.catalogue.GRIDDED_POPULATION_YEARS
    )
    available_future_population_years = np.array(
        utils.catalogue.PROJECTION_YEARS
    )

    # Find the year of the population data that is closest to the year
    # of the temperature data.
    if climate_scenario is None:
        population_year = available_historical_population_years[
            np.abs(available_historical_population_years - year).argmin()
        ]
    else:
        population_year = available_future_population_years[
            np.abs(available_future_population_years - year).argmin()
        ]

    # Find the scenario of the population data if the year of the
    # population data is in the future.
    population_scenario = (
        utils.catalogue.get_ssp(climate_scenario)
        if climate_scenario is not None
        else None
    )

    # Define the file path of the population data.
    population_data_file_path = utils.paths.get_gridded_file(
        "population", code, int(population_year), population_scenario
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
        The temperature data of the closest grid cell to each of the
        most populous grid cells, along the "cell" dimension. Populous
        cells that share their closest grid cell each count it once.
    """
    # Select the coordinates in pairs: separate lists of x and y would
    # select all their combinations, such as 9 cells for 3.
    return temperature_data.sel(
        x=xarray.DataArray(
            most_populous_grid_cells["x"].to_numpy(), dims="cell"
        ),
        y=xarray.DataArray(
            most_populous_grid_cells["y"].to_numpy(), dims="cell"
        ),
        method="nearest",
    )


def _extract_temperature_in_local_year(
    temperature_data: xarray.DataArray,
    year: int,
    entity_time_zone: datetime.tzinfo,
    projections: bool,
) -> xarray.DataArray:
    """
    Extract the hourly mean temperature of a year in local time.

    The electricity demand of an hour is its mean, at the end of the
    hour, so the temperature of an hour is its mean too: the mean of the
    temperatures at its start and at its end, which are instantaneous,
    or the temperature at its half hour if it changes linearly.

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
        The mean temperature of the hours of the year in local time, at
        their ends in UTC: the hours that start in the year.
    """
    if projections:
        # Add 12 hours to the time coordinate to center the daily data
        # on noon.
        temperature_data["time"] = temperature_data["time"] + np.timedelta64(
            12, "h"
        )

        # Upsample the daily data to hourly data using linear
        # interpolation.
        temperature_data = temperature_data.resample(time="1h").interpolate()

    # The mean temperature of each hour, at its end.
    temperature_data = temperature_data.rolling(time=2).mean()

    # The hours that start in the year in local time.
    local_years = utils.time_series.get_local_years(
        temperature_data.indexes["time"], entity_time_zone
    )
    return temperature_data.isel(time=np.flatnonzero(local_years == year))


def _get_temperature_of_points(
    most_populous_grid_cells: xarray.DataArray,
) -> xarray.DataArray:
    """
    Get the temperature of the points of the most populous cells.

    Parameters
    ----------
    most_populous_grid_cells : xarray.DataArray
        The grid cells with the largest population.

    Returns
    -------
    xarray.DataArray
        The hourly temperature of the closest point of ERA5 to each of
        the most populous cells, along the "cell" dimension, as given by
        _extract_temperature_in_most_populous_cells.
    """
    points = [
        retrievals.era5_points.get_grid_point(float(x), float(y))
        for x, y in zip(
            most_populous_grid_cells["x"].to_numpy(),
            most_populous_grid_cells["y"].to_numpy(),
            strict=True,
        )
    ]
    series = pd.concat(
        retrievals.era5_points.get_points_series("temperature", points),
        axis=1,
        keys=range(len(points)),
    )
    return xarray.DataArray(
        series.to_numpy(),
        coords={"time": pd.DatetimeIndex(series.index).to_numpy()},
        dims=("time", "cell"),
    )


def _get_temperature_in_most_populous_cells(
    code: str,
    year: int,
    available_climate_years: list[int],
    climate_model: str | None,
    climate_scenario: str | None,
    entity_time_zone: datetime.tzinfo,
    numbers_of_grid_cells: tuple[int, ...] = (1,),
    reanalysis_source: str = "points",
) -> list[pd.Series]:
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
    numbers_of_grid_cells : tuple[int, ...], optional
        The numbers of grid cells to consider.
    reanalysis_source : str, optional
        The source of the temperature of the reanalysis, "points",
        "cds" or "arco" (see the description of the module).

    Returns
    -------
    list[pandas.Series]
        Temperature data for each number of most populous grid cells.
    """
    # Load the gridded temperature data, unless the reanalysis comes
    # from the series of points.
    temperature_data = None
    if climate_model is not None or reanalysis_source != "points":
        temperature_data = _load_gridded_temperature_data(
            code,
            year,
            available_climate_years,
            climate_model,
            climate_scenario,
            "cds" if climate_model is not None else reanalysis_source,
        )

    # Harmonize the time coordinate of the temperature data.
    if temperature_data is None:
        pass
    elif climate_model is None:
        # Reanalysis data has a time coordinate named "valid_time".
        temperature_data = temperature_data.rename({"valid_time": "time"})
    else:
        # Climate models use different calendars, such as one without
        # leap days or one with 360 days, decoded as dates of cftime,
        # or the standard one, decoded as datetime64. Convert them to
        # the standard calendar: the days that their calendar does not
        # have are interpolated with the hours.
        temperature_data = temperature_data.convert_calendar(
            "standard", align_on="year", use_cftime=False
        )

    # Load the population data.
    population_data = _load_gridded_population_data(
        code,
        year,
        climate_scenario,
    )

    # Get the shape of the country or subdivision.
    entity_shape = utils.shapes.get_entity_shape(code, make_plot=False)

    temperatures = []
    for number_of_grid_cells in numbers_of_grid_cells:
        # Get the grid cells with the largest population in the given
        # country or subdivision.
        most_populous_grid_cells = (
            utils.geospatial.get_largest_values_in_shape(
                entity_shape, population_data, number_of_grid_cells
            )
        )

        # Extract the temperature data for the most populous grid
        # cells, in the given year in local time.
        temperature_in_most_populous_grid_cells = (
            _extract_temperature_in_local_year(
                _get_temperature_of_points(most_populous_grid_cells)
                if temperature_data is None
                else _extract_temperature_in_most_populous_cells(
                    temperature_data, most_populous_grid_cells
                ),
                year,
                entity_time_zone,
                (climate_model is not None),
            )
        )

        # Calculate the average temperature for the grid cells with the
        # largest population.
        temperatures.append(
            temperature_in_most_populous_grid_cells.mean(
                dim="cell"
            ).to_series()
        )

    return temperatures


def has_current_processing(file_path: str) -> bool:
    """
    Check whether a temperature file was made by the current processing.

    Parameters
    ----------
    file_path : str
        The path of the Parquet file.

    Returns
    -------
    bool
        Whether the file records the current PROCESSING_VERSION, False
        if it records another one, none, or cannot be read.
    """
    try:
        # The attributes are read without the columns.
        attributes = pd.read_parquet(file_path, columns=[]).attrs
    except (OSError, ValueError):
        return False
    processing = attributes.get(PROCESSING_KEY) or {}
    return processing.get("version") == PROCESSING_VERSION


def _build_temperature_database(
    temperature_time_series_top_1: pd.Series,
    temperature_time_series_top_3: pd.Series,
    entity_time_zone: datetime.tzinfo,
) -> pd.DataFrame:
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
    temperature_database = pd.DataFrame(
        index=temperature_time_series_top_1.index
    )

    # Get the local time of the start of each hour, which gives the
    # hour, the day, the month and the year of the hour: the times are
    # the ends of the hours in UTC.
    local_time = (
        pd.DatetimeIndex(temperature_time_series_top_1.index).tz_localize(
            "UTC"
        )
        - pd.Timedelta(hours=1)
    ).tz_convert(entity_time_zone)

    # Get the monthly average temperature.
    monthly_average_temperature = temperature_time_series_top_1.groupby(
        local_time.month
    ).mean()

    # Get the rank of the monthly average temperature.
    monthly_average_temperature_rank = monthly_average_temperature.rank(
        ascending=False
    )

    # Map the monthly average temperature to the original temperature
    # time series.
    monthly_average_temperature = local_time.month.map(
        monthly_average_temperature.to_dict()
    ).to_series()
    monthly_average_temperature.index = temperature_time_series_top_1.index

    # Map the monthly average temperature rank to the original
    # temperature time series.
    monthly_average_temperature_rank = local_time.month.map(
        monthly_average_temperature_rank.to_dict()
    ).to_series()
    monthly_average_temperature_rank.index = (
        temperature_time_series_top_1.index
    )

    # Get the annual average temperature.
    annual_average_temperature = pd.Series(
        temperature_time_series_top_1.mean(),
        index=temperature_time_series_top_1.index,
    )

    # Get the 5 and 95 percentiles of the temperature.
    temperature_5_percentile = pd.Series(
        temperature_time_series_top_1.quantile(0.05),
        index=temperature_time_series_top_1.index,
    )
    temperature_95_percentile = pd.Series(
        temperature_time_series_top_1.quantile(0.95),
        index=temperature_time_series_top_1.index,
    )

    # Add the hour of the day, day of the week, month of the year, and
    # year to the DataFrame.
    temperature_database["Local hour of the day"] = local_time.hour
    temperature_database["Local weekend indicator"] = (
        local_time.dayofweek >= 5
    ).astype(int)
    temperature_database["Local month of the year"] = local_time.month
    temperature_database["Local year"] = local_time.year

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
    reanalysis_source: str = "points",
) -> None:
    """
    Extract temperature data for the most populous grid cells.

    This function extracts temperature data downloaded from the
    Copernicus Climate Data Store (CDS) for the most populous grid
    cells in a given country or subdivision. It calculates the
    average temperature and saves the results into CSV and Parquet
    files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
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
    reanalysis_source : str, optional
        The source of the temperature of the reanalysis, "points",
        "cds" or "arco" (see the description of the module).

    Raises
    ------
    ValueError
        If the source of the reanalysis is not supported.
    """
    if reanalysis_source not in REANALYSIS_SOURCES:
        raise ValueError(
            f"Reanalysis source {reanalysis_source} is not supported. "
            f"Supported sources are: {', '.join(REANALYSIS_SOURCES)}."
        )

    # Create a directory to store the weather data.
    result_directory = utils.paths.get_indicator_folder("temperature")
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.availability.check_and_get_codes_with(
        "historical_data", code=code, file_path=file
    )

    # Define the available years of the reanalysis and of the
    # projections of the weather.
    available_historical_years = utils.catalogue.get_reanalysis_years()
    available_future_years = utils.catalogue.get_climate_projection_years()

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
            {
                climate_model: list(scenarios)
                for climate_model, scenarios in (
                    utils.catalogue.CLIMATE_MODEL_SCENARIOS.items()
                )
            },
        )
    )

    # Loop over the countries and subdivisions of interest.
    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        logging.info(f"Retrieving temperature data for {entity_code}.")

        # Get the time zone of the country or subdivision.
        entity_time_zone = utils.time_zones.get_time_zone(entity_code)

        # Loop over the year, model, and scenario combinations.
        for (
            selected_year,
            selected_model,
            selected_scenario,
        ) in year_model_scenario_list:
            logging.info(
                f"Extracting temperature data for the year {selected_year}"
                + (
                    f", model {selected_model}, and scenario "
                    f"{selected_scenario}."
                    if selected_model and selected_scenario
                    else "."
                )
            )

            # Define the file paths of the temperature time series.
            file_path_without_ext = os.path.join(
                result_directory,
                f"{entity_code}_{selected_year}"
                + (
                    (
                        f"_{selected_model.replace('-', '_')}_"
                        + selected_scenario.replace("-", "_").replace(".", "_")
                    )
                    if selected_model and selected_scenario
                    else ""
                ),
            )

            # Extract the temperature time series if it does not exist,
            # if it was made by another processing, or if the reanalysis
            # data may have been updated since.
            if (
                not os.path.exists(file_path_without_ext + ".csv")
                or not has_current_processing(
                    file_path_without_ext + ".parquet"
                )
                or retrievals.gridded_weather.is_outdated(
                    file_path_without_ext + ".parquet",
                    selected_year,
                    selected_model,
                    selected_scenario,
                )
            ):
                # Get the temperature data for the most populous grid
                # cell and for the 3 most populous grid cells in the
                # given country or subdivision.
                (
                    temperature_time_series_top_1,
                    temperature_time_series_top_3,
                ) = _get_temperature_in_most_populous_cells(
                    entity_code,
                    selected_year,
                    available_future_years
                    if selected_model and selected_scenario
                    else available_historical_years,
                    selected_model,
                    selected_scenario,
                    entity_time_zone,
                    numbers_of_grid_cells=(1, 3),
                    reanalysis_source=reanalysis_source,
                )

                # Add temperature statistics to the time series.
                temperature_database = _build_temperature_database(
                    temperature_time_series_top_1,
                    temperature_time_series_top_3,
                    entity_time_zone,
                )

                # Save the temperature time series, with its processing.
                temperature_database.attrs[PROCESSING_KEY] = {
                    "version": PROCESSING_VERSION,
                    "reanalysis_source": None
                    if selected_model
                    else reanalysis_source,
                }
                temperature_database.to_parquet(
                    file_path_without_ext + ".parquet"
                )
                temperature_database.to_csv(file_path_without_ext + ".csv")

                logging.info(
                    f"Temperature time series for the year {selected_year}"
                    + (
                        f", model {selected_model}, and scenario "
                        f"{selected_scenario}"
                        if selected_model and selected_scenario
                        else ""
                    )
                    + " has been successfully extracted and saved."
                )
            else:
                logging.info(
                    f"Temperature time series for the year {selected_year}"
                    + (
                        f", model {selected_model}, and scenario "
                        f"{selected_scenario}"
                        if selected_model and selected_scenario
                        else ""
                    )
                    + " already exists. Skipping extraction."
                )
