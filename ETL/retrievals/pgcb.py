# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:
    This module provides functions to retrieve electricity demand data
    from the website of the Power Grid Company of Bangladesh (PGCB),
    now Power Grid Bangladesh PLC. The data spans from 2014 to the
    present and is obtained from the Excel files available on the PGCB
    website.

    Note:
    Retrieving all the data take a considerable amount of time,
    potentially up to 2 hours in total. This is due to the large number
    of Excel sheets that need to be processed.

    Source: https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09IiwibWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4NzRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/show_report
"""  # noqa: W505

import logging
import re

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


def _clean_and_format(date: str) -> str:
    """
    Clean and format the date string to YYYY-MM-DD.

    Parameters
    ----------
    date : str
        The date string to be cleaned and formatted.

    Returns
    -------
    str
        The date string in the format YYYY-MM-DD.

    Raises
    ------
    ValueError
        If the date string cannot be inferred.
    """
    # Create a dictionary to fix known typos in the date strings.
    # The file name for 2022-04-25 does not have the date in it. The
    # regular expression captures only "t". Add it manually.
    fix_typo = {
        "t": "25-04-2022",
        "2209-2023": "22-09-2023",
        "21-8-20223": "21-08-2023",
        "149.2.2023": "19-02-2023",
        "31.2.2022": "31-12-2022",
        "03/01/202": "03-01-2022",
        "05-052020": "05-05-2020",
        "04-11-219": "04-11-2019",
    }

    # Fix known typos in the date string.
    if date in fix_typo:
        date = fix_typo[date]

    # Clean the date strings from trailing whitespaces and dots and
    # replace different separators with a hyphen.
    date = date.strip().strip(".").replace(".", "-").replace("/", "-")

    # Extract the date components.
    day = date.split("-")[0]
    month = date.split("-")[1]
    year = date.split("-")[2]

    # Add leading zero to month if needed.
    if len(month) == 1:
        month = f"0{month}"

    # Add leading thousand to year if needed.
    if len(year) == 2:
        year = f"20{year}"

    # Reconstruct the date string.
    date = f"{year}-{month}-{day}"

    try:
        # Validate the date format.
        pandas.to_datetime(date, format="%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Cannot infer the date from the string: {date}.")

    return date


def _check_input_parameters() -> None:
    """Check if the input parameters are valid."""
    logging.debug(
        "Checking if the input parameters are valid would be extremely "
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
    logging.info("Retrieving the available requests from the PGCB website.")

    # List of dates for which the files are known to be unavailable.
    dates_not_available = [
        "2014-04-12",  # Some data is missing in this file.
        "2016-01-07",  # File corrupted.
        "2016-01-23",  # Missing file.
        "2016-01-24",  # Missing file.
        "2016-01-25",  # Missing file.
        "2016-01-26",  # Missing file.
        "2016-01-27",  # Missing file.
        "2016-01-28",  # Missing file.
        "2016-01-29",  # Missing file.
        "2016-01-30",  # Missing file.
        "2016-01-31",  # Missing file.
        "2016-02-01",  # Missing file.
        "2016-02-02",  # Missing file.
        "2017-02-13",  # Missing file.
        "2017-02-14",  # Missing file.
        "2017-02-15",  # Missing file.
        "2017-02-16",  # Missing file.
        "2018-02-26",  # Missing file.
        "2018-11-10",  # Missing file.
        "2022-06-14",  # Missing file.
        "2023-01-13",  # Missing file.
    ]

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

        # Use regular expressions to find all file numbers and
        # extensions.
        file_info = re.findall(
            r"https://erp\.powergrid\.gov\.bd/web/files/download\?location=erp%2Fweb%2Freport_docs%2F(\d+)\.(xlsm|xlsx|xls)",  # noqa: W505
            html_content.text,
        )

        # Remove duplicates and keep the order.
        file_info = list(dict.fromkeys(file_info))

        # Use regular expressions to find all dates.
        dates = re.findall(
            r'<td style="text-align: left; font-size: 14px;">(?:[a-zA-Z]+)(?:[\s_]+)(?:[a-zA-Z]+)(?:[\s_-]*)(.+)</td>',  # noqa: W505
            html_content.text,
        )

        # Format the dates to YYYY-MM-DD.
        dates = [_clean_and_format(date) for date in dates]

        # Combine the file numbers, extensions, and dates into a list
        # of tuples.
        requests_on_page = [
            (file_number, extension, date)
            for (file_number, extension), date in zip(file_info, dates)
            if date not in dates_not_available
        ]

        # Add the requests from the current page to the list of
        # available requests.
        available_requests += requests_on_page

    return available_requests


def get_url(file_number: str, extension: str) -> str:
    """
    Get the URL of the electricity demand data on the PGCB website.

    Parameters
    ----------
    file_number : str
        The file number of the Excel file.
    extension : str
        The file extension of the Excel file (xls, xlsx, xlsm).

    Returns
    -------
    str
        The URL for the electricity demand data request.
    """
    return (
        "https://erp.powergrid.gov.bd/web/files/download?"
        f"location=erp%2Fweb%2Freport_docs%2F{file_number}.{extension}"
    )


def download_and_extract_data_for_request(
    file_number: str, extension: str, date: str
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
    date : str
        The date in the format YYYY-MM-DD.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for {date}.")

    # Get the URL of the electricity demand data.
    url = get_url(file_number, extension)

    # Fetch the data from the URL.
    excel_file: pandas.ExcelFile = utils.fetcher.fetch_data(
        url, "html", read_as="excel_file", verify_ssl=False
    )

    # Extract the name of the sheet containing the demand data.
    if "L-Curve" in excel_file.sheet_names:
        demand_sheet = "L-Curve"
    elif "L.curve" in excel_file.sheet_names:
        demand_sheet = "L.curve"
    else:
        logging.error("No valid sheet found. Skipping this file.")
        return pandas.Series(dtype=float)

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
        logging.error("No valid header/row found. Skipping this file.")
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
