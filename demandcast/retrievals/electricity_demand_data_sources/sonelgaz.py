"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from a publicly available repository with data provided by the
    Société Nationale de l'Electricité et du Gaz (Sonelgaz) in Algeria.
    The data is retrieved all at once.

    Source: https://data.mendeley.com/datasets/z5x2d3mhw7/1
    Source: https://doi.org/10.1016/j.dib.2023.109854
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
        The code of Algeria.
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
    Get the URL of the electricity demand data from Sonelgaz.

    Returns
    -------
    str
        The URL of the electricity demand data
    """
    # Return the URL of the electricity demand data.
    return (
        "https://"
        "prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/"
        "028bbb1d-0e1a-4318-ba22-f4bf1ff5fec5"
    )


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from Sonelgaz.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Algeria.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(url, "excel")

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
            dataset.iloc[:, 1].astype(str).str.replace("h", "").astype(int) - 1
        ).astype(str),
        format="%Y-%m-%d %H",
    )

    # Define the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Value"].values,
        index=index,
    )

    # Sort the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.sort_index()
    )

    # Move the times to the ends of the hours, in local time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Africa/Algiers",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
