"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data from the website
    of the Power Grid Company of Bangladesh (PGCB), now Power Grid
    Bangladesh PLC. The data is obtained from the daily reports on the
    website, one Excel file a day from 2014, which the website lists on
    about 150 pages. Retrieving all the data takes a few hours.

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

    The server of the website sends its certificate without the
    intermediate certificate that links it to a root of the default
    certificates, which the browsers fetch and Python does not. The
    module verifies the website with the default certificates and that
    intermediate one, pgcb_intermediate_certificate.pem next to it,
    from the address that the certificate of the website gives.

    Source: https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09IiwibWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4NzRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/show_report
"""

import atexit
import datetime as dt
import functools
import logging
import os
import re
import shutil
import tempfile

import pandas as pd
import requests.utils

import utils.fetcher

# The intermediate certificate of the website, which its server does not
# send.
INTERMEDIATE_CERTIFICATE = os.path.join(
    os.path.dirname(__file__), "pgcb_intermediate_certificate.pem"
)


@functools.cache
def _get_certificates() -> str:
    """
    Write the certificates that verify the website.

    Returns
    -------
    str
        The path of a file with the default certificates and the
        intermediate certificate of the website, which is deleted when
        Python exits.
    """
    folder = tempfile.mkdtemp(prefix="demandcast_pgcb_")
    atexit.register(shutil.rmtree, folder, ignore_errors=True)
    file_path = os.path.join(folder, "certificates.pem")
    with (
        open(
            requests.utils.DEFAULT_CA_BUNDLE_PATH, encoding="ascii"
        ) as default,
        open(INTERMEDIATE_CERTIFICATE, encoding="ascii") as intermediate,
        open(file_path, "w", encoding="ascii") as certificates,
    ):
        certificates.write(default.read())
        certificates.write("\n")
        certificates.write(intermediate.read())
    return file_path


def _clean_and_format(date: str) -> str:
    """
    Convert the date of a report name to the format YYYY-MM-DD.

    Parameters
    ----------
    date : str
        The date of the report name, day first.

    Returns
    -------
    str
        The date string in the format YYYY-MM-DD.

    Raises
    ------
    ValueError
        If the date string cannot be inferred.

    Notes
    -----
    Some report names have typos in their dates, which are fixed by
    their known corrections. The name of the report of 2022-04-25 has no
    date, so the regular expression captures only "t" from it. The
    dates use dots, slashes or hyphens as separators, and some have
    trailing dots, months of one digit or years of two digits.
    """
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
    if date in fix_typo:
        date = fix_typo[date]

    date = date.strip().strip(".").replace(".", "-").replace("/", "-")

    date_components = date.split("-")
    if len(date_components) != 3:
        raise ValueError(f"Cannot infer the date from the string: {date}.")
    day, month, year = date_components

    if len(month) == 1:
        month = f"0{month}"

    if len(year) == 2:
        year = f"20{year}"

    date = f"{year}-{month}-{day}"

    try:
        pd.to_datetime(date, format="%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Cannot infer the date from the string: {date}."
        ) from e

    return date


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[str, str, str]]:
    """
    Get the available requests.

    The requests are the Excel files of the reports listed on the pages
    of the PGCB website, except those known to be unavailable.

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
    list[tuple[str, str, str]]
        The number and extension of the file of each report, and the
        date of the report in the format YYYY-MM-DD, in chronological
        order.

    Notes
    -----
    The pages are read until the first one without reports: the website
    has about 150 pages, and adds one every month. The rows without a
    spreadsheet or a date, such as a test row that appeared on the
    website in September 2026, are skipped. The website lists the
    reports from the newest, so the requests are sorted by date.

    The files of the reports known to be unavailable are missing,
    except that of 2014-04-12, which lacks some data, and that of
    2016-01-07, which is corrupted.
    """
    logging.info("Retrieving the available requests from the PGCB website.")

    file_dates_not_available = [
        "2014-04-12",
        "2016-01-07",
        "2016-01-23",
        "2016-01-24",
        "2016-01-25",
        "2016-01-26",
        "2016-01-27",
        "2016-01-28",
        "2016-01-29",
        "2016-01-30",
        "2016-01-31",
        "2016-02-01",
        "2016-02-02",
        "2017-02-13",
        "2017-02-14",
        "2017-02-15",
        "2017-02-16",
        "2018-02-26",
        "2018-11-10",
        "2022-06-14",
    ]

    available_requests = []

    for page_number in range(1, 1000):
        page_url = (
            "https://erp.powergrid.gov.bd/w/report/eyJpdiI6IldsU2ZQTGkvbkRnQU9"
            "FMjZ5UHhmeGc9PSIsInZhbHVlIjoiQzhONVl5ZGxRY3E3T3ZVNCtLZGt1Zz09Iiwi"
            "bWFjIjoiN2JiNTI5MzNhOWIxZDVjY2NkMmFlZWU4ZDU1N2I4OWZlYjNlZWM1ZGU4N"
            "zRiNWU4ZjQ3ZDc1ODRlMTk3MDc0YyIsInRhZyI6IiJ9/"
            f"show_report?page={page_number}"
        )

        html_content = utils.fetcher.fetch_response(
            page_url, verify_ssl=_get_certificates()
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
        The URL of the electricity demand data.
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
    """
    file_number, extension, date = file_number_extension_and_date

    logging.info(
        f"Retrieving electricity demand data from file with date {date}."
    )

    url = get_url(file_number, extension)

    excel_file = utils.fetcher.fetch_excel_file(
        url, verify_ssl=_get_certificates()
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
    # or time objects. The summary rows below the times have none. A
    # "24:00" that Excel stores as a whole day reads as 1900-01-01.
    table = dataset.iloc[header_row + 1 :, [time_column, total_column]]
    hours_and_minutes = (
        table.iloc[:, 0]
        .map(
            lambda time: (
                f"{24 + time.hour}:{time.minute:02d}"
                if isinstance(time, dt.datetime)
                and time.date() == dt.date(1900, 1, 1)
                else time
            )
        )
        .astype(str)
        .str.strip()
        .str[:5]
        .str.extract(r"^(\d{1,2}):(\d{2})$")
        .astype(float)
    )
    hours, minutes = hours_and_minutes[0], hours_and_minutes[1]

    # Keep the readings at the full hours, with midnight from "24:00"
    # when the report has it.
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
