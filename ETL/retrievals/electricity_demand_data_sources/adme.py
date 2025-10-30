# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Administrador del Mercado Eléctrico (ADME)
    in  Uruguay. The data is retrieved manually for the years from
    2019-01-01 to 2025-09-30. The data is retrieved all at once.

    Source: https://adme.com.uy/controlpanel.php
"""

import logging
import os

import pandas
import utils.directories


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Open data.")
    logging.debug("Source: https://adme.com.uy/datosabiertos.html")
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the ADME website.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data from the ADME website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://adme.com.uy/panelControl/gpf.php"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the ADME
    website. This function assumes that the data has been downloaded and
    is available in the specified folder.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    FileNotFoundError
        If the data file is not found in the specified folder.
    """
    # Get the data folder.
    data_directory = utils.directories.read_folders_structure()[
        "manually_downloaded_electricity_demand_folder"
    ]

    # Get the paths of the downloaded files that start with "ADM".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("ADM")
    ]

    if not downloaded_file_paths:
        raise FileNotFoundError(
            f"The data for ADME has not been found in the folder "
            f"{data_directory}. Please download the data manually from "
            f"{get_url()}. The data files must be named starting with 'ADM'."
        )

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pandas.concat(
        [
            pandas.read_csv(file_path, sep=";")
            for file_path in downloaded_file_paths
        ],
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["Demanda"].values,
        index=pandas.to_datetime(dataset["Fecha"], format="%d-%m-%Y %H:%M"),
    )

    # Add the timezone information.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("America/Montevideo")
    )

    return electricity_demand_time_series
