# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the National Grid Corporation of the
    Philippines (NGCP) in Philippines. The data is downloaded from
    Jan 1, 2013 to Dec 31, 2024. The data is retrieved all at once.

    Source: https://www.ngcp.ph/operations#operations
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
    logging.debug("All rights reserved by NGCP.")
    logging.debug("Source: https://ngcp.ph/privacy")
    return False


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for Philippines.
    """
    logging.debug("The data is retrieved manually.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data for Philippines.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.ngcp.ph/Attachment-Uploads/operations/Hourly%20Demand%20per%20Grid.xlsx"


def download_and_extract_data() -> pandas.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the
    NGCP portal. This function assumes that the data has been
    downloaded and is available in the specified folder.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the data folder.
    data_directory = utils.directories.read_folders_structure()[
        "manually_downloaded_data_folder"
    ]

    # Get the paths of the downloaded files that start with "NGC".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("NGC")
    ]

    # Define sheet names and how many rows to skip before header
    sheets_to_read = {
        "LUZON HOURLY LOAD 2013-2024": 1,
        "VISAYAS HOURLY LOAD 2013-2024": 2,
        "MINDANAO HOURLY LOAD 2013-2024": 1,
    }

    all_data = []

    for sheet, skiprows in sheets_to_read.items():
        # Load the data from the downloaded files into pandas DataFrame.
        dataset = pandas.read_excel(
            downloaded_file_paths[0], sheet_name=sheet, skiprows=skiprows
        )

        # Rename first column to "Date"
        dataset = dataset.rename(columns={dataset.columns[0]: "Date"})

        # Keep only columns "Date" + 1 to 24
        allowed_columns = ["Date"] + list(range(1, 25))  # 1 to 24
        dataset = dataset.loc[
            :,
            dataset.columns.map(
                lambda x: x in allowed_columns
                or str(x).strip() in map(str, allowed_columns)
            ),
        ]

        # Melt into long format
        dataset = dataset.melt(
            id_vars=["Date"], var_name="Hour", value_name="Demand"
        )
        dataset["Hour"] = pandas.to_numeric(dataset["Hour"], errors="coerce")
        dataset["Demand"] = pandas.to_numeric(
            dataset["Demand"], errors="coerce"
        )
        dataset = dataset.dropna(subset=["Date", "Hour", "Demand"])

        # Build full datetime
        dataset["Datetime"] = pandas.to_datetime(
            dataset["Date"], errors="coerce"
        ) + pandas.to_timedelta(dataset["Hour"] - 1, unit="h")
        dataset = dataset[["Datetime", "Demand"]].dropna()
        all_data.append(dataset)

    # Combine all regions and sum by hour
    combined = pandas.concat(all_data)
    combined = combined.groupby("Datetime").sum().sort_index()

    # Convert to Series and localize timezone
    electricity_demand_time_series = pandas.Series(
        combined["Demand"].values, index=combined.index
    )
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Manila")
    )

    return electricity_demand_time_series
