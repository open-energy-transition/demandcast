"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the National Grid Corporation of the
    Philippines (NGCP). The data is downloaded from Jan 1, 2013 to Dec
    31, 2025. The data is retrieved all at once.

    Source: https://www.ngcp.ph/operations#operations
"""

import logging

import pandas as pd
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


def download_and_extract_data() -> pd.Series:
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
    TypeError
        If the extracted data is not a pandas ExcelFile or DataFrame.
    ValueError
        If the Excel file does not have the sheets of the main regions.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Download the Excel file once, and read its sheets below.
    excel_file = utils.fetcher.fetch_data(
        url,
        "html",
        read_as="excel_file",
        header_params={"User-Agent": "Mozilla/5.0"},
    )

    if not isinstance(excel_file, pd.ExcelFile):
        raise TypeError(
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
        for sheet in map(str, excel_file.sheet_names)
        if sheet.split(" ")[0].upper() in regions
    }

    if len(sheet_names) < 3:
        raise ValueError(
            "The extracted Excel file from NGCP does not contain all "
            "the required sheets for the main regions: Luzon, Visayas, "
            "and Mindanao."
        )

    # Define the number of rows to skip for each region's sheet.
    rows_to_skip = {
        "LUZON": 1,
        "VISAYAS": 2,
        "MINDANAO": 1,
    }

    all_data = []

    # Read and process each sheet individually.
    for region in regions:
        dataset = excel_file.parse(
            sheet_names[region], skiprows=rows_to_skip[region]
        )

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pd.DataFrame):
            raise TypeError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )

        # Keep only "Date" and hours 1 to 24.
        selected_columns = ["DATE", *range(1, 25)]
        dataset = dataset.loc[:, selected_columns]

        # Reshape to long format.
        dataset = dataset.melt(
            id_vars=["DATE"], var_name="Hour", value_name="Demand"
        )
        dataset["Hour"] = pd.to_numeric(dataset["Hour"])
        dataset["Demand"] = pd.to_numeric(dataset["Demand"])

        # Convert date and hour columns into hourly timestamps.
        dataset["Datetime"] = pd.to_datetime(
            dataset["DATE"]
        ) + pd.to_timedelta(dataset["Hour"], unit="h")

        # Retain only Datetime and Demand columns.
        dataset = dataset[["Datetime", "Demand"]]
        all_data.append(dataset)

    # Combine and aggregate data across all regions. An hour without the
    # demand of every region gets no total, rather than a partial one.
    combined = pd.concat(all_data)
    combined = (
        combined.groupby("Datetime").sum(min_count=len(regions)).sort_index()
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        combined["Demand"].values, index=combined.index
    )

    # Add the timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Asia/Manila")
    )

    return electricity_demand_time_series
