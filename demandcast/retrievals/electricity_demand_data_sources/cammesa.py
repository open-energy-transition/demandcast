"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Compañía Administradora del Mercado
    Mayorista Eléctrico S.A. (CAMMESA) in Argentina. The data is
    retrieved in one-day intervals.

    The API gives the demand of the national system (SADI) in MW every
    5 minutes, at times with their offset from UTC, from 00:00 to 00:00
    of the next day, for about the last 8 months only. The same request
    gives the demand of the regions, provinces and distributors of the
    regions file below, by their identifier.

    Source: https://api.cammesa.com/demanda-svc/swagger-ui.html#/demanda-ws
    Source: https://api.cammesa.com/demanda-svc/demanda/RegionesDemanda
    Source: https://microfe.cammesa.com/demandaregionchart/assets/data/regionesCammesa.geojson.json
"""

import datetime
import logging

import pandas as pd
import utils.fetcher


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[str]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the CAMMESA website.

    Parameters
    ----------
    code : str
        The code of Argentina.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[str]
        The list of available requests.
    """
    # CAMMESA only provides the data of about the last 8 months, so the
    # requests start at the start date or 8 months before the month of
    # the end date, whichever is later.
    first_day = max(
        pd.Timestamp(start_date),
        pd.Timestamp(end_date.year, end_date.month, 1)
        - pd.DateOffset(months=8),
    )

    # Return the available requests, which are the dates in the format
    # YYYY-MM-DD.
    return (
        pd.date_range(start=first_day, end=end_date, freq="D")
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
    # Return the URL of the electricity demand data of the region 1002,
    # Argentina. The other regions are listed in the regions file of the
    # sources above, such as 422 for Centro or 111 for Patagonia.
    return (
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        f"id_region=1002&fecha={date}"
    )


def download_and_extract_data_for_request(date: str, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CAMMESA website.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.
    code : str
        The code of Argentina.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    """
    logging.info(f"Retrieving electricity demand data for {date}.")

    # Get the URL of the electricity demand data.
    url = get_url(date)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url, "html", read_with="requests.get", read_as="json"
    )

    # Remove rows with NaN values for demand.
    dataset = dataset.dropna(subset=["dem"])

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["dem"].values, index=pd.to_datetime(dataset["fecha"])
    )

    # Drop the last value of the time series because it belongs to
    # the following day.
    electricity_demand_time_series = electricity_demand_time_series[:-1]

    return electricity_demand_time_series
