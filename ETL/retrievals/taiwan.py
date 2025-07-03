# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Taiwan from a publicly available repository developed for
    research purposes. The data is downloaded from Jan 1, 2017 to
    July 1, 2022. The data is retrieved all at once.

    Source: https://zenodo.org/records/7537890
"""

import logging

import pandas
import utils.fetcher


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for Taiwan.
    """
    logging.debug("The data is retrieved all at once.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data for Taiwan.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://zenodo.org/records/7537890/files/loadarea_10min_2017Jan_2022Jun.csv?download=1"


def download_and_extract_data() -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    for Taiwan.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "csv",
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Sum the regional demand columns to get total national demand
        dataset["National Demand"] = (
            dataset["south"]
            + dataset["north"]
            + dataset["east"]
            + dataset["central"]
        )

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["National Demand"].values,
            index=pandas.to_datetime(dataset["datetime"]),
        )

        # Add 10 minutes to the index because the electricity demand
        # seems to be provided at the beginning of the time-interval
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index + pandas.Timedelta(minutes=10)
        )

        # Add the timezone information to the index.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Asia/Taipei")
        )

        return electricity_demand_time_series
