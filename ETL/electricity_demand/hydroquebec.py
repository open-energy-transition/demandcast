# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Hydro-Québec in Canada. The data is
    retrieved for the years from 2019 to 2023. The data is retrieved all
    at once.

    Source: https://donnees.hydroquebec.com/explore/dataset/historique-demande-electricite-quebec/information/
"""  # noqa: W505

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
    logging.debug("Non-commercial use with attribution to Hydro-Québec.")
    logging.debug(
        "Source: https://donnees.hydroquebec.com/explore/dataset/historique-demande-electricite-quebec/information/"  # noqa: W505
    )
    return True


def get_available_requests() -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the Hydro-Québec website.
    """
    logging.debug("The data is retrieved all at once.")


def get_url() -> str:
    """
    Get the URL of the electricity demand on the Hydro-Québec website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return (
        "https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets/"
        "historique-demande-electricite-quebec/exports/csv?"
        "lang=en&timezone=America%2FToronto&use_labels=true&delimiter=%2C"
    )


def download_and_extract_data() -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the Hydro-Québec website.

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

    # Fetch the electricity demand data.
    electricity_demand_time_series = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(electricity_demand_time_series, pandas.DataFrame):
        raise ValueError(
            "The extracted data is a "
            f"{type(electricity_demand_time_series)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Set the date as the index.
        electricity_demand_time_series = (
            electricity_demand_time_series.set_index(
                "date", drop=True
            ).squeeze()
        )

        # Convert the index to a datetime object.
        electricity_demand_time_series.index = pandas.to_datetime(
            electricity_demand_time_series.index,
            format="%Y-%m-%dT%H:%M:%S%z",
            utc=True,
        )

        # Sort the index.
        electricity_demand_time_series = (
            electricity_demand_time_series.sort_index()
        )

        return electricity_demand_time_series
