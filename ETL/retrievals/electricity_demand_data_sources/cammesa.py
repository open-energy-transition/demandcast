# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Compañía Administradora del Mercado
    Mayorista Eléctrico S.A. (CAMMESA) in Argentina. The data is
    retrieved from 2024-08-01 to current date. The data is retrieved in
    one-day intervals.

    Source: https://api.cammesa.com/demanda-svc/swagger-ui.html#/demanda-ws
    Source: https://api.cammesa.com/demanda-svc/demanda/RegionesDemanda
    Source: https://microfe.cammesa.com/demandaregionchart/assets/data/regionesCammesa.geojson.json
"""  # noqa: W505

import logging

import pandas
import utils.entities
import utils.fetcher

province_id = {
    "AR": 1002,  # Argentina
    "BAS": [425, 426],  # Provincia de Buenos Aires
    "CEN": 422,  # Centro
    "COM": 420,  # Comahue
    "CUY": 429,  # Cuyo
    "LIT": 417,  # Litoral
    "NEA": 418,  # Nordeste Argentino
    "NOA": 419,  # Noroeste Argentino
    "PAT": 111,  # Patagonia
}


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug(
        "Reproduction, modification, distribution and / or "
        "transmission of the information is strictly prohibited."
    )
    logging.debug("https://cammesaweb.cammesa.com/politicas-de-acceso/")
    return False


def _check_input_parameters(date: str) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.
    """
    # Check if the date is supported.
    assert date in get_available_requests(), (
        f"The date {date} is not in the supported range."
    )


def get_available_requests() -> list[str]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the CAMMESA website.

    Returns
    -------
    list[str]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="cammesa"
    )["AR"]

    # Return the available requests, which are the dates in the format
    # YYYY-MM-DD.
    return (
        pandas.date_range(start=start_date, end=end_date, freq="D")
        .strftime("%Y-%m-%d")
        .to_list()
    )


def get_url(date: str) -> str:
    """
    Get the URL of the electricity demand data on the CAMMESA website.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(date)

    # Return the URL of the electricity demand data.
    return (
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        f"id_region=1002&fecha={date}"
    )


def download_and_extract_data_for_request(date: str) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CAMMESA website.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.

    """
    # Check if the input parameters are valid.
    _check_input_parameters(date)

    logging.info(f"Retrieving electricity demand data for {date}.")

    # Get the URL of the electricity demand data.
    url = get_url(date)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url, "html", read_with="requests.get", read_as="json"
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Remove rows with NaN values for demand.
        dataset = dataset.dropna(subset=["dem"])

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["dem"].values, index=pandas.to_datetime(dataset["fecha"])
        )

        # Drop the last value of the time series because it belongs to
        # the following day.
        electricity_demand_time_series = electricity_demand_time_series[:-1]

        return electricity_demand_time_series
