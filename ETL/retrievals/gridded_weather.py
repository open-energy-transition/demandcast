# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module downloads weather data from the Copernicus Climate Data
    Store (CDS). It then extracts the weather data for the countries and
    subdivisions of interest and saves it into NetCDF files. The country
    and subdivision code can be specified or a list can be provided as a
    yaml file. If no file or code is provided, the module will use all
    available codes. The variable of the weather data can be specified
    as a command line argument. The default variable is 2m_temperature.
    The year of the weather data can be specified as a command line
    argument. If no year is provided, the module will use all the years
    of available electricity demand data.
"""

import logging
import os

import pandas
import utils.copernicus
import utils.directories
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray
from tqdm import tqdm


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    model: str | None,
    scenario: str | None,
    variable: str,
) -> None:
    """
    Run the gridded weather data retrieval.

    This function retrieves weather data from the Copernicus Climate
    Data Store (CDS) for the countries and subdivisions of interest.
    The data is saved into NetCDF files in the specified directory.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the weather data to be retrieved.
    start_year : int | None
        The start year of the range of weather data to be retrieved.
    end_year : int | None
        The end year of the range of weather data to be retrieved.
    scenario : str | None
        The scenario of the weather data to be retrieved.
    variable : str
        The variable of the weather data to be downloaded.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "gridded_weather_folder"
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

    if len(codes) > 5:
        # If there are many codes download the global data and then
        # extract the data for each country and subdivision.

        # Loop over the year, model, and scenario combinations.
        for year, model, scenario in year_model_scenario_list:
            logging.info(
                f"Processing {variable} data for the year {year}"
                + (f", model {model}" if model else "")
                + (f", and scenario {scenario}." if scenario else ".")
            )

            # Define the full file path for the global weather data.
            global_file_path = os.path.join(
                result_directory,
                f"{variable}_{year}"
                + (f"_{model}" if model else "")
                + (f"_{scenario}" if scenario else "")
                + ".nc",
            )

            # Check if the global file does not exist.
            if not os.path.exists(global_file_path):
                logging.info(f"Downloading global data for the year {year}.")

                # Download the global weather data from CDS.
                utils.copernicus.download_data(
                    global_file_path,
                    year,
                    variable,
                    "projections" if model and scenario else "reanalysis",
                    model,
                    scenario,
                )
            else:
                logging.info(
                    f"Global data for the year {year} already exists. "
                    "Using existing file."
                )

            # Load the global weather data.
            global_data = xarray.open_dataarray(global_file_path)

            # Harmonize the coordinates of the global data.
            global_data = utils.geospatial.harmonize_coords(global_data)

            # Process each country/subdivision.
            for code in tqdm(codes, desc=f"Processing countries for {year}"):
                logging.info(
                    f"Processing {variable} data for {code} for year {year}."
                )

                try:
                    # Define the file path for the country-specific
                    # data.
                    country_file_path = os.path.join(
                        result_directory, f"{code}_{variable}_{year}.nc"
                    )

                    # Check if the country file already exists
                    # or if the year is the current year (to
                    # overwrite).
                    if not os.path.exists(country_file_path) or (
                        os.path.exists(country_file_path)
                        and year == pandas.Timestamp.now().year
                    ):
                        logging.info(
                            f"Extracting data for {code} for the year {year}."
                        )

                        # Get the shape of the country or
                        # subdivision.
                        entity_shape = utils.shapes.get_entity_shape(
                            code, make_plot=False
                        )

                        # Get the lateral bounds for the shape
                        entity_bounds = utils.shapes.get_entity_bounds(
                            entity_shape
                        )  # West, South, East, North

                        # Extract data for the country or
                        # subdivision.
                        country_data = global_data.sel(
                            x=slice(entity_bounds[0], entity_bounds[2]),
                            y=slice(entity_bounds[1], entity_bounds[3]),
                        )

                        # Save the country-specific data
                        country_data.to_netcdf(country_file_path)

                        logging.info(
                            f"{variable} data for {code} for year {year} "
                            "has been successfully extracted and saved."
                        )
                    else:
                        logging.info(
                            f"Data for {code} for year {year} already "
                            "exists. Skipping extraction."
                        )

                except Exception as e:
                    logging.error(
                        f"Error processing global data for year {year}: "
                        f"{str(e)}"
                    )
                    continue

            logging.info(
                f"Processing of {variable} data for year {year} has been "
                "completed."
            )

    # else:
    #     # Loop over the countries and subdivisions of interest.
    #     for code in codes:
    #         logging.info(f"Retrieving {variable} data for {code}.")

    #         if year is not None:
    #             # If the year is provided, use it.
    #             years = [year]
    #         else:
    #             # Get the years of available data for the country or
    #             # subdivision of interest.
    #             years = utils.entities.get_available_years(code)

    #         # Get the shape of the country or subdivision.
    #         entity_shape = utils.shapes.get_entity_shape(code, make_plot=False)

    #         # Get the lateral bounds of the country or subdivision.
    #         entity_bounds = utils.shapes.get_entity_bounds(
    #             entity_shape
    #         )  # West, South, East, North

    #         # Loop over the years.
    #         for year in years:
    #             # Define the full file paths of the ERA5 data.
    #             file_path = os.path.join(
    #                 result_directory, f"{code}_{variable}_{year}.nc"
    #             )

    #             # Check if the file does not exist or if the year is the
    #             # current year.
    #             if not os.path.exists(file_path) or (
    #                 os.path.exists(file_path)
    #                 and year == pandas.Timestamp.now().year
    #             ):
    #                 logging.info(f"Retrieving data for the year {year}.")

    #                 # Download the ERA5 data from the Copernicus Climate
    #                 # Data Store (CDS).
    #                 utils.copernicus.download_data(
    #                     year, variable, file_path, bounds=entity_bounds
    #                 )

    #             else:
    #                 logging.info(
    #                     f"Data for the year {year} already exists. Skipping "
    #                     "download."
    #                 )

    #         logging.info(
    #             f"{variable} data for {code} has been successfully retrieved "
    #             "and saved."
    #         )
