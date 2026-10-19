"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from a publicly available repository with data provided by the
    Société Nationale de l'Electricité et du Gaz (Sonelgaz) in Algeria,
    on Mendeley Data under the CC BY 4.0 license. The data is retrieved
    all at once, from a single Excel file.

    The file gives the hourly demand from 2008-01-01 to 2020-02-01, one
    row a day, with the hours ending from "1h" to "24h" in the time of
    Algeria, which has no daylight saving time. Its values are the
    demand in MW multiplied by 125/148: all of them are whole numbers of
    MW times 125/148, and divided by it they give the peak demand of
    Sonelgaz, such as 10,464 MW on 2013-08-07 at 21:00 and 7% above the
    peak of 2012. The module divides them by 125/148. In 2019, the rows
    from 2019-02-10 come three times, with the same values, and the
    cleaning keeps one of each.

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
    # Return the URL of the file of the dataset.
    return (
        "https://data.mendeley.com/public-files/datasets/z5x2d3mhw7/files/"
        "049d33a5-6d4f-465a-8a65-b613487eb1c9/file_downloaded"
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

    # Fetch the data from the URL, with requests: Mendeley Data refuses
    # the downloads of pandas.
    dataset = utils.fetcher.fetch_dataframe(url, "html", read_as="excel_table")

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

    # Define the electricity demand time series, in MW: the values are
    # the demand multiplied by 125/148.
    electricity_demand_time_series = pd.Series(
        dataset["Value"].to_numpy(dtype="float64") * 148 / 125,
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
