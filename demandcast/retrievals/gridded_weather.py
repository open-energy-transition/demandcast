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
from collections.abc import Callable

import cdsapi
import pandas as pd
import utils.availability
import utils.catalogue
import utils.geospatial
import utils.paths
import utils.scenarios
import utils.shapes
import xarray
from dotenv import load_dotenv
from tqdm import tqdm

import retrievals.gridded

# The time after the end of a year until its reanalysis data is
# complete: ERA5 is published about five days after real time, and
# updated every day until then.
REANALYSIS_DELAY = pd.Timedelta(days=7)
REANALYSIS_UPDATE = pd.Timedelta(days=1)

# The names of the weather variables in the reanalysis and in the
# projections of the Climate Data Store.
CDS_VARIABLES = {
    "temperature": {
        "reanalysis": "2m_temperature",
        "projections": "near_surface_air_temperature",
    }
}


def get_file_name(
    variable: str,
    year: int,
    model: str | None,
    scenario: str | None,
    code: str | None = None,
) -> str:
    """
    Get the name of a file of weather data, without extension.

    Parameters
    ----------
    variable : str
        The weather variable.
    year : int
        The year of the weather data.
    model : str | None
        The model of the weather data, None for reanalysis data.
    scenario : str | None
        The scenario of the weather data, None for reanalysis data.
    code : str | None, optional
        The code of the country or subdivision, None for global data.

    Returns
    -------
    str
        The name of the file, such as DEU_temperature_2024 or
        temperature_2030_CESM2_SSP2_4_5.
    """
    name = f"{variable}_{year}"
    if model and scenario:
        name += f"_{model}_" + scenario.replace("-", "_").replace(".", "_")
    return f"{code}_{name}" if code else name


def is_outdated(
    file_path: str, year: int, model: str | None, scenario: str | None
) -> bool:
    """
    Check whether a file of weather data must be retrieved again.

    Parameters
    ----------
    file_path : str
        The path of the file.
    year : int
        The year of the weather data.
    model : str | None
        The model of the weather data, None for reanalysis data.
    scenario : str | None
        The scenario of the weather data, None for reanalysis data.

    Returns
    -------
    bool
        Whether the file does not exist, or has reanalysis data written
        before the data of its year was complete and more than a day
        ago, when the data may have been updated since. This also
        completes a year retrieved while it was in progress.
    """
    if not os.path.exists(file_path):
        return True
    if model is not None or scenario is not None:
        return False
    written = pd.Timestamp(os.path.getmtime(file_path), unit="s")
    return written < min(
        pd.Timestamp(year + 1, 1, 1) + REANALYSIS_DELAY,
        pd.Timestamp.now() - REANALYSIS_UPDATE,
    )


def _get_request(
    variable: str,
    years: list[int],
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
    years : list[int]
        The years of the data retrieval.
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
        "year": [str(year) for year in years],
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
    years: list[int],
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
    file_path : str
        The full file path without the file extension where the
        downloaded data will be saved.
    years : list[int]
        The years of the data retrieval.
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
        f"Downloading gridded {variable} data for the "
        + (
            f"years {years[0]} to {years[-1]}"
            if len(years) > 1
            else f"year {years[0]}"
        )
        + (
            f", model {model}, and scenario {scenario}."
            if model and scenario
            else "."
        )
    )

    # Load the environment variables.
    load_dotenv(dotenv_path=utils.paths.ENV_FILE)

    # Get the API key.
    cds_key = os.getenv("CDS_API_KEY")

    # Create a new CDS API client.
    client = cdsapi.Client(
        url="https://cds.climate.copernicus.eu/api", key=cds_key
    )

    # Define the dataset.
    if dataset in {"reanalysis-era5-single-levels", "reanalysis"}:
        dataset = "reanalysis-era5-single-levels"
        file_path += ".nc"
    elif dataset in {"projections-cmip6", "projections"}:
        dataset = "projections-cmip6"
        file_path += ".zip"
    else:
        raise ValueError(f"Dataset {dataset} is not supported.")

    # Define the request.
    request = _get_request(variable, years, model, scenario, bounds)
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
            f"Gridded {variable} data for the "
            + (
                f"years {years[0]} to {years[-1]}"
                if len(years) > 1
                else f"year {years[0]}"
            )
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
    result_directory = utils.paths.get_gridded_folder("weather", "processed")
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.availability.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )

    if variable not in CDS_VARIABLES:
        raise ValueError(
            f"Variable {variable} is not implemented yet. "
            f"Supported variables are: {', '.join(CDS_VARIABLES)}."
        )

    # Get the list of year, model, and scenario combinations.
    year_model_scenario_list = (
        utils.scenarios.get_year_model_and_scenario_combinations(
            year,
            start_year,
            end_year,
            utils.catalogue.get_reanalysis_years(),
            utils.catalogue.get_climate_projection_years(),
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

    # If there are many codes, download the global data and then extract
    # the data for each country and subdivision.
    if len(codes) > 5:
        _retrieve_global_data(variable, codes, year_model_scenario_list)
    else:
        _retrieve_data_of_each_code(variable, codes, year_model_scenario_list)


def _download(
    file_path: str,
    variable: str,
    year: int,
    model: str | None,
    scenario: str | None,
    bounds: list[float] | None = None,
) -> None:
    """
    Download the weather data of a year, model and scenario.

    Parameters
    ----------
    file_path : str
        The path of the file, without its extension.
    variable : str
        The weather variable.
    year : int
        The year.
    model : str | None
        The climate model, None for the reanalysis.
    scenario : str | None
        The scenario, None for the reanalysis.
    bounds : list[float] | None, optional
        The bounds of the area, west, south, east and north, None for
        the whole world.
    """
    dataset = "projections" if model and scenario else "reanalysis"
    _download_data(
        file_path,
        [year],
        CDS_VARIABLES[variable][dataset],
        dataset,
        model,
        scenario,
        bounds=bounds,
    )


def _get_entity_file_path_function(
    variable: str, year: int, model: str | None, scenario: str | None
) -> Callable[[str], str]:
    """
    Get the function that gives the processed file of a code.

    Parameters
    ----------
    variable : str
        The weather variable.
    year : int
        The year.
    model : str | None
        The climate model, None for the reanalysis.
    scenario : str | None
        The scenario, None for the reanalysis.

    Returns
    -------
    Callable[[str], str]
        The function that gives the path of the file of a code.
    """
    processed_directory = utils.paths.get_gridded_folder(
        "weather", "processed"
    )
    return lambda code: os.path.join(
        processed_directory,
        get_file_name(variable, year, model, scenario, code) + ".nc",
    )


def _get_is_newer_function(global_file_path: str) -> Callable[[str], bool]:
    """
    Get the function that tells whether a file is up to date.

    Parameters
    ----------
    global_file_path : str
        The path of the global data.

    Returns
    -------
    Callable[[str], bool]
        The function that tells whether a file exists and is not older
        than the global data, from which it was extracted.
    """
    return lambda file_path: (
        os.path.exists(file_path)
        and (os.path.getmtime(file_path) >= os.path.getmtime(global_file_path))
    )


def _retrieve_global_data(
    variable: str,
    codes: list[str],
    year_model_scenario_list: list[tuple[int, str | None, str | None]],
) -> None:
    """
    Download the global weather data and extract each code from it.

    The global data of each year, model and scenario is downloaded
    once, in the raw folder, and the data of a country or subdivision
    is extracted again when the global data is newer.

    Parameters
    ----------
    variable : str
        The weather variable.
    codes : list[str]
        The codes of the countries and subdivisions.
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        The years, climate models and scenarios.
    """
    raw_directory = utils.paths.get_gridded_folder("weather", "raw")
    os.makedirs(raw_directory, exist_ok=True)

    for selected_year, selected_model, selected_scenario in tqdm(
        year_model_scenario_list, desc="Years, models, and scenarios"
    ):
        description = f"{variable} data of {selected_year}" + (
            f", model {selected_model}, and scenario {selected_scenario}"
            if selected_model and selected_scenario
            else ""
        )
        logging.info(f"Processing the gridded {description}.")

        # Download the global data if it does not exist, or if the
        # reanalysis data may have been updated since.
        global_file_path_without_ext = os.path.join(
            raw_directory,
            get_file_name(
                variable, selected_year, selected_model, selected_scenario
            ),
        )
        global_file_path = global_file_path_without_ext + ".nc"
        if is_outdated(
            global_file_path, selected_year, selected_model, selected_scenario
        ):
            _download(
                global_file_path_without_ext,
                variable,
                selected_year,
                selected_model,
                selected_scenario,
            )

        with xarray.open_dataset(global_file_path) as global_data:
            retrievals.gridded.extract_entity_grids(
                utils.geospatial.harmonize_coords(global_data),
                codes,
                _get_entity_file_path_function(
                    variable, selected_year, selected_model, selected_scenario
                ),
                description,
                is_up_to_date=_get_is_newer_function(global_file_path),
            )

        logging.info(f"The gridded {description} has been processed.")


def _retrieve_data_of_each_code(
    variable: str,
    codes: list[str],
    year_model_scenario_list: list[tuple[int, str | None, str | None]],
) -> None:
    """
    Download the weather data of each code on its own.

    The data of a country or subdivision is downloaded within its
    bounds, straight into the processed folder.

    Parameters
    ----------
    variable : str
        The weather variable.
    codes : list[str]
        The codes of the countries and subdivisions.
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        The years, climate models and scenarios.
    """
    processed_directory = utils.paths.get_gridded_folder(
        "weather", "processed"
    )

    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        logging.info(f"Retrieving gridded {variable} data for {entity_code}.")

        # Get the lateral bounds of the country or subdivision.
        entity_bounds = utils.shapes.get_entity_bounds(
            utils.shapes.get_entity_shape(entity_code, make_plot=False)
        )  # West, South, East, North

        for (
            selected_year,
            selected_model,
            selected_scenario,
        ) in year_model_scenario_list:
            entity_file_path_without_ext = os.path.join(
                processed_directory,
                get_file_name(
                    variable,
                    selected_year,
                    selected_model,
                    selected_scenario,
                    entity_code,
                ),
            )

            # Download the data if it does not exist, or if the
            # reanalysis data may have been updated since.
            if is_outdated(
                entity_file_path_without_ext + ".nc",
                selected_year,
                selected_model,
                selected_scenario,
            ):
                _download(
                    entity_file_path_without_ext,
                    variable,
                    selected_year,
                    selected_model,
                    selected_scenario,
                    bounds=entity_bounds,
                )

        logging.info(
            f"Gridded {variable} data for {entity_code} has been retrieved "
            "and saved."
        )
