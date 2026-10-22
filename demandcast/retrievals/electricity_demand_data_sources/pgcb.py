"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve electricity demand data
    from the website of the Power Grid Company of Bangladesh (PGCB),
    now Power Grid Bangladesh PLC. The data is obtained from the daily
    reports on the website, one Excel file a day from 2014, which the
    website lists on about 150 pages. Retrieving all the data takes a
    few hours.

    The report of a day has the data of the day before. Its load curve
    gives the total generation of the East and West grids in MW at the
    times of the day in Bangladesh, which has no daylight saving time.
    It is the generation of the power stations on the grid and the
    imports from India and Nepal, which the reports call the demand at
    the generation end: its values at the day and evening peaks are the
    peak generation of the summary. It leaves out the load shed in the
    shortages of supply, which the reports add to the generation for
    their demand, and the rooftop solar, which is not among the power
    stations.
    The readings are at the full hours: the half hours in between are
    the averages of the hours around them, except for one or two in
    the evening peak, so the module keeps the full hours only. The
    midnight at the end of the day is "24:00" until 2024, whose value
    the reports of 2018 to 2024 also give at "00:00" of the same day,
    and "00:00" of the next day from 2025, when the reports end at
    "23:00". The module takes midnight from "24:00" when the report has
    it, and from "00:00" otherwise.

    Source: https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09IiwibWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4NzRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/show_report
"""

import datetime
import logging
import re

import pandas as pd
import requests
import utils.fetcher


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
    date_components = date.split("-")
    if len(date_components) != 3:
        raise ValueError(f"Cannot infer the date from the string: {date}.")
    day, month, year = date_components

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
        pd.to_datetime(date, format="%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Cannot infer the date from the string: {date}."
        ) from e

    return date


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[str, str, str]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the PGCB website. Each request corresponds to
    a specific Excel file identified by a unique number, file
    extension, and date. The function scrapes the website to find
    all available files and returns a list of tuples containing
    the file number, file extension, and date.

    Parameters
    ----------
    code : str
        The code of Bangladesh.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    available_requests : list[tuple[str, str, str]
        A list of tuples, each containing the file number, file
        extension, and date in the format.

    Raises
    ------
    TypeError
        If the extracted response is not a requests.Response object.
    """
    logging.info("Retrieving the available requests from the PGCB website.")

    # List of dates for which the files are known to be unavailable.
    file_dates_not_available = [
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
    ]

    # Initialize an empty list to store available requests.
    available_requests = []

    # Read the pages until the first one without reports. The website
    # has about 150 pages, and adds one every month.
    for page_number in range(1, 1000):
        # Construct the URL for the current page.
        page_url = (
            "https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9"
            "FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09Iiwi"
            "bWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4N"
            "zRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/"
            f"show_report?page={page_number}"
        )

        # Fetch the HTML content of the page.
        html_content = utils.fetcher.fetch_data(
            url=page_url,
            content_type="html",
            read_as="plain",
        )

        # Make sure the response is a requests.Response object.
        if not isinstance(html_content, requests.Response):
            raise TypeError(
                f"The extracted response is a {type(html_content)} object, "
                "expected a requests.Response object."
            )

        # Read each row of the table on its own: the report name gives
        # the date, and the link the number and extension of the file.
        page_has_reports = False
        for row in re.findall(r"<tr>.*?</tr>", html_content.text, re.DOTALL):
            report_name = re.search(
                r'<td style="text-align: left; font-size: 14px;">(.+?)</td>',
                row,
            )
            if report_name is None:
                # The row is the header of the table.
                continue
            page_has_reports = True

            file_info = re.search(
                r"https://erp\.powergrid\.gov\.bd/web/files/download\?location=erp%2Fweb%2Freport_docs%2F(\d+)\.(xlsm|xlsx|xls)",
                row,
            )
            date_text = re.fullmatch(
                r"(?:[a-zA-Z]+)(?:[\s_]+)(?:[a-zA-Z]+)(?:[\s_-]*)(.+)",
                report_name.group(1),
            )
            try:
                date = (
                    _clean_and_format(date_text.group(1))
                    if date_text
                    else None
                )
            except ValueError:
                date = None

            # Skip the rows without a spreadsheet or a date, such as a
            # test row that appeared on the website in September 2026.
            if file_info is None or date is None:
                logging.warning(
                    f"Skipping the report '{report_name.group(1)}' on page "
                    f"{page_number}, without a spreadsheet or a date."
                )
                continue

            if date not in file_dates_not_available:
                available_requests.append(
                    (file_info.group(1), file_info.group(2), date)
                )

        if not page_has_reports:
            break

    # Return the requests in chronological order, as the other data
    # sources do: the website lists the reports from the newest.
    return sorted(available_requests, key=lambda request: request[2])


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
    file_number_extension_and_date: tuple[str, str, str], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the PGCB website for the given date range.

    Parameters
    ----------
    file_number_extension_and_date : tuple[str, str, str]
        The file number of the Excel file, its file extension (xls,
        xlsx, xlsm), and the date in the format YYYY-MM-DD.
    code : str
        The code of Bangladesh.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas ExcelFile.
    """
    file_number, extension, date = file_number_extension_and_date

    logging.info(
        f"Retrieving electricity demand data from file with date {date}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(file_number, extension)

    # Fetch the data from the URL.
    excel_file = utils.fetcher.fetch_data(url, "html", read_as="excel_file")

    # Make sure the data is an Excel file.
    if not isinstance(excel_file, pd.ExcelFile):
        raise TypeError(
            f"The extracted data is a {type(excel_file)} object, "
            "expected a pandas ExcelFile."
        )

    # Read the sheet of the load curve.
    if "L-Curve" in excel_file.sheet_names:
        demand_sheet = "L-Curve"
    elif "L.curve" in excel_file.sheet_names:
        demand_sheet = "L.curve"
    else:
        logging.error("No valid sheet found. Skipping this file.")
        return pd.Series(dtype=float)
    dataset = pd.read_excel(excel_file, sheet_name=demand_sheet, header=None)

    # Find the row of the column names, with "TIME" and "TOTAL".
    header_row = None
    for row_index in range(len(dataset)):
        row = dataset.iloc[row_index].astype(str).str.strip().str.upper()
        if "TIME" in row.to_list() and "TOTAL" in row.to_list():
            header_row = row_index
            time_column = row.to_list().index("TIME")
            total_column = row.to_list().index("TOTAL")
            break
    if header_row is None:
        logging.error("No valid header/row found. Skipping this file.")
        return pd.Series(dtype=float)

    # Read the hours and minutes of the times, such as "00:30", "24:00"
    # or time objects. The summary rows below the times have none.
    table = dataset.iloc[header_row + 1 :, [time_column, total_column]]
    hours_and_minutes = (
        table.iloc[:, 0]
        .astype(str)
        .str.strip()
        .str[:5]
        .str.extract(r"^(\d{1,2}):(\d{2})$")
        .astype(float)
    )
    hours, minutes = hours_and_minutes[0], hours_and_minutes[1]

    # Keep the readings at the full hours, with midnight from "24:00"
    # when the report has it, and from "00:00" otherwise.
    is_reading = minutes.eq(0)
    if hours[is_reading].eq(24).any():
        is_reading &= hours.ne(0)

    # The report has the data of the day before its date.
    day = pd.Timestamp(date) - pd.Timedelta(days=1)
    electricity_demand_time_series = pd.Series(
        pd.to_numeric(table.iloc[:, 1][is_reading], errors="coerce").to_numpy(
            dtype="float64"
        ),
        index=pd.DatetimeIndex(
            day + pd.to_timedelta(hours[is_reading], unit="h")
        ),
    )

    # The readings are at their times in Bangladesh.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Asia/Dhaka")
    )

    return electricity_demand_time_series
