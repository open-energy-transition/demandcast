# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Eskom in South Africa. The data is
    retrieved by submitting a request to the Eskom website. The user
    then receives a link on the provided email address to download the
    data.

    Source: https://www.eskom.co.za/dataportal/data-request-form/
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
    logging.debug(
        "Content may not be used for any commercial and non-private purposes."
    )
    logging.debug(
        "Source: https://www.eskom.co.za/wp-content/uploads/2021/10/WEBSITE-TERMS-AND-CONDITIONS_Sep2021.pdf"  # noqa: W505
    )
    return False


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the Eskom website.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data from the Eskom website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.eskom.co.za/dataportal/cf-api/CF600011bdba174"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the Eskom
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

    # Get the paths of the downloaded files that start with "ESK".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("ESK")
    ]

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pandas.concat(
        [pandas.read_csv(file_path) for file_path in downloaded_file_paths]
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["RSA Contracted Demand"].values,
        index=pandas.to_datetime(
            dataset["Date Time Hour Beginning"], format="%Y-%m-%d %H:%M:%S %p"
        ),
    )

    # Add one hour to the index because the electricity demand seems to
    # be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Africa/Johannesburg")
    )

    return electricity_demand_time_series
