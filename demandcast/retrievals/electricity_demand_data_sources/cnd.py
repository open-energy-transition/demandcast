# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data for Panama from a publicly available repository containing
    data from the Centro Nacional de Despacho (CND). The data is
    available from Jan 2, 2016 to July 31, 2020. The data is retrieved
    all at once.

    Source: https://data.mendeley.com/datasets/tcmmj4t6f4/1
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
    demand data from CND.
    """
    logging.debug("The data is retrieved all at once.")


def get_url() -> str:
    """
    Get the URL of the electricity demand data from CND.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://data.mendeley.com/public-files/datasets/tcmmj4t6f4/files/1b23f797-b28e-445b-85ef-e8c773922a23/file_downloaded"


def download_and_extract_data() -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from CND.

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
    dataset = utils.fetcher.fetch_data(url, "html", read_as="excel_table")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["Carga Real"].values,
        index=pandas.to_datetime(dataset["Fecha Hora"]),
    )

    # Add one hour to the index because the electricity demand seems
    # to be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("America/Panama")
    )

    return electricity_demand_time_series
