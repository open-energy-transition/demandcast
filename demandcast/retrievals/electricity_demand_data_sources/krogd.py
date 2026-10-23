"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Korean Open Government Data (KROGD) portal
    in South Korea. The data is retrieved from the versions of the file
    data of the hourly national demand of the Korea Power Exchange
    (KPX), which the portal keeps and gives without login.

    The portal publishes a new version every year, and keeps the
    earlier ones in its history: the version that ends on 2020-12-31
    covers 2013 to 2020, and each later one its year. The module reads
    the versions from the dataset page, its history and their details,
    and downloads the latest version of each year.

    The files give the demand in MWh of each hour, at the generation
    side and provisional, by date and hour ending from 1시 to 24시 in
    the time of Korea, which has no daylight saving time.

    Source: https://www.data.go.kr/data/15065266/fileData.do
"""

import datetime
import logging
import re

import pandas as pd
import utils.fetcher
import utils.time_series

# The identifier of the dataset on the portal.
DATASET_ID = "15065266"

# The URL of the portal.
PORTAL_URL = "https://www.data.go.kr"


def _read_text(url: str, data: dict[str, str] | None = None) -> str:
    """
    Read a page of the portal, with a POST request if there is data.

    Parameters
    ----------
    url : str
        The URL of the page.
    data : dict[str, str] | None, optional
        The data of the POST request.

    Returns
    -------
    str
        The text of the page.
    """
    page = utils.fetcher.fetch_text(
        url,
        "POST" if data else "GET",
        post_data_params=data,
        header_params={"User-Agent": "Mozilla/5.0"},
    )
    return page


def _read_versions() -> dict[str, str]:
    """
    Read the versions of the file data on the portal.

    Returns
    -------
    dict[str, str]
        The identifier of the file of each version, by the last date of
        its data in the format YYYYMMDD.

    Raises
    ------
    ValueError
        If the dataset page has no current version.
    """
    # The page of the dataset gives the current version and its file.
    page = _read_text(f"{PORTAL_URL}/data/{DATASET_ID}/fileData.do")
    current = re.search(r"전력수요량_(\d{8})", page)
    file_id = re.search(r"fileDownload\.do\?atchFileId=(FILE_\d+)", page)
    detail_id = re.search(
        rf"fn_fileDataDown\('{DATASET_ID}', '(uddi:[0-9a-f-]+)'", page
    )
    if current is None or file_id is None or detail_id is None:
        raise ValueError("The dataset page of KROGD has no current version.")
    versions = {current.group(1): file_id.group(1)}

    # The history gives the earlier versions, and their details give
    # their files.
    history = _read_text(
        f"{PORTAL_URL}/tcs/dss/selectHistAndCsvData.do",
        {"publicDataPk": DATASET_ID, "publicDataDetailPk": detail_id.group(1)},
    )
    for version_id, version_number, date in re.findall(
        r'data-public-pk="(uddi:[0-9a-f-]+)"\s+'
        r'data-public-detail-sn="(\d+)">\s*[^<]*?_(\d{8})',
        history,
    ):
        details = _read_text(
            f"{PORTAL_URL}/tcs/dss/selectDpkDetailInfo.do",
            {
                "publicDataDetailPk": version_id,
                "publicDataHistSn": version_number,
            },
        )
        version_file_id = re.search(r"'(FILE_\d+)', '\d+', 'csv'", details)
        if version_file_id is not None:
            versions[date] = version_file_id.group(1)

    return versions


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """
    Get the available requests.

    This function reads the versions of the file data on the portal and
    keeps the latest version of each year between the dates.

    Parameters
    ----------
    code : str
        The code of South Korea.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp, str]]
        The first and last day of the data of each version, and the
        identifier of its file, in chronological order. Each version
        starts the day after the previous one ends, and the first one
        at the start date.
    """
    latest_by_year: dict[str, tuple[str, str]] = {}
    for date, file_id in sorted(_read_versions().items()):
        if start_date.year <= int(date[:4]) <= end_date.year:
            latest_by_year[date[:4]] = (date, file_id)

    requests = []
    first_day = pd.Timestamp(start_date)
    for year in sorted(latest_by_year):
        date, file_id = latest_by_year[year]
        last_day = pd.Timestamp(date)
        requests.append((first_day, last_day, file_id))
        first_day = last_day + pd.Timedelta(days=1)
    return requests


def get_url(file_id: str) -> str:
    """
    Get the URL of a file of the electricity demand data on the portal.

    Parameters
    ----------
    file_id : str
        The identifier of the file.

    Returns
    -------
    str
        The URL of the file.
    """
    return (
        f"{PORTAL_URL}/cmm/cmm/fileDownload.do?atchFileId={file_id}"
        "&fileDetailSn=1&insertDataPrcus=N"
    )


def download_and_extract_data_for_request(
    version: tuple[pd.Timestamp, pd.Timestamp, str], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the KROGD portal.

    Parameters
    ----------
    version : tuple[pandas.Timestamp, pandas.Timestamp, str]
        The first and last day of the data of the version, and the
        identifier of its file.
    code : str
        The code of South Korea.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    first_day, last_day, file_id = version
    logging.info(
        "Retrieving electricity demand data from "
        f"{first_day.date()} to {last_day.date()}."
    )

    # Fetch the file, with Korean characters, without its empty rows.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(file_id), "csv", csv_kwargs={"encoding": "cp949"}
    )
    dataset = dataset.dropna(subset=[dataset.columns[0]])

    # The column names have the time information. Rearrange the
    # columns to have the time information on another column.
    dataset = dataset.melt(
        id_vars=dataset.columns[0], var_name="Hour", value_name="Value"
    )

    # Define the new index, at the starts of the hours.
    index = pd.to_datetime(
        dataset.iloc[:, 0].astype(str)
        + " "
        + (
            dataset.iloc[:, 1].astype(str).str.replace("시", "").astype(int)
            - 1
        ).astype(str),
        format="%Y-%m-%d %H",
    )

    # Define the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Value"].values,
        index=index,
    )

    # Move the times to the ends of the hours, in local time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series, "Asia/Seoul", pd.Timedelta(hours=1)
        )
    )

    return electricity_demand_time_series
