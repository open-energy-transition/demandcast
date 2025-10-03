# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for the Johor region in Malaysia from a publicly available
    repository developed for research purposes only. The data is
    retrieved for the years 2009 and 2010. The data is retrieved
    all at once.

    Source: https://data.mendeley.com/datasets/f4fcrh4tn9/1
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
    logging.debug("Source: https://creativecommons.org/licenses/by/4.0/")
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data for the Johor region in Malaysia.
    """
    logging.debug("The data is retrieved all at once.")


def get_url() -> str:
    """
    Get the URL of electricity demand data for Johor region in Malaysia.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return (
        "https://"
        "data.mendeley.com/public-files/datasets/f4fcrh4tn9/files/"
        "b2cae16c-bd04-4bbd-a444-a506013d5abd/file_downloaded"
    )


def download_and_extract_data() -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    for the Johor region in Malaysia.

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
        "html",
        read_as="csv_table",
        header_params={"User-Agent": "Mozilla/5.0"},
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

        # Assign proper column names
        dataset.columns = ["time", "temperature", "load"]

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["load"].values,
            index=pandas.to_datetime(
                dataset["time"], format="%m/%d/%y %I:%M %p"
            ),
        )

        # Add the timezone information to the index.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize(
                "Asia/Kuala_Lumpur"
            )
        )

        return electricity_demand_time_series
