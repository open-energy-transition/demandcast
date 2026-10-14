"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for China from a publicly available repository developed for
    research purposes. The data is available from Jan 1, 2018 to
    Dec 31, 2018. The data is retrieved all at once.

    Source: https://zenodo.org/records/8322210
"""

import datetime

import pandas as pd
import utils.fetcher


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
        The code of China.
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
    Get the URL of the electricity demand data for China.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://zenodo.org/records/8322210/files/Appendix%201_Hourly%20electric%20power%20load%20final.csv?download=1"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data for China.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of China.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    url = get_url()

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "csv",
    )

    # Split semicolon-delimited columns (original CSV is single-column).
    dataset = dataset.iloc[:, 0].str.split(";", expand=True)

    # Convert all columns except the first one to numeric.
    for i in range(1, dataset.shape[1]):
        dataset[dataset.columns[i]] = pd.to_numeric(dataset.iloc[:, i])

    # Sum the regional demand columns to get total national demand.
    dataset["National Demand"] = dataset.iloc[:, 1:].sum(axis=1)

    # Construct the index of the electricity demand time series.
    timestamps = pd.date_range(
        start="2018-01-01 01:00:00",
        periods=8760,
        freq="h",
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["National Demand"].values, index=timestamps
    )

    # Add the timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Asia/Shanghai")
    )

    return electricity_demand_time_series
