# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:
    This module provides functions to retrieve electricity demand data
    from the website of the Power Grid Company of Bangladesh (PGCB),
    now Power Grid Bangladesh PLC. The data spans from 2014 to the present
    and is obtained from the Excel files available on the PGCB website.

    Note:
    Retrieving data over an extended historical period (e.g., multiple
    years) may take a considerable amount of time — potentially up to
    14 hours in total. This is due to the large number of Excel
    sheets that need to be processed.

    Source: https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09IiwibWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4NzRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/show_report
"""  # noqa: W505

import logging
import re

import numpy
import pandas
import requests
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("All rights reserved by PGCB.")
    logging.debug("Source: https://pgcb.gov.bd/l")
    return False


def _clean_date_string(date: str) -> str:
    """
    Clean the date string to the correct format.

    Parameters
    ----------
    date : str
        The date string to be cleaned.

    Returns
    -------
    str
        The cleaned date string in the format YYYY-MM-DD.
    """
    # Clean the date string.
    date = date.replace("%2F", "-")
    date = date.replace(".", "-")
    date = date.replace("%20", "")

    # Extract the date components.
    day = date.split("-")[0]
    month = date.split("-")[1]
    year = date.split("-")[2]

    # Add leading thousand to year if needed.
    if len(year) == 2:
        year = f"20{year}"

    # Fix a typo in one of the filenames.
    if year == "20223":
        year = "2023"

    # Add leading zero to month if needed.
    if len(month) == 1:
        month = f"0{month}"

    # Reconstruct the date string.
    date = f"{year}-{month}-{day}"

    return date


def _check_input_parameters() -> None:
    """Check if the input parameters are valid."""
    logging.debug(
        "Checking if the input parameters are valis would be extremely "
        "time-consuming. Skipping this step."
    )


def get_available_requests() -> list[tuple[str, str, str]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the PGCB website. Each request corresponds to
    a specific Excel file identified by a unique number, file
    extension, and date. The function scrapes the website to find
    all available files and returns a list of tuples containing
    the file number, file extension, and date.

    Returns
    -------
    available_requests : list[tuple[str, str, str]
        A list of tuples, each containing the file number, file
        extension, and date in the format.
    """
    # Initialize an empty list to store available requests.
    available_requests = []

    # Iterate through a reasonable range of pages to find all available
    # files. The maximum page number is currently 142, but we use 200
    # to include any future additions.
    for page_number in range(1, 200):
        # Construct the URL for the current page.
        page_url = (
            "https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9"
            "FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09Iiwi"
            "bWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4N"
            "zRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/"
            f"show_report?page={page_number}"
        )

        # Fetch the HTML content of the page.
        html_content: requests.Response = utils.fetcher.fetch_data(
            url=page_url,
            content_type="html",
            read_as="plain",
            verify_ssl=False,
        )

        # Parse the HTML content to find the parameters in the URLs.
        available_requests += re.findall(
            r'"https://erp.powergrid.gov.bd/web/files/download\?location=erp%2Fweb%2Freport_docs%2F(\d+).(xlsm|xls|xlsx)&amp;title=Daily%20Report%20(.+)"target',  # noqa: W505
            html_content.text,
        )

    return available_requests


def get_url(file_number: str, extension: str, unformatted_date: str) -> str:
    """
    Get the URL of the electricity demand data on the PGCB website.

    Parameters
    ----------
    file_number : str
        The file number of the Excel file.
    extension : str
        The file extension of the Excel file (xls, xlsx, xlsm).
    unformatted_date : str
        The date in the format DD-MM-YYYY or similar.

    Returns
    -------
    str
        The URL for the electricity demand data request.
    """
    return (
        "https://erp.powergrid.gov.bd/web/files/download?"
        f"location=erp%2Fweb%2Freport_docs%2F{file_number}.{extension}"
        f"&title=Daily%20Report%20{unformatted_date}"
    )


def download_and_extract_data_for_request(
    file_number: str, extension: str, unformatted_date: str
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the PGCB website for the given date range.

    Parameters
    ----------
    file_number : str
        The file number of the Excel file.
    extension : str
        The file extension of the Excel file (xls, xlsx, xlsm).
    unformatted_date : str
        The date in the format DD-MM-YYYY or similar.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
        Returns None if no valid sheet/date/header is found.
    """
    # Convert date to the correct format.
    date = _clean_date_string(unformatted_date)

    logging.info(f"Retrieving electricity demand data for {date}.")

    # Get the URL of the electricity demand data.
    url = get_url(file_number, extension, unformatted_date)

    # Fetch the data from the URL.
    excel_file: pandas.ExcelFile = utils.fetcher.fetch_data(
        url, "html", read_as="excel_file", verify_ssl=False
    )

    # Extract the name of the sheet containing the demand data.
    demand_sheet = [
        sheet
        for sheet in excel_file.sheet_names
        if "L-Curve" in sheet or "L.curve" in sheet
    ][0]

    # Read the sheet containing the demand data.
    dataset = pandas.read_excel(excel_file, sheet_name=demand_sheet)

    # Find the row that contains both "TIME" and "TOTAL".
    header_row = None
    time_col = None
    total_col = None
    for id in range(len(dataset)):
        row = dataset.iloc[id].astype(str).str.upper()
        if "TIME" in row.to_list() and "TOTAL" in row.to_list():
            header_row = id
            time_col = dataset.iloc[id][row == "TIME"].iloc[0]
            total_col = dataset.iloc[id][row == "TOTAL"].iloc[0]
            break

    if header_row is None or time_col is None or total_col is None:
        logging.error(
            f"No valid Excel sheet/date/header found for {date}. "
            "Skipping this date."
        )
        return pandas.Series(dtype=float)

    # Extract the following 48 rows containing the time and demand data.
    dataset = pandas.read_excel(
        excel_file,
        sheet_name=demand_sheet,
        header=header_row + 1,
        nrows=48,
        usecols=[time_col, total_col],
    )

    # Define the new index.
    index = pandas.to_datetime([f"{date} {t}" for t in dataset[time_col]])

    # Raise an error if the index is not unique.
    if not index.is_unique:
        logging.error(f"The index is not unique for {date}.")
    if numpy.any(numpy.isnan(index.to_numpy().astype(float))):
        logging.error(f"The index contains NaN values for {date}.")
    if numpy.any(numpy.isnan(dataset["TOTAL"].values)):
        logging.error(f"The data contains NaN values for {date}.")

    # Define the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["TOTAL"].values, index=index
    )

    # Add 30 minutes to each timestamp to represent the end of
    # the half-hour period.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(minutes=30)
    )

    # Add the timezone information.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Dhaka")
    )

    return electricity_demand_time_series
