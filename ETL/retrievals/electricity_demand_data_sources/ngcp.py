# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the National Grid Corporation of the
    Philippines (NGCP). The data is downloaded from Jan 1, 2013 to Dec
    31, 2024. The data is retrieved all at once.

    Source: https://www.ngcp.ph/operations#operations
"""

import logging

import pandas
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("All rights reserved by NGCP.")
    logging.debug("Source: https://ngcp.ph")
    return False


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for Philippines.
    """
    logging.debug("The data is retrieved all at once.")


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
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    for Philippines.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Read the Excel file from the URL.
    excel_file = utils.fetcher.fetch_data(url, "html", read_as="excel_file")

    if not isinstance(excel_file, pandas.ExcelFile):
        raise ValueError(
            f"The extracted data is a {type(excel_file)} object, "
            "expected a pandas ExcelFile."
        )

    # Define the main regions in the Philippines.
    regions = ["LUZON", "VISAYAS", "MINDANAO"]

    # Extract the sheet names from the Excel file that refer to the
    # main regions: Luzon, Visayas, and Mindanao. The other 5 sheets in
    # the Excel file are sub-regions of Visayas, and their data is
    # already aggregated in the main Visayas sheet.
    sheet_names = {
        sheet.split(" ")[0].upper(): sheet
        for sheet in excel_file.sheet_names
        if sheet.split(" ")[0].upper() in regions
    }

    if len(sheet_names) < 3:
        raise ValueError(
            "The extracted Excel file from NGCP does not contain all "
            "the required sheets for the main regions: Luzon, Visayas, "
            "and Mindanao."
        )

    # Define the number of rows to skip for each region's sheet.
    rows_to_skeep = {
        "LUZON": 1,
        "VISAYAS": 2,
        "MINDANAO": 1,
    }

    all_data = []

    # Fetch and process each sheet individually.
    for region in regions:
        dataset = utils.fetcher.fetch_data(
            url,
            "excel",
            excel_kwargs={
                "storage_options": {"User-Agent": "Mozilla/5.0"},
                "sheet_name": sheet_names[region],
                "skiprows": rows_to_skeep[region],
            },
        )

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pandas.DataFrame):
            raise ValueError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )

        # Keep only "Date" and hours 1 to 24.
        selected_columns = ["DATE"] + list(range(1, 25))
        dataset = dataset.loc[:, selected_columns]

        # Reshape to long format.
        dataset = dataset.melt(
            id_vars=["DATE"], var_name="Hour", value_name="Demand"
        )
        dataset["Hour"] = pandas.to_numeric(dataset["Hour"])
        dataset["Demand"] = pandas.to_numeric(dataset["Demand"])

        # Convert date and hour columns into hourly timestamps.
        dataset["Datetime"] = pandas.to_datetime(
            dataset["DATE"]
        ) + pandas.to_timedelta(dataset["Hour"], unit="h")

        # Retain only Datetime and Demand columns.
        dataset = dataset[["Datetime", "Demand"]]
        all_data.append(dataset)

    # Combine and aggregate data across all regions.
    combined = pandas.concat(all_data)
    combined = combined.groupby("Datetime").sum().sort_index()

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        combined["Demand"].values, index=combined.index
    )

    # Add the timezone information to the index.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Manila")
    )

    return electricity_demand_time_series
