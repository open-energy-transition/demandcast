# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from a publicly available repository with data provided by the
    National Transmission & Despatch Company (NTDC) in Pakistan. The
    data is retrieved by registering on the website and downloading
    the data manually. The user needs to create an account on the
    Kaggle website, which is free of charge. After registration,
    the user can log in to the website and download the data.

    Source: https://www.kaggle.com/datasets/tentative/ntdc-dataset
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
    logging.debug("CC0.")
    logging.debug(
        "Source: https://www.kaggle.com/datasets/tentative/ntdc-dataset"
    )
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for Pakistan.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data for Pakistan.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.kaggle.com/datasets/tentative/ntdc-dataset"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data for
    Pakistan. This function assumes that the data has
    been downloaded and is available in the specified folder.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Get the data folder.
    data_directory = utils.directories.read_folders_structure()[
        "manually_downloaded_data_folder"
    ]

    # Get the paths of the downloaded files that start with "NTD".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("NTD")
    ]

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pandas.concat(
        [pandas.read_csv(file_path) for file_path in downloaded_file_paths]
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Define the new index.
        index = pandas.to_datetime(
            dataset.iloc[:, 0].astype(str)
            + " "
            + (dataset.iloc[:, 1].astype(str).astype(int) - 1).astype(str),
            format="%d/%m/%Y %H",
        ) + pandas.Timedelta(hours=1)

        # Remove commas and convert SYSLOAD to numeric.
        dataset["SYSLOAD"] = pandas.to_numeric(
            dataset["SYSLOAD"].astype(str).str.replace(",", ""),
            errors="coerce",
        )

        # Define the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["SYSLOAD"].values,
            index=index,
        )

        # Add the timezone information.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Asia/Karachi")
        )

        return electricity_demand_time_series
