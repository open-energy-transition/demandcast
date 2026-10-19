"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Nigeria from a dataset on Mendeley Data, under the CC BY
    4.0 license, which has a single Excel file of 2016.

    The file gives the hourly national demand in MW of 2016,
    unsuppressed and suppressed. The module reads the unsuppressed
    demand, which the authors reconstruct from the data of five
    distribution companies as the demand that there would have been
    without load shedding: it is modelled, not measured, and more than
    twice the suppressed demand (5.5 GW against 2.3 GW on average). The
    times have the errors of their storage as fractions of a day, such
    as 22:59:59.998, so they are rounded to the second. Their hours run
    from 0 to 23, so they are taken as the starts of the hours, in the
    time of Nigeria, which has no daylight saving time.

    Source: https://data.mendeley.com/datasets/pxvdm26rn7/2
    Source: https://doi.org/10.1016/j.esd.2020.08.009 (not the model
            used to generate the data but a related one)
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
        The code of Nigeria.
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
    Get the URL of the electricity demand data for Nigeria.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the file of the dataset.
    return (
        "https://data.mendeley.com/public-files/datasets/pxvdm26rn7/files/"
        "140d6dcc-90fb-4fa6-8e98-a91379b1ad60/file_downloaded"
    )


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    for Nigeria.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Nigeria.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the data from the URL, with requests: Mendeley Data refuses
    # the downloads of pandas.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_as="excel_table",
        excel_kwargs={"sheet_name": "Demand Timeseries", "skiprows": 3},
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["National Unsuppressed Demand"].values,
        index=pd.to_datetime(dataset["date time"]),
    )

    # Round the index to the nearest second.
    electricity_demand_time_series.index = pd.DatetimeIndex(
        electricity_demand_time_series.index
    ).round("s")

    # Move the starts of the hours to their ends.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Africa/Lagos",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
