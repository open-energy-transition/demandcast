"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Grupo ICE (GRUPOICE) in Costa Rica.
    The data is downloaded from Mar 01, 2012 up to the current date.
    The data is retrieved in one-year intervals.

    Source: https://apps.grupoice.com/CenceWeb
"""

import datetime
import logging

import pandas as pd
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
        "Source: https://www.grupoice.com/wps/wcm/connect/328d1cc7-6796-44cb-a981-8dca6043c983/Reglamento_funcionamiento_CENCE.pdf?MOD=AJPERES&CACHEID=ROOTWORKSPACE-328d1cc7-6796-44cb-a981-8dca6043c983-nWcNMD."
    )
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the GRUPOICE website.

    Parameters
    ----------
    code : str
        The code of Costa Rica.
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
    # Construct the URL for the request.
    return (
        "https://apps.grupoice.com/CenceWeb/data/sen/csv/DemandaMW?intervalo=15&"
        f"inicio={year}0101&fin={year}1231"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the GRUPOICE website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Costa Rica.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
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
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["MW"].values,
        index=pd.to_datetime(dataset["fechaHora"]),
    )

    # Add 15 minutes to each timestamp to represent the end of the time
    # period.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pd.Timedelta(minutes=15)
    )

    # Add the timezone information.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("America/Costa_Rica")
    )

    return electricity_demand_time_series
