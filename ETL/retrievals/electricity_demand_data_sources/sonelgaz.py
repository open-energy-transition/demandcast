# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from a publicly available repository with data provided by the
    Société Nationale de l'Electricité et du Gaz (Sonelgaz) in Algeria.
    The data is retrieved for the years from 2008-01-01 to 2020-02-01.
    The data is retrieved all at once.

    Source: https://data.mendeley.com/datasets/z5x2d3mhw7/1
    Source: https://doi.org/10.1016/j.dib.2023.109854
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
    logging.debug("Source: https://data.mendeley.com/datasets/z5x2d3mhw7/1")
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from Sonelgaz.
    """
    logging.debug("The data is retrieved all at once.")


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


def download_and_extract_data() -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from Sonelgaz.

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
    dataset = utils.fetcher.fetch_data(url, "excel")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # The column names have the time information. Rearrange the
        # columns to have the time information on another column.
        dataset = dataset.melt(
            id_vars=dataset.columns[0], var_name="Hour", value_name="Value"
        )

        # Define the new index.
        index = pandas.to_datetime(
            dataset.iloc[:, 0].astype(str)
            + " "
            + (
                dataset.iloc[:, 1].astype(str).str.replace("h", "").astype(int)
                - 1
            ).astype(str),
            format="%Y-%m-%d %H",
        ) + pandas.Timedelta(hours=1)

        # Define the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["Value"].values,
            index=index,
        )

        # Sort the index.
        electricity_demand_time_series = (
            electricity_demand_time_series.sort_index()
        )

        # Add the timezone information.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("Africa/Algiers")
        )

        return electricity_demand_time_series
