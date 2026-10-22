"""
License: AGPL-3.0.

Description:

    This module includes functions to download gridded weather data and
    extract the weather data of the countries and subdivisions of
    interest into NetCDF files, from one of two sources of the same
    ERA5 reanalysis:

    - cds: the Copernicus Climate Data Store (CDS), which prepares each
      request, of a year of the globe or of a country, in a queue, from
      minutes to hours, and gives the data until about a week ago. The
      projections of the climate models come only from the CDS.
    - arco: the analysis-ready ERA5 of Google Research on Google Cloud
      Storage (ARCO-ERA5), read without an account and without a queue,
      one global map an hour, with the same values as the CDS to its
      rounding (0.001 K) and the preliminary data until about a week
      ago. Google gives no commitment to keep it up to date.

    The temperature of the most populous cells (see
    retrievals/temperature.py) can also come from the time series of
    single points of the CDS (see retrievals/era5_points.py).

    Source: https://cds.climate.copernicus.eu/
    Source: https://github.com/google-research/arco-era5
"""

import logging
import os
import zipfile

import cdsapi
import pandas as pd
import utils.config
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.shapes
import xarray
from tqdm import tqdm

# The sources of the gridded reanalysis data.
SOURCES = ("cds", "arco")

# The API of the CDS, and the names of the variables in its datasets.
CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_VARIABLES = {
    "temperature": {
        "reanalysis": "2m_temperature",
        "projections": "near_surface_air_temperature",
    }
}

# The store of ARCO-ERA5, the names of its variables and of the
# variables of the files of the CDS, and the hours read at once.
ARCO_ERA5_URL = (
    "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
)
ARCO_VARIABLES = {"temperature": ("2m_temperature", "t2m")}
ARCO_HOURS_PER_READ = 7 * 24
ARCO_READ_THREADS = 16

# The time after the end of a year until its reanalysis data is
# complete: ERA5 is published about five days after real time, and
# updated every day until then.
REANALYSIS_DELAY = pd.Timedelta(days=7)
REANALYSIS_UPDATE = pd.Timedelta(days=1)


def get_available_scenarios_for_model() -> dict[str, list[str]]:
    """
    Get the available future scenarios for each climate model.

    Returns
    -------
    dict[str, list[str]]
        A dictionary mapping each climate model to its available
        scenarios.
    """
    return {
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


def get_cds_client(**kwargs: bool) -> cdsapi.Client:
    """
    Get a client of the API of the Copernicus Climate Data Store.

    Parameters
    ----------
    **kwargs : bool
        Other options of the client, such as quiet.

    Returns
    -------
    cdsapi.Client
        The client, with the key in CDS_API_KEY.
    """
    return cdsapi.Client(
        url=CDS_URL,
        key=utils.config.read_api_key(
            "CDS_API_KEY", "the Copernicus Climate Data Store"
        ),
        **kwargs,
    )


def _open_arco_year(variable: str, year: int) -> xarray.DataArray:
    """
    Open the hours of a year of a variable of ARCO-ERA5.

    Parameters
    ----------
    variable : str
        The weather variable.
    year : int
        The year.

    Returns
    -------
    xarray.DataArray
        The variable, lazily, with harmonized coordinates (see
        utils.geospatial.harmonize_coords), until the last day with
        data: the store has the times until 2050.
    """
    dataset = xarray.open_zarr(
        ARCO_ERA5_URL, chunks={}, storage_options={"token": "anon"}
    )
    last_day = dataset.attrs.get(
        "valid_time_stop_era5t", dataset.attrs.get("valid_time_stop")
    )
    end = f"{year}-12-31T23"
    if last_day:
        end = min(end, f"{last_day}T23")
    data = dataset[ARCO_VARIABLES[variable][0]].sel(
        time=slice(f"{year}-01-01", end)
    )
    return utils.geospatial.harmonize_coords(data)


def _extract_from_arco(
    variable: str,
    year: int,
    bounds: dict[str, list[float]],
    file_paths: dict[str, str],
) -> None:
    """
    Extract the gridded data of a year of ARCO-ERA5 for some codes.

    The hours are read a week at a time, for all the codes at once, and
    the files have the variables and coordinates of those of the CDS.

    Parameters
    ----------
    variable : str
        The weather variable.
    year : int
        The year.
    bounds : dict[str, list[float]]
        The bounds of each code (West, South, East, North).
    file_paths : dict[str, str]
        The NetCDF file of each code.
    """
    data = _open_arco_year(variable, year)
    parts: dict[str, list[xarray.DataArray]] = {code: [] for code in bounds}
    for start in tqdm(
        range(0, data.sizes["time"], ARCO_HOURS_PER_READ),
        desc=f"Weeks of {year}",
    ):
        hours = data.isel(
            time=slice(start, start + ARCO_HOURS_PER_READ)
        ).compute(num_workers=ARCO_READ_THREADS)
        for code, (west, south, east, north) in bounds.items():
            parts[code].append(
                hours.sel(x=slice(west, east), y=slice(south, north))
            )

    name = ARCO_VARIABLES[variable][1]
    for code, file_path in file_paths.items():
        dataset = (
            xarray.concat(parts.pop(code), dim="time")
            .rename(time="valid_time")
            .to_dataset(name=name)
        )
        # Replace the file only once it is written.
        dataset.to_netcdf(
            file_path + ".tmp",
            encoding={name: {"zlib": True, "complevel": 1}},
        )
        os.replace(file_path + ".tmp", file_path)
    logging.info(
        f"Gridded {variable} data of ARCO-ERA5 for year {year} has been "
        f"extracted for {len(file_paths)} codes."
    )


def _retrieve_from_arco(
    variable: str,
    codes: list[str],
    year_model_scenario_list: list[tuple[int, str | None, str | None]],
    result_directory: str,
) -> list[tuple[int, str | None, str | None]]:
    """
    Extract the reanalysis data of the codes from ARCO-ERA5.

    Parameters
    ----------
    variable : str
        The weather variable.
    codes : list[str]
        The codes of the countries and subdivisions.
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        The years, models and scenarios to retrieve.
    result_directory : str
        The folder of the gridded weather data.

    Returns
    -------
    list[tuple[int, str | None, str | None]]
        The years, models and scenarios of the projections, which come
        from the CDS.
    """
    for year, model, scenario in tqdm(year_model_scenario_list, desc="Years"):
        if model or scenario:
            continue
        file_paths = {
            code: os.path.join(
                result_directory,
                get_file_name(variable, year, None, None, code) + ".nc",
            )
            for code in codes
        }
        outdated = {
            code: file_path
            for code, file_path in file_paths.items()
            if is_outdated(file_path, year, None, None)
        }
        if outdated:
            _extract_from_arco(
                variable,
                year,
                {
                    code: utils.shapes.get_entity_bounds(
                        utils.shapes.get_entity_shape(code, make_plot=False)
                    )
                    for code in outdated
                },
                outdated,
            )
    return [
        combination
        for combination in year_model_scenario_list
        if combination[1] or combination[2]
    ]


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

    # Create a new CDS API client.
    client = get_cds_client()

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


def _retrieve_global_from_cds(
    variable: str,
    codes: list[str],
    year_model_scenario_list: list[tuple[int, str | None, str | None]],
    result_directory: str,
) -> None:
    """
    Download the global data of the CDS and extract each code.

    Parameters
    ----------
    variable : str
        The weather variable.
    codes : list[str]
        The codes of the countries and subdivisions.
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        The years, models and scenarios to retrieve.
    result_directory : str
        The folder of the gridded weather data.
    """
    # Create a directory to store the downloaded global data.
    downloaded_data_directory = os.path.join(result_directory, "downloads")
    os.makedirs(downloaded_data_directory, exist_ok=True)

    # Loop over the year, model, and scenario combinations.
    for selected_year, selected_model, selected_scenario in tqdm(
        year_model_scenario_list, desc="Years, models, and scenarios"
    ):
        logging.info(
            f"Processing gridded {variable} data for the year "
            f"{selected_year}"
            + (
                f", model {selected_model}, and scenario {selected_scenario}."
                if selected_model and selected_scenario
                else "."
            )
        )

        # Define the full file path for the global weather data.
        global_file_path_without_ext = os.path.join(
            downloaded_data_directory,
            get_file_name(
                variable, selected_year, selected_model, selected_scenario
            ),
        )

        # Download the global data if it does not exist, or if the
        # reanalysis data may have been updated since.
        if is_outdated(
            global_file_path_without_ext + ".nc",
            selected_year,
            selected_model,
            selected_scenario,
        ):
            # Get the CDS variable name.
            cds_variable_name = CDS_VARIABLES[variable][
                "projections"
                if selected_model and selected_scenario
                else "reanalysis"
            ]

            # Download the global weather data from CDS.
            _download_data(
                global_file_path_without_ext,
                [selected_year],
                cds_variable_name,
                "projections"
                if selected_model and selected_scenario
                else "reanalysis",
                selected_model,
                selected_scenario,
            )

        # Load the global weather data.
        global_data = xarray.open_dataset(global_file_path_without_ext + ".nc")

        # Harmonize the coordinates of the global data.
        global_data = utils.geospatial.harmonize_coords(global_data)

        # Loop over the countries and subdivisions of interest.
        for entity_code in tqdm(codes, desc="Countries and subdivisions"):
            # Define the file path for the weather data of
            # the country or subdivision.
            entity_file_path = os.path.join(
                result_directory,
                get_file_name(
                    variable,
                    selected_year,
                    selected_model,
                    selected_scenario,
                    entity_code,
                )
                + ".nc",
            )

            # Extract the weather data of the country or
            # subdivision if it does not exist, or if the global
            # data is newer.
            if not os.path.exists(entity_file_path) or os.path.getmtime(
                entity_file_path
            ) < os.path.getmtime(global_file_path_without_ext + ".nc"):
                logging.info(
                    f"Extracting gridded {variable} data for "
                    f"{entity_code} and "
                    f"year {selected_year}."
                )

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    entity_code, make_plot=False
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
                    f"Gridded {variable} data for {entity_code} and "
                    f"year {selected_year} has been successfully "
                    "extracted and "
                    "saved."
                )
            else:
                logging.info(
                    f"Gridded {variable} data for {entity_code} and "
                    f"year {selected_year} already exists. Skipping "
                    "extraction."
                )

        logging.info(
            f"Processing of gridded {variable} data for year "
            f"{selected_year} has "
            "been completed."
        )


def _retrieve_each_from_cds(
    variable: str,
    codes: list[str],
    year_model_scenario_list: list[tuple[int, str | None, str | None]],
    result_directory: str,
) -> None:
    """
    Download the data of each code from the CDS.

    Parameters
    ----------
    variable : str
        The weather variable.
    codes : list[str]
        The codes of the countries and subdivisions.
    year_model_scenario_list : list[tuple[int, str | None, str | None]]
        The years, models and scenarios to retrieve.
    result_directory : str
        The folder of the gridded weather data.
    """
    # Loop over the countries and subdivisions of interest.
    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        logging.info(f"Retrieving gridded {variable} data for {entity_code}.")

        # Get the shape of the country or subdivision.
        entity_shape = utils.shapes.get_entity_shape(
            entity_code, make_plot=False
        )

        # Get the lateral bounds of the country or subdivision.
        entity_bounds = utils.shapes.get_entity_bounds(
            entity_shape
        )  # West, South, East, North

        # Loop over the year, model, and scenario combinations.
        for (
            selected_year,
            selected_model,
            selected_scenario,
        ) in year_model_scenario_list:
            # Define the full file paths of the ERA5 data.
            entity_file_path_without_ext = os.path.join(
                result_directory,
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
                # Get the CDS variable name.
                cds_variable_name = CDS_VARIABLES[variable][
                    "projections"
                    if selected_model and selected_scenario
                    else "reanalysis"
                ]

                # Download the weather data from CDS.
                _download_data(
                    entity_file_path_without_ext,
                    [selected_year],
                    cds_variable_name,
                    "projections"
                    if selected_model and selected_scenario
                    else "reanalysis",
                    selected_model,
                    selected_scenario,
                    bounds=entity_bounds,
                )

        logging.info(
            f"Gridded {variable} data for {entity_code} has been "
            "successfully "
            "retrieved and saved."
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
    source: str = "cds",
) -> None:
    """
    Download and extract gridded weather data.

    This function retrieves weather data from the Copernicus Climate
    Data Store (CDS) or from ARCO-ERA5 for the countries and
    subdivisions of interest. The data is saved into NetCDF files in the
    specified directory.

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
    source : str, optional
        The source of the reanalysis data, "cds" or "arco" (see the
        description of the module). The projections come from the CDS.

    Raises
    ------
    ValueError
        If the variable or the source is not supported.
    """
    if source not in SOURCES:
        raise ValueError(
            f"Source {source} is not supported. Supported sources are: "
            f"{', '.join(SOURCES)}."
        )

    # Get the directory to store the population density data.
    result_directory = utils.config.read_folders_structure()[
        "gridded_weather_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )

    # Define the available years for the historical weather data.
    # Historical data is available from 1940 but it is not necessary to
    # go that far back for our purposes.
    available_historical_years = list(range(1990, pd.Timestamp.now().year + 1))

    # Define the available years for the future weather data.
    available_future_years = list(range(pd.Timestamp.now().year, 2101))

    # Get the available scenarios for each climate model.
    available_scenarios_for_model = get_available_scenarios_for_model()

    # Define the available weather variables.
    available_variables = ["temperature"]

    if variable not in available_variables:
        raise ValueError(
            f"Variable {variable} is not implemented yet. "
            f"Supported variables are: {', '.join(available_variables)}."
        )

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

    if source == "arco":
        year_model_scenario_list = _retrieve_from_arco(
            variable, codes, year_model_scenario_list, result_directory
        )
        if not year_model_scenario_list:
            return

    # If there are many codes, download the global data and then extract
    # the data for each country and subdivision, and otherwise download
    # the data of each of them.
    if len(codes) > 5:
        _retrieve_global_from_cds(
            variable, codes, year_model_scenario_list, result_directory
        )
    else:
        _retrieve_each_from_cds(
            variable, codes, year_model_scenario_list, result_directory
        )
