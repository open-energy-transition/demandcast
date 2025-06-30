# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script provides functions to retrieve the electricity demand
    data from the website of National Institution for Transforming India
    (NITI) Aayog in India. The data is retrieved by submitting a request
    to the NITI Aayog website. The user then able to download the data.

    Source: https://iced.niti.gov.in
"""

import logging
import os

import pandas
import utils.directories


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the NITI Aayog website.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data from NITI Aayog website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://iced.niti.gov.in/energy/electricity/distribution/national-level-consumption/load-curve"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the
    NITI Aayog website. This function assumes that the data has
    been downloaded and is available in the specified folder.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the data folder.
    data_directory = utils.directories.read_folders_structure()[
        "manually_downloaded_data_folder"
    ]

    # Get the paths of the downloaded files that start with "NIT".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("NIT")
    ]

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pandas.concat(
        [pandas.read_excel(file_path) for file_path in downloaded_file_paths]
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["Hourly Demand Met (in MW)"].values,
        index=pandas.to_datetime(
            dataset["Year"].astype(str) + " " + dataset["Date"],
            format="%Y %d-%b %I%p",
        ),
    )

    # Add one hour to the index because the electricity demand seems to
    # be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Kolkata")
    )

    return electricity_demand_time_series
