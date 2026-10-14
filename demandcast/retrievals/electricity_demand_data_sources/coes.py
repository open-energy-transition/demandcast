"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Comité de Operación Económica (COES)
    of Peru. The data is retrieved from 1997 to current date. The data
    is retrieved in one-year intervals.

    Source: https://www.coes.org.pe/Portal/portalinformacion/demanda
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
    logging.debug(
        "Prohibited any use for commercial or distribution purposes."
    )
    logging.debug(
        "Source: "
        "https://www.coes.org.pe/Portal/Organizacion/TerminosyCondiciones"
    )
    return False


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

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
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
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.post",
        request_params=request_params,
        read_as="json",
        json_keys=["Chart", "Series"],
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
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
