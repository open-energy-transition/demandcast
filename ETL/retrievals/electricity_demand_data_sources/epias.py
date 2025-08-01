# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Enerji Piyasaları İşletme A.Ş. (EPIAS) in
    Turkey. The data is retrieved by registering on the website and
    downloading the data manually. The user needs to create an account
    on the EPIAS website, which is free of charge. After registration,
    the user can log in to the website and download the data.

    Source: https://seffaflik.epias.com.tr/
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
    logging.debug("Use for any purpose with attribution to EPIAS.")
    logging.debug("Source: https://seffaflik.epias.com.tr/about/about")
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EPIAS website.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data from the EPIAS website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://seffaflik.epias.com.tr/"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the EPIAS
    website. This function assumes that the data has been downloaded and
    is available in the specified folder.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the data folder.
    data_directory = utils.directories.read_folders_structure()[
        "manually_downloaded_data_folder"
    ]

    # Get the paths of the downloaded files that start with "EPI".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("EPI")
    ]

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pandas.concat(
        [pandas.read_excel(file_path) for file_path in downloaded_file_paths]
    )

    # Extract the electricity demand data from the dataset.
    electricity_demand_time_series = pandas.Series(
        dataset["Tüketim Miktarı(MWh)"].values,
        index=pandas.to_datetime(dataset["Tarih"], format="%d/%m/%Y %H:%M:%S"),
    )

    # Add one hour to the index because the electricity demand seems to
    # be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize(
            "Europe/Istanbul", ambiguous="NaT", nonexistent="NaT"
        )
    )

    return electricity_demand_time_series
