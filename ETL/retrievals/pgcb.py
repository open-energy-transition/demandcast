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

    Source: https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09IiwibWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4NzRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/show_report?page=140
"""  # noqa: W505

import logging
import ssl
import warnings

import pandas
import utils.fetcher
from urllib3.exceptions import InsecureRequestWarning

# Ignore SSL certificate warnings
warnings.simplefilter("ignore", InsecureRequestWarning)

# Globally ignore SSL certificate verification
ssl._create_default_https_context = ssl._create_unverified_context


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


def _check_input_parameters(
    file_info: tuple[int, str], available_files: list[tuple[int, str]]
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    file_info : tuple[int, str]
        A tuple containing the file number and the extension.
    available_files : list of tuple[int, str]
        Pre-fetched list of available (file_number, extension) pairs.
    """
    # Check if the (file_number, extension) pair is supported
    assert file_info in available_files, (
        f"File {file_info[0]}.{file_info[1]} is not supported."
    )


def get_available_requests() -> list[tuple[int, str]]:
    """
    Get the available requests.

    This function retrieves the available file numbers and their
    extensions from the PGCB website.

    Returns
    -------
    list of tuple[int, str]
        The list of available (file_number, extension) requests.
    """
    available_files = []

    # Define ranges with preferred extensions
    ranges = [
        (197, 846, "xlsm"),
        (847, 2292, "xls"),
        (2293, 4432, "xlsm"),
        (4433, 99999, "xlsx"),  # large upper bound for open-ended
    ]

    for start, end, preferred_ext in ranges:
        consecutive_missing = 0
        for file_number in range(start, end + 1):
            found = False

            for extension in [preferred_ext]:
                url = (
                    f"https://erp.powergrid.gov.bd/web/files/download?"
                    f"location=erp%2Fweb%2Freport_docs%2F{file_number}.{extension}"
                )
                try:
                    utils.fetcher.fetch_data(
                        url=url,
                        content_type="html",
                        read_as="plain",
                        retries=1,
                        verify_ssl=False,
                    )
                    available_files.append((file_number, extension))
                    logging.info(
                        f"Found available file: {file_number}.{extension}"
                    )
                    found = True
                    break  # stop checking other extensions for this file_number
                except Exception:
                    continue

            if found:
                consecutive_missing = 0  # reset counter on success
            else:
                consecutive_missing += 1

            if consecutive_missing >= 20:
                logging.info(
                    f"Stopping early in range {start}-{end} after "
                    f"{consecutive_missing} consecutive missing files."
                )
                break

    return available_files


def get_url(file_info: tuple[int, str]) -> str:
    """
    Get the URL of the electricity demand data on the PGCB website.

    Parameters
    ----------
    file_info : tuple[int, str]
        A tuple containing the file number and the extension.

    Returns
    -------
    str
        The URL for the electricity demand data request.
    """
    file_number, extension = file_info
    return (
        "https://erp.powergrid.gov.bd/web/files/download?"
        f"location=erp%2Fweb%2Freport_docs%2F{file_number}.{extension}"
    )


def download_and_extract_data_for_request(
    file_number: int, extension: str
) -> pandas.Series | None:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the PGCB website for the given date range.

    Parameters
    ----------
    file_number : int
        The number of the file to read.
    extension : str
        The file extension (xls, xlsm, xlsx).

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
        Returns None if no valid sheet/date/header is found.
    """
    file_info = (file_number, extension)

    logging.info(
        "Retrieving electricity demand data from the "
        f"file {file_number}.{extension}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(file_info)
    possible_sheets = ["L-Curve", "L.curve"]

    dataset = None
    sheet_date = None

    # Try all possible sheets
    for sheet_name in possible_sheets:
        try:
            raw_data = utils.fetcher.fetch_data(
                url,
                "excel",
                excel_kwargs={"sheet_name": sheet_name, "header": None},
                verify_ssl=False,
            )
        except Exception:
            continue

        # Detect sheet date from first few rows
        for i in range(5):
            cell_value = str(raw_data.iloc[i, 1]).strip()
            possible_date = None

            try:
                if 850 <= file_number <= 2292:
                    # Range 2: mm/dd/yy
                    possible_date = pandas.to_datetime(
                        cell_value, dayfirst=False, errors="coerce"
                    )

                elif file_number >= 4433:
                    # Range 4: dd/mm/yyyy
                    possible_date = pandas.to_datetime(
                        cell_value, dayfirst=True, errors="coerce"
                    )

                else:
                    # Range 1 & 3: dd-mon-yy
                    possible_date = pandas.to_datetime(
                        cell_value, errors="raise"
                    )

                # If parsing failed, try automatic detection
                if possible_date is pandas.NaT or possible_date is None:
                    possible_date = pandas.to_datetime(
                        cell_value, errors="coerce"
                    )

                if (
                    possible_date is not pandas.NaT
                    and possible_date is not None
                ):
                    sheet_date = possible_date.date()
                    break

            except Exception:
                continue

        if sheet_date is None:
            continue

        # Detect header row
        header_row = None
        for i in range(5):
            row = raw_data.iloc[i].astype(str).str.upper()
            if "TIME" in row.to_numpy() and "TOTAL" in row.to_numpy():
                header_row = i
                break
        if header_row is None:
            continue

        try:
            dataset = utils.fetcher.fetch_data(
                url,
                "excel",
                excel_kwargs={"sheet_name": sheet_name, "header": header_row},
                verify_ssl=False,
            )
        except Exception:
            dataset = None
            continue

    # If nothing usable was found, return empty Series
    if dataset is None or sheet_date is None:
        logging.warning(
            f"Skipping file {file_number}.{extension}: could not find valid sheet, date, or header."
        )
        return pandas.Series(dtype="float64")  # empty

    # Remove any rows where TIME is '24:00'
    dataset = dataset[dataset["TIME"] != "24:00"]

    # Build the DateTime column by combining sheet_date and TIME column
    dataset["DateTime"] = pandas.to_datetime(
        dataset["TIME"].apply(lambda t: f"{sheet_date} {t}"),
        errors="coerce",
    )

    # Drop rows with invalid DateTime or TOTAL
    dataset = dataset.dropna(subset=["DateTime", "TOTAL"])

    # Remove duplicates just in case (e.g., 00:00 appearing twice)
    dataset = dataset.drop_duplicates(subset=["DateTime"])

    # Define the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["TOTAL"].values, index=dataset["DateTime"]
    )

    # Sort the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.sort_index()
    )

    # Add the timezone information.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("Asia/Dhaka")
    )

    return electricity_demand_time_series
