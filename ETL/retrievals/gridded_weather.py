# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download weather data from the
    Copernicus Climate Data Store (CDS). It then extracts the weather
    data for the countries and subdivisions of interest and saves it
    into NetCDF files.

    Source: https://cds.climate.copernicus.eu/
"""

import logging
import os
import zipfile

import cdsapi
import pandas
import utils.directories
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray
from dotenv import load_dotenv
from tqdm import tqdm


def _get_request(
    variable: str,
    year: int,
    model: str | None,
    scenario: str | None,
    bounds: list[float] | None = None,
) -> dict[str, str | list[str] | list[float]]:
    """
    Get the request to download weather data from the Copernicus CDS.

    Parameters
    ----------
    variable : str
        The weather variable of interest.
    year : int
        The year of the data retrieval.
    model : str | None
        The climate model of interest.
    scenario : str | None
        The scenario of interest.
    bounds : list[float], optional
        The lateral bounds of the area of interest
        (West, South, East, North).

    Returns
    -------
    request : dict[str, str | list[str] | list[float]]
        The request for the data retrieval.

    Raises
    ------
    ValueError
        If only one of model or scenario is provided.
    """
    # Initialize the request with the common parameters.
    request: dict[str, str | list[str] | list[float]] = {
        "year": [str(year)],
        "month": [f"{mm:02d}" for mm in range(1, 13)],
        "day": [f"{dd:02d}" for dd in range(1, 32)],
    }

    if model is None and scenario is None:
        # Historical reanalysis data.
        request["product_type"] = ["reanalysis"]
        request["variable"] = [variable]
        request["data_format"] = "netcdf"
        request["download_format"] = "unarchived"
        request["time"] = [f"{tt:02d}:00" for tt in range(24)]
    else:
        # Climate projections.
        if model is None or scenario is None:
            raise ValueError(
                "Both model and scenario must be provided for climate "
                "projections."
            )
        request["temporal_resolution"] = "daily"
        request["variable"] = variable
        request["model"] = model.lower().replace("-", "_")
        request["experiment"] = (
            scenario.lower().replace("-", "_").replace(".", "_")
        )

    # Add the bounds to the request if they are provided.
    if bounds is not None:
        request["area"] = [
            bounds[3],
            bounds[0],
            bounds[1],
            bounds[2],
        ]  # North, West, South, East

    return request


def _download_data(
    file_path: str,
    year: int,
    variable: str,
    dataset: str,
    model: str | None,
    scenario: str | None,
    bounds: list[float] | None = None,
) -> None:
    """
    Download the weather data from the Copernicus CDS.

    Parameters
    ----------
    file_path_without_ext : str
        The full file path without the file extension where the
        downloaded data will be saved.
    year : int
        The year of the data retrieval.
    variable : str
        The weather variable of interest.
    dataset : str
        The dataset to be used for the retrieval of the data.
        Supported datasets are "reanalysis-era5-single-levels" and
        "projections-cmip6".
    model : str | None
        The climate model of interest.
    scenario : str | None
        The scenario of interest.
    bounds : list of float, optional
        The lateral bounds of the area of interest
        (West, South, East, North).

    Raises
    ------
    ValueError
        If the dataset is not supported or if the zip file contains
        multiple .nc files.
    """
    logging.info(
        f"Downloading global {variable} data for the year "
        f"{year}"
        + (
            f", model {model}, and scenario {scenario}."
            if model and scenario
            else "."
        )
    )

    # Get the root directory of the project.
    root_directory = utils.directories.read_folders_structure()["root_folder"]

    # Load the environment variables.
    load_dotenv(dotenv_path=os.path.join(root_directory, ".env"))

    # Get the API key.
    cds_key = os.getenv("CDS_API_KEY")

    # Create a new CDS API client.
    client = cdsapi.Client(
        url="https://cds.climate.copernicus.eu/api", key=cds_key
    )

    # Define the dataset.
    if dataset == "reanalysis-era5-single-levels" or dataset == "reanalysis":
        dataset = "reanalysis-era5-single-levels"
        file_path += ".nc"
    elif dataset == "projections-cmip6" or dataset == "projections":
        dataset = "projections-cmip6"
        file_path += ".zip"
    else:
        raise ValueError(f"Dataset {dataset} is not supported.")

    # Define the request.
    request = _get_request(variable, year, model, scenario, bounds)
    client.retrieve(dataset, request, file_path)

    # Unzip the file if it is a projections dataset.
    if dataset == "projections-cmip6":
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            zip_ref.extractall(os.path.dirname(file_path))

            # Delete the extracted files that do not have a .nc
            # extension.
            for file in zip_ref.namelist():
                if not file.endswith(".nc"):
                    os.remove(os.path.join(os.path.dirname(file_path), file))

            # Rename the extracted .nc file to the desired file path.
            extracted_nc_files = [
                file for file in zip_ref.namelist() if file.endswith(".nc")
            ]
            if len(extracted_nc_files) == 1:
                os.rename(
                    os.path.join(
                        os.path.dirname(file_path), extracted_nc_files[0]
                    ),
                    file_path.replace(".zip", ".nc"),
                )
            else:
                raise ValueError(
                    "The zip file contains multiple .nc files. "
                    "Cannot determine which one to rename."
                )

        # Remove the zip file.
        os.remove(file_path)

        logging.info(
            f"Global {variable} data for the year {year}"
            + (
                f", model {model}, and scenario {scenario} has "
                "been successfully downloaded."
                if model and scenario
                else " has been successfully downloaded."
            )
        )


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    variable: str,
    model: str | None,
    scenario: str | None,
) -> None:
    """
    Download and extract gridded weather data.

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
    variable : str
        The variable of the weather data to be downloaded.
    model : str | None
        The model of the weather data to be retrieved.
    scenario : str | None
        The scenario of the weather data to be retrieved.

    Raises
    ------
    ValueError
        If the variable is not supported.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "gridded_weather_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "shape", code=code, file_path=file
    )

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

    # Define the available weather variables.
    available_variables = ["temperature"]

    if variable not in available_variables:
        raise ValueError(
            f"Variable {variable} is not implemented yet. "
            f"Supported variables are: {', '.join(available_variables)}."
        )

    cds_variable_mapping = {
        "temperature": {
            "reanalysis": "2m_temperature",
            "projections": "near_surface_air_temperature",
        }
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

    # If there are many codes download the global data and then
    # extract the data for each country and subdivision.
    if len(codes) > 5:
        # Create a directory to store the downloaded global data.
        downloaded_data_directory = os.path.join(result_directory, "downloads")
        os.makedirs(downloaded_data_directory, exist_ok=True)

        # Loop over the year, model, and scenario combinations.
        for year, model, scenario in tqdm(
            year_model_scenario_list, desc="Years, models, and scenarios"
        ):
            logging.info(
                f"Processing {variable} data for the year {year}"
                + (
                    f", model {model}, and scenario {scenario}."
                    if model and scenario
                    else "."
                )
            )

            # Define the case name for the file.
            case_name = f"{variable}_{year}" + (
                f"_{model}_{scenario.replace('-', '_').replace('.', '_')}"
                if model and scenario
                else ""
            )

            # Define the full file path for the global weather data.
            global_file_path_without_ext = os.path.join(
                downloaded_data_directory,
                f"{case_name}",
            )

            # Check if the global file does not exist. For the
            # current year and historical data, we re-download the
            # global data to account for possible updates in the
            # reanalysis data.
            if not os.path.exists(global_file_path_without_ext + ".nc") or (
                os.path.exists(global_file_path_without_ext + ".nc")
                and year == pandas.Timestamp.now().year
                and model is None
                and scenario is None
            ):
                # Get the CDS variable name.
                cds_variable_name = cds_variable_mapping[variable][
                    "projections" if model and scenario else "reanalysis"
                ]

                # Download the global weather data from CDS.
                _download_data(
                    global_file_path_without_ext,
                    year,
                    cds_variable_name,
                    "projections" if model and scenario else "reanalysis",
                    model,
                    scenario,
                )

            # Load the global weather data.
            global_data = xarray.open_dataarray(
                global_file_path_without_ext + ".nc"
            )

            # Harmonize the coordinates of the global data.
            global_data = utils.geospatial.harmonize_coords(global_data)

            # Loop over the countries and subdivisions of interest.
            for code in codes:
                # Define the file path for the weather data of
                # the country or subdivision.
                entity_file_path = os.path.join(
                    result_directory,
                    f"{code}_{case_name}.nc",
                )

                # Check if the file of weather data for the
                # given country or subdivision, year, model, and
                # scenario already exists. For the current year
                # and historical data, we re-extract the weather
                # data to account for possible updates in the
                # reanalysis data.
                if not os.path.exists(entity_file_path) or (
                    os.path.exists(entity_file_path)
                    and year == pandas.Timestamp.now().year
                    and model is None
                    and scenario is None
                ):
                    logging.info(
                        f"Extracting {variable} data for {code} and "
                        f"year {year}."
                    )

                    # Get the shape of the country or subdivision.
                    entity_shape = utils.shapes.get_entity_shape(
                        code, make_plot=False
                    )

                    # Get the lateral bounds for the shape.
                    entity_bounds = utils.shapes.get_entity_bounds(
                        entity_shape
                    )  # West, South, East, North

                    # Extract data for the country or subdivision.
                    entity_data = global_data.sel(
                        x=slice(entity_bounds[0], entity_bounds[2]),
                        y=slice(entity_bounds[1], entity_bounds[3]),
                    )

                    # Save the data to a NetCDF file.
                    entity_data.to_netcdf(entity_file_path)

                    logging.info(
                        f"{variable.capitalize()} data for {code} and "
                        f"year {year} has been successfully extracted and "
                        "saved."
                    )
                else:
                    logging.info(
                        f"{variable.capitalize()} data for {code} and "
                        f"year {year} already exists. Skipping extraction."
                    )

            logging.info(
                f"Processing of {variable} data for year {year} has been "
                "completed."
            )

    else:
        # Loop over the countries and subdivisions of interest.
        for code in tqdm(codes, desc="Countries and subdivisions"):
            logging.info(f"Retrieving {variable} data for {code}.")

            # Get the shape of the country or subdivision.
            entity_shape = utils.shapes.get_entity_shape(code, make_plot=False)

            # Get the lateral bounds of the country or subdivision.
            entity_bounds = utils.shapes.get_entity_bounds(
                entity_shape
            )  # West, South, East, North

            # Loop over the year, model, and scenario combinations.
            for year, model, scenario in year_model_scenario_list:
                # Define the full file paths of the ERA5 data.
                entity_file_path_without_ext = os.path.join(
                    result_directory,
                    f"{code}_{variable}_{year}"
                    + (
                        f"_{model}_{scenario.replace('-', '_').replace('.', '_')}"
                        if model and scenario
                        else ""
                    ),
                )

                # Check if the file does not exist.
                if not os.path.exists(entity_file_path_without_ext + ".nc"):
                    logging.info(
                        f"Downloading {variable} data for year {year}"
                        + (
                            f", model {model}, and scenario {scenario}"
                            if model and scenario
                            else ""
                        )
                        + " from Copernicus CDS."
                    )

                    # Get the CDS variable name.
                    cds_variable_name = cds_variable_mapping[variable][
                        "projections" if model and scenario else "reanalysis"
                    ]

                    # Download the weather data from CDS.
                    _download_data(
                        entity_file_path_without_ext,
                        year,
                        cds_variable_name,
                        "projections" if model and scenario else "reanalysis",
                        model,
                        scenario,
                        bounds=entity_bounds,
                    )

            logging.info(
                f"{variable} data for {code} has been successfully retrieved "
                "and saved."
            )
