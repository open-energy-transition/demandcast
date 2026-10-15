"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from a publicly available repository with data provided by the
    National Transmission & Despatch Company (NTDC) in Pakistan. The
    data is retrieved by registering on the website and downloading
    the data manually. The user needs to create an account on the
    Kaggle website, which is free of charge. After registration,
    the user can log in to the website and download the data.

    Source: https://www.kaggle.com/datasets/tentative/ntdc-dataset
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

    The data is read at once from the files downloaded manually, so
    there is a single request, without parameters.

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
    list[None]
        The single request.
    """
    return [None]


def get_url() -> str:
    """
    Get the URL of the electricity demand data for Pakistan.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.kaggle.com/datasets/tentative/ntdc-dataset"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data for
    Pakistan. This function assumes that the data has
    been downloaded and is available in the specified folder.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Pakistan.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Read the downloaded files.
    dataset = utils.fetcher.read_manual_files(
        data_source_name="NTDC",
        url=get_url(),
        prefix="NTD",
        read_file=pd.read_csv,
        access=" after registering on the website",
    )

    # Define the new index, at the starts of the hours.
    index = pd.to_datetime(
        dataset.iloc[:, 0].astype(str)
        + " "
        + (dataset.iloc[:, 1].astype(str).astype(int) - 1).astype(str),
        format="%d/%m/%Y %H",
    )

    # Remove commas and convert SYSLOAD to numeric.
    dataset["SYSLOAD"] = pd.to_numeric(
        dataset["SYSLOAD"].astype(str).str.replace(",", ""),
        errors="coerce",
    )

    # Define the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["SYSLOAD"].values,
        index=index,
    )

    # Move the times to the ends of the hours, in local time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Asia/Karachi",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
