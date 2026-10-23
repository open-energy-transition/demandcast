"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Panama from a publicly available repository containing
    data from the Centro Nacional de Despacho (CND). The data is
    retrieved all at once, from the file of the daily post-dispatch
    reports.

    The file gives the hourly load ("Carga Real"), generation, imports
    and exports in MW, at the start of each hour in the time of Panama,
    which has no daylight saving time: the hours of each week are
    numbered from 1, at 00:00.

    Source: https://data.mendeley.com/datasets/tcmmj4t6f4/1
"""

import datetime

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is retrieved all at once, so there is a single request,
    without parameters.

    Parameters
    ----------
    code : str
        The code of Panama.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[None]
        The single request.
    """
    return [None]


def get_url() -> str:
    """
    Get the URL of the electricity demand data from CND.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://data.mendeley.com/public-files/datasets/tcmmj4t6f4/files/1b23f797-b28e-445b-85ef-e8c773922a23/file_downloaded"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from CND.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Panama.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(url, "html", read_as="excel_table")

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Carga Real"].values,
        index=pd.to_datetime(dataset["Fecha Hora"]),
    )

    # The times are the starts of the hours, the first of each week
    # numbered 1. Move them to the ends of the hours.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "America/Panama",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
