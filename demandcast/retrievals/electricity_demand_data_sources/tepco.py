"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Tokyo Electric Power Company (TEPCO) in
    Japan. The data is retrieved for the years from 2016 to the current
    year: until 2024 from one CSV file per year, and from 2025 from one
    ZIP file per month, with one CSV file per day, since the yearly file
    of 2025 stops in July.

    Source: https://www.tepco.co.jp/en/forecast/html/download-e.html
"""

import datetime
import io
import logging
import zipfile

import pandas as pd
import requests
import utils.fetcher

# The last year with a yearly file.
LAST_YEARLY_FILE = 2024

# The header of the hourly values in the daily files, which also have
# the values every five minutes under another header.
HOURLY_HEADER = "DATE,TIME,当日実績(万kW)"


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Personal use only. Redistribution is not allowed.")
    logging.debug("Source: https://www4.tepco.co.jp/en/pg/legal/index-e.html")
    return False


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[int, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the TEPCO website: the years with a yearly file,
    and then the months.

    Parameters
    ----------
    code : str
        The code of the Kantō region.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[int, int | None]]
        The list of available requests.
    """
    # Requests of the yearly files.
    requests_of_years: list[tuple[int, int | None]] = [
        (year, None)
        for year in range(
            start_date.year, min(end_date.year, LAST_YEARLY_FILE) + 1
        )
    ]

    # Requests of the monthly files.
    requests_of_months: list[tuple[int, int | None]] = [
        (date.year, date.month)
        for date in pd.date_range(
            start=pd.Timestamp(LAST_YEARLY_FILE + 1, 1, 1),
            end=pd.Timestamp(end_date),
            freq="MS",
        )
    ]

    return requests_of_years + requests_of_months


def get_url(year: int, month: int | None) -> str:
    """
    Get the URL of the electricity demand data on the TEPCO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    month : int | None
        The month of the electricity demand data, or None for a whole
        year.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    if month is None:
        return f"https://www4.tepco.co.jp/forecast/html/images/juyo-{year}.csv"

    return (
        "https://www.tepco.co.jp/forecast/html/images/"
        f"{year}{month:02d}_power_usage.zip"
    )


def _read_yearly_file(content: bytes) -> pd.Series:
    """
    Read the hourly values of a yearly file.

    Parameters
    ----------
    content : bytes
        The content of the CSV file, in Shift JIS.

    Returns
    -------
    pandas.Series
        The values in 10 MW, at the start of each hour.
    """
    # Skip the time of the last update and an empty line.
    dataset = pd.read_csv(io.StringIO(content.decode("cp932")), skiprows=2)

    return pd.Series(
        dataset["実績(万kW)"].to_numpy(),
        index=pd.to_datetime(
            dataset["DATE"] + " " + dataset["TIME"], format="%Y/%m/%d %H:%M"
        ),
    )


def _read_monthly_file(content: bytes) -> pd.Series:
    """
    Read the hourly values of the daily files of a monthly file.

    Parameters
    ----------
    content : bytes
        The content of the ZIP file, with one CSV file per day, in
        Shift JIS.

    Returns
    -------
    pandas.Series
        The values in 10 MW, at the start of each hour.

    Raises
    ------
    ValueError
        If a daily file has no hourly values.
    """
    daily_values = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for file_name in sorted(archive.namelist()):
            lines = archive.read(file_name).decode("cp932").splitlines()

            # Read the 24 lines after the header of the hourly values.
            header_line = next(
                (
                    number
                    for number, line in enumerate(lines)
                    if line.startswith(HOURLY_HEADER)
                ),
                None,
            )
            if header_line is None:
                raise ValueError(f"No hourly values in {file_name}.")
            dataset = pd.read_csv(
                io.StringIO("\n".join(lines[header_line : header_line + 25]))
            )

            daily_values.append(
                pd.Series(
                    dataset["当日実績(万kW)"].to_numpy(),
                    index=pd.to_datetime(
                        dataset["DATE"] + " " + dataset["TIME"],
                        format="%Y/%m/%d %H:%M",
                    ),
                )
            )

    return pd.concat(daily_values)


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int | None], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the TEPCO website.

    Parameters
    ----------
    year_and_month : tuple[int, int | None]
        The year and month of the electricity demand data, with None
        as the month for a whole year.
    code : str
        The code of the Kantō region.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a requests.Response object.
    """
    year, month = year_and_month

    logging.info(
        f"Retrieving electricity demand data for {year}"
        + (f"-{month:02d}." if month is not None else ".")
    )

    # Fetch the file. The website rejects the user agent of requests.
    response = utils.fetcher.fetch_data(
        get_url(year, month),
        "html",
        read_as="plain",
        header_params={"User-Agent": "Mozilla/5.0"},
    )

    # Make sure the response is a requests.Response object.
    if not isinstance(response, requests.Response):
        raise TypeError(
            f"The extracted data is a {type(response)} object, "
            "expected a requests.Response object."
        )

    if month is None:
        values = _read_yearly_file(response.content)
    else:
        values = _read_monthly_file(response.content)

    # Convert from 10 MW to MW, and mark the end of each hour.
    electricity_demand_time_series = values * 10
    electricity_demand_time_series.index += pd.Timedelta(hours=1)

    return electricity_demand_time_series.tz_localize("Asia/Tokyo")
