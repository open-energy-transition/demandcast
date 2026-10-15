"""
License: AGPL-3.0.

Description:

    This script provides functions to retrieve the electricity demand
    data from the website of National Institution for Transforming India
    (NITI) Aayog in India. The data is retrieved by submitting a request
    to the NITI Aayog website. The user is then able to download the
    data.

    Source: https://iced.niti.gov.in
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
        The code of India.
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
    Get the URL of the electricity demand data from NITI Aayog website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://iced.niti.gov.in/energy/electricity/distribution/national-level-consumption/load-curve"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the
    NITI Aayog website. This function assumes that the data has
    been downloaded and is available in the specified folder.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of India.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Read the downloaded files.
    dataset = utils.fetcher.read_manual_files(
        data_source_name="NITI Aayog",
        url=get_url(),
        prefix="NIT",
        read_file=pd.read_excel,
        access=" after submitting a request via the form on the website",
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Hourly Demand Met (in MW)"].values,
        index=pd.to_datetime(
            dataset["Year"].astype(str) + " " + dataset["Date"],
            format="%Y %d-%b %I%p",
        ),
    )

    # Add one hour to the index because the electricity demand seems to
    # be provided at the beginning of the hour.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Asia/Kolkata",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
