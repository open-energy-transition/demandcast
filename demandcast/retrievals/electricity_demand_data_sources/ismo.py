"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Independent System and Market Operator
    (ISMO) of Pakistan, which took over the system and market operation
    of the National Transmission & Despatch Company (NTDC) in 2024. The
    data is retrieved from the Excel file of each fiscal year, from July
    to June, in the library of the website.

    The library lists its files only through an API that needs the
    authorization of the website, and their names end with random
    characters, so the module keeps the URL of each file. The library
    has only the file of the fiscal year 2025, from July 2024 to June
    2025.

    The file gives the actual metered demand of the system without
    K-Electric, which supplies Karachi, in MW, by date and hour from 0
    to 23 in the time of Pakistan, which has no daylight saving time.
    The hours are their starts: the solar generation of the hourly
    generation file of the same year is centered at 11:44 by these
    hours, about half an hour before solar noon. The demand is at the
    level of the data of NTDC in 2018 and 2019. Its lowest values, about
    5.8 GW, are around noon on 2025-03-31, the day of Eid al-Fitr.

    The demand leaves out K-Electric, so its data has same_area false
    in the yaml file: it does not cover the whole shape of Pakistan.

    Source: https://www.ismo.gov.pk/library/hourly-system-demand
"""

import datetime
import logging

import pandas as pd

import utils.fetcher
import utils.time_series

# The URLs of the files of the hourly demand, by the year in which the
# fiscal year ends.
FILE_URLS = {
    2025: (
        "https://cmsadmin.ismo.gov.pk/storage/uploads/documents/"
        "System%20Demand%20Profile_Hourly_ismo_iaqXjdgb8B.xlsx"
    ),
}


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the ISMO website.

    Parameters
    ----------
    code : str
        The code of Pakistan.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The years in which the fiscal years of the files with data
        between the dates end.
    """
    return [
        fiscal_year
        for fiscal_year in sorted(FILE_URLS)
        if datetime.date(fiscal_year - 1, 7, 1) <= end_date
        and start_date <= datetime.date(fiscal_year, 6, 30)
    ]


def get_url(fiscal_year: int) -> str:
    """
    Get the URL of the electricity demand data on the ISMO website.

    Parameters
    ----------
    fiscal_year : int
        The year in which the fiscal year ends.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return FILE_URLS[fiscal_year]


def download_and_extract_data_for_request(
    fiscal_year: int, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ISMO website.

    Parameters
    ----------
    fiscal_year : int
        The year in which the fiscal year ends.
    code : str
        The code of Pakistan.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(
        "Retrieving electricity demand data from "
        f"{fiscal_year - 1}-07-01 to {fiscal_year}-06-30."
    )

    # Fetch the date, the hour and the demand, whose column name is a
    # description on several lines.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(fiscal_year),
        "html",
        read_as="excel_table",
        excel_kwargs={"usecols": [0, 1, 2]},
    )

    # The hours are their starts. Move them to their ends.
    electricity_demand_time_series = pd.Series(
        dataset.iloc[:, 2].to_numpy(dtype="float64"),
        index=pd.to_datetime(dataset["Date"])
        + pd.to_timedelta(dataset["Hour"], unit="h"),
    )
    return utils.time_series.localize_interval_starts(
        electricity_demand_time_series, "Asia/Karachi", pd.Timedelta(hours=1)
    )
