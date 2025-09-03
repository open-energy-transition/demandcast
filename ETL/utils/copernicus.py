# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to set up the connection to the
    Copernicus Climate Data Store (CDS) and retrieve weather data from
    the ERA5 dataset.

    Source: https://cds.climate.copernicus.eu/how-to-api
"""

import os

import cdsapi
from dotenv import load_dotenv

import utils.directories


def get_request(
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
        The weather model of interest.
    scenario : str | None
        The scenario of interest.
    bounds : list[float], optional
        The lateral bounds of the area of interest
        (West, South, East, North).

    Returns
    -------
    request : dict[str, str | list[str] | list[float]]
        The request for the ERA5 data.
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


def download_data(
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
    file_path : str
        The full file path to store the downloaded data.
    year : int
        The year of the data retrieval.
    variable : str
        The weather variable of interest.
    dataset : str
        The dataset to be used for the retrieval of the data.
        Supported datasets are "reanalysis-era5-single-levels" and
        "projections-cmip6".
    model : str | None
        The weather model of interest.
    scenario : str | None
        The scenario of interest.
    bounds : list of float, optional
        The lateral bounds of the area of interest
        (West, South, East, North).
    """
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
    elif dataset == "projections-cmip6" or dataset == "projections":
        dataset = "projections-cmip6"
    else:
        raise ValueError(f"Dataset {dataset} is not supported.")

    # Define the request.
    request = get_request(variable, year, model, scenario, bounds)
    client.retrieve(dataset, request, file_path)
