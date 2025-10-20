# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script provides functions to retrieve the electricity demand
    data from the website of Korean Open Government Data (KROGD) portal
    in South Korea. The data is retrieved manually for the years from
    2013-01-01 to 2024-12-31.

    Source: https://www.data.go.kr/
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
    logging.debug(
        "Source: https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do"
    )
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the KROGD Portal.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data from the KROGD portal.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.data.go.kr/data/15065266/fileData.do"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the
    KROGD portal. This function assumes that the data has been
    downloaded and is available in the specified folder.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.

    Raises
    ------
    FileNotFoundError
        If the data file is not found in the specified folder.
    """
    # Get the data folder.
    data_directory = utils.directories.read_folders_structure()[
        "manually_downloaded_electricity_demand_folder"
    ]

    # Get the paths of the downloaded files that start with "KRO".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("KRO")
    ]

    if not downloaded_file_paths:
        raise FileNotFoundError(
            f"The data for KROGD has not been found in the folder "
            f"{data_directory}. Please download the data manually from "
            f"{get_url()}. The data files must be named starting with 'KRO'."
        )

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pandas.concat(
        [
            pandas.read_csv(file_path, encoding="euc-kr")
            for file_path in downloaded_file_paths
        ]
    )

    # The column names have the time information. Rearrange the
    # columns to have the time information on another column.
    dataset = dataset.melt(
        id_vars=dataset.columns[0], var_name="Hour", value_name="Value"
    )

    # Define the new index.
    index = pandas.to_datetime(
        dataset.iloc[:, 0].astype(str)
        + " "
        + (
            dataset.iloc[:, 1].astype(str).str.replace("시", "").astype(int)
            - 1
        ).astype(str),
        format="%Y-%m-%d %H",
    ) + pandas.Timedelta(hours=1)

    # Define the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["Value"].values,
        index=index,
    )

    # Add the timezone information.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Seoul")
    )

    return electricity_demand_time_series
