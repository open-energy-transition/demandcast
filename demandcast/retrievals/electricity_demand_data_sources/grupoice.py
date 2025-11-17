# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Grupo ICE (GRUPOICE) in Costa Rica.
    The data is downloaded from Mar 01, 2012 up to the current date.
    The data is retrieved in one-year intervals.

    Source: https://apps.grupoice.com/CenceWeb
"""

import logging

import pandas
import utils.entities
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Open data.")
    logging.debug(
        "Source: https://www.grupoice.com/wps/wcm/connect/328d1cc7-6796-44cb-a981-8dca6043c983/Reglamento_funcionamiento_CENCE.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE-328d1cc7-6796-44cb-a981-8dca6043c983-nWcNMD."  # noqa: W505
    )
    return True


def _check_input_parameters(year: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    """
    # Check if the year is supported.
    assert year in get_available_requests(), (
        f"The year {year} is not in the supported range."
    )


def get_available_requests() -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the GRUPOICE website.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            data_source="grupoice"
        )["CRI"]
    )

    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if input parameters are valid.
    _check_input_parameters(year)

    # Construct the URL for the request.
    return (
        "https://apps.grupoice.com/CenceWeb/data/sen/csv/DemandaMW?intervalo=15&"
        f"inicio={year}0101&fin={year}1231"
    )


def download_and_extract_data_for_request(year: int) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if input parameters are valid.
    _check_input_parameters(year)

    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_as="csv_table",
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["MW"].values,
        index=pandas.to_datetime(dataset["fechaHora"]),
    )

    # Add 15 minutes to each timestamp to represent the end of the time
    # period.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pandas.Timedelta(minutes=15)
    )

    # Add the timezone information.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("America/Costa_Rica")
    )

    return electricity_demand_time_series
