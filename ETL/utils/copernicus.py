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
import utils.directories
from dotenv import load_dotenv


def get_request(
    ERA5_variable: str, year: int, bounds: list[float] | None = None
) -> dict[str, str | list[str] | list[float]]:
    """
    Get the request for the ERA5 data from the Copernicus CDS.

    Parameters
    ----------
    ERA5_variable : str
        The ERA5 variable of interest.
    year : int
        The year of the data retrieval.
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
        "product_type": ["reanalysis"],
        "variable": [ERA5_variable],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "year": [str(year)],
        "month": [f"{mm:02d}" for mm in range(1, 13)],
        "day": [f"{dd:02d}" for dd in range(1, 32)],
        "time": [f"{tt:02d}:00" for tt in range(24)],
    }

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
    year: int,
    ERA5_variable: str,
    file_path: str,
    bounds: list[float] | None = None,
) -> None:
    """
    Download the ERA5 data from the Copernicus Climate Data Store (CDS).

    Parameters
    ----------
    year : int
        The year of the data retrieval.
    ERA5_variable : str
        The ERA5 variable of interest.
    file_path : str
        The full file path to store the ERA5 data.
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
    dataset = "reanalysis-era5-single-levels"

    # Define the request.
    request = get_request(ERA5_variable, year, bounds)
    client.retrieve(dataset, request, file_path)
