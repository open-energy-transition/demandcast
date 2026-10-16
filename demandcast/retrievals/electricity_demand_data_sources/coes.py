"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Comité de Operación Económica (COES)
    of Peru. The data is retrieved in one-year intervals.

    The portal gives the executed demand of the national system in MW
    every 30 minutes, at the end of each interval in the time of Peru,
    which has no daylight saving time: a year runs from 00:30 of its
    first day to 00:00 of the next year. Until 1999 the values are
    hourly, each given for both half hours, and about 20% lower, as the
    demand jumps from 1,651 MW to 1,929 MW at 00:30 of 1 January 2000,
    so the data starts in 2000.

    Source: https://www.coes.org.pe/Portal/portalinformacion/demanda
"""

import datetime
import logging

import pandas as pd
import utils.fetcher


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the COES website.

    Parameters
    ----------
    code : str
        The code of Peru.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the COES website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.coes.org.pe/Portal/portalinformacion/demanda"


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the COES website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Peru.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url()

    # Define the request parameters.
    request_params = {
        "fechaInicial": f"01/01/{year}",
        "fechaFinal": f"31/12/{year}",
    }

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_with="requests.post",
        request_params=request_params,
        read_as="json",
        json_keys=["Chart", "Series"],
    )

    # Extract the electricity demand data from the dataset.
    dataset = pd.DataFrame(dataset[dataset["Name"] == "Ejecutado"]["Data"][0])

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Valor"].values,
        index=pd.to_datetime(dataset["Nombre"]),
    )

    # Add timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("America/Lima")
    )

    return electricity_demand_time_series
