"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data of XM, the operator of the electricity system and market of
    Colombia. The data is retrieved in one-month intervals, through the
    proxy of the API of XM that the website of Energía de Colombia uses:
    the API of XM itself (servapibi.xm.com.co) does not answer from
    outside Colombia.

    The data is the real demand of the system (DemaReal) in kWh of each
    hour, which the module converts to MW, from 2000, by date and hour
    from "Hour01" to "Hour24", the hours that end at 01:00 to 24:00 in
    the time of Colombia, which has no daylight saving time.

    The proxy takes 22 to 26 seconds to answer the request of a month,
    longer than the usual time limit of the requests (10 seconds), so
    the requests wait for up to 120 seconds.

    Source: https://xm.com.co
    Source: https://www.energiadecolombia.com/consulta
"""

import datetime
import logging

import pandas as pd
import utils.fetcher
import utils.time_series

# The seconds that a request waits for the answer of the proxy.
TIMEOUT = 120


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the XM website.

    Parameters
    ----------
    code : str
        The code of Colombia.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Split the period of the data into one-month periods.
    return utils.time_series.split_period(start_date, end_date, "MS")


def get_url(start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    """
    Get the URL of the electricity demand data on the XM website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the retrieval period is longer than 1 month.
    """
    # Check that the retrieval period is less than one month.
    if end_date - start_date > pd.Timedelta("31days"):
        raise ValueError(
            "The retrieval period is greater than 1 month. Please reduce the "
            "period to 1 month."
        )

    # Return the URL of the electricity demand data.
    return (
        "https://50uclmn31c.execute-api.us-east-1.amazonaws.com/prod/xmproxy?"
        f"metricId=DemaReal&entity=Sistema&start={start_date:%Y-%m-%d}"
        f"&end={end_date:%Y-%m-%d}"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the XM website.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The start and end date and time of the data retrieval.
    code : str
        The code of Colombia.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    start_date, end_date = period

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(start_date, end_date)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        timeout=TIMEOUT,
        read_with="requests.post",
        read_as="json",
    )

    # Initialize the list to store the daily values.
    daily_values_list = []

    # Iterate over the dates in the dataset.
    for date in dataset["Date"]:
        # Extract the row corresponding to the date.
        values_dict = dataset[dataset["Date"] == date]

        # Extract the values for each hour of the day.
        hourly_values = [
            (values_dict["Values"].to_numpy()[0])[f"Hour{hour:02d}"]
            for hour in range(1, 25)
        ]

        # Define the date and time for each hour of the day.
        date_and_time = [date + f" {hour:02d}:00" for hour in range(24)]

        # Create and append a pandas Series for the day.
        daily_values_list.append(
            pd.Series(
                hourly_values,
                index=pd.to_datetime(date_and_time),
            )
        )

    # Concatenate the daily values into a single pandas Series.
    electricity_demand_time_series = pd.concat(daily_values_list)

    # Convert the electricity demand values to float type.
    electricity_demand_time_series = electricity_demand_time_series.astype(
        float
    )

    # Values are in kWh with a frequency of 1 hour. Convert to MW.
    electricity_demand_time_series = electricity_demand_time_series / 1000

    # The times above are the starts of the hours, from 00:00 for
    # "Hour01", which ends at 01:00: move them to the ends of the hours.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "America/Bogota",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series
