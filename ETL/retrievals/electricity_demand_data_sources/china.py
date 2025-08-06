# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for China from a publicly available repository developed for
    research purposes. The data is downloaded from Jan 1, 2018 to
    Dec 31, 2018. The data is retrieved all at once.

    Source: https://zenodo.org/records/8322210
"""

import logging

import pandas
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("CC-BY 4.0 license. Use for any purpose with attribution.")
    logging.debug("Source: https://zenodo.org/records/8322210")
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for China.
    """
    logging.debug("The data is retrieved all at once.")


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


def download_and_extract_data() -> pandas.Series:
    """
    Download and extract electricity demand data for China.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
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
        # Split semicolon-delimited columns
        # (original CSV is single-column)
        dataset = dataset.iloc[:, 0].str.split(";", expand=True)

        # Convert all columns except the first one to numeric
        for i in range(1, dataset.shape[1]):
            dataset.iloc[:, i] = pandas.to_numeric(dataset.iloc[:, i])

        # Sum the regional demand columns to get total national demand
        dataset["National Demand"] = dataset.iloc[:, 1:].sum(axis=1)

        # Construct the index of the electricity demand time series.
        timestamps = pandas.date_range(
            start="2018-01-01 01:00:00",
            periods=8760,
            freq="h",
        )

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["National Demand"].values, index=timestamps
        )

        # Add the timezone information to the index.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Asia/Shanghai")
        )

    return electricity_demand_time_series
