"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Enerji Piyasaları İşletme A.Ş. (EPIAS) in
    Turkey. The data is retrieved by registering on the website and
    downloading the data manually. The user needs to create an account
    on the EPIAS website, which is free of charge. After registration,
    the user can log in to the website and download the data.

    Source: https://seffaflik.epias.com.tr/
"""

import datetime

import pandas as pd
import utils.fetcher


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is read at once from the files downloaded manually, so
    there is a single request, without parameters.

    Parameters
    ----------
    code : str
        The code of Turkey.
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
    Get the URL of the electricity demand data from the EPIAS website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://seffaflik.epias.com.tr/"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the EPIAS
    website. This function assumes that the data has been downloaded and
    is available in the specified folder.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Turkey.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Read the downloaded files.
    dataset = utils.fetcher.read_manual_files(
        data_source_name="EPIAS",
        url=get_url(),
        prefix="EPI",
        read_file=pd.read_excel,
        access=" after registering on the website",
    )

    # Extract the electricity demand data from the dataset.
    electricity_demand_time_series = pd.Series(
        dataset["Tüketim Miktarı(MWh)"].values,
        index=pd.to_datetime(dataset["Tarih"], format="%d/%m/%Y %H:%M:%S"),
    )

    # Add one hour to the index because the electricity demand seems to
    # be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pd.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize(
            "Europe/Istanbul", ambiguous="NaT", nonexistent="NaT"
        )
    )

    return electricity_demand_time_series
