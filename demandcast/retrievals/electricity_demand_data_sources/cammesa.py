"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Compañía Administradora del Mercado
    Mayorista Eléctrico S.A. (CAMMESA) in Argentina. The data is
    retrieved in one-day intervals.

    The API gives the demand of the national system (SADI) in MW every
    5 minutes, at times with their offset from UTC, from 00:00 to 00:00
    of the next day, for about the last 7 to 8 months only: on
    2026-10-19, from 2026-03-01. The same request gives the demand of
    the regions, provinces and distributors of the regions file below,
    by their identifier. The module retrieves 21 provinces of Argentina,
    and Buenos Aires with its autonomous city, which CAMMESA splits into
    Greater Buenos Aires and the rest of the province. Tierra del Fuego
    is not connected.

    The provinces make up the national system, whose demand is not
    retrieved: from March to October 2026, their demand added up to
    98.9% of it (median of the hours, from 95.4% to 100.6% for 98% of
    them).

    Source: https://api.cammesa.com/demanda-svc/swagger-ui.html#/demanda-ws
    Source: https://api.cammesa.com/demanda-svc/demanda/RegionesDemanda
    Source: https://microfe.cammesa.com/demandaregionchart/assets/data/regionesCammesa.geojson.json
"""

import datetime as dt
import logging

import pandas as pd

import utils.fetcher

# The identifiers of the regions of CAMMESA whose demand makes up each
# province of Argentina. CAMMESA splits Buenos Aires and its autonomous
# city into Greater Buenos Aires (426), with the city and the
# municipalities around it, and the rest of the province (425), so only
# their sum matches the two of them. The other regions, such as 422 for
# Centro, group several provinces.
REGION_IDS = {
    "ARG_BA": (426, 425),  # Buenos Aires and its autonomous city
    "ARG_A": (1933,),  # Salta
    "ARG_D": (1944,),  # San Luis
    "ARG_E": (2541,),  # Entre Ríos
    "ARG_F": (1910,),  # La Rioja
    "ARG_G": (1905,),  # Santiago del Estero
    "ARG_H": (1892,),  # Chaco
    "ARG_J": (1922,),  # San Juan
    "ARG_K": (1938,),  # Catamarca
    "ARG_L": (427,),  # La Pampa
    "ARG_M": (1946,),  # Mendoza
    "ARG_N": (2426,),  # Misiones
    "ARG_P": (1886,),  # Formosa
    "ARG_Q": (2528,),  # Neuquén
    "ARG_R": (2525,),  # Río Negro
    "ARG_S": (2540,),  # Santa Fe
    "ARG_T": (1936,),  # Tucumán
    "ARG_U": (2543,),  # Chubut
    "ARG_W": (1893,),  # Corrientes
    "ARG_X": (1945,),  # Córdoba
    "ARG_Y": (1937,),  # Jujuy
    "ARG_Z": (2542,),  # Santa Cruz
}


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[str]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of Argentina or of the subdivision.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[str]
        The list of available requests.

    Notes
    -----
    CAMMESA gives the data of about the last 8 months only, so the
    requests start at the start date or 8 months before the month of the
    end date, whichever is later.
    """
    first_day = max(
        pd.Timestamp(start_date),
        pd.Timestamp(end_date.year, end_date.month, 1)
        - pd.DateOffset(months=8),
    )

    return (
        pd.date_range(start=first_day, end=end_date, freq="D")
        .strftime("%Y-%m-%d")
        .to_list()
    )


def get_url(date: str, region_id: int) -> str:
    """
    Get the URL of the electricity demand data on the CAMMESA website.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.
    region_id : int
        The identifier of the region of CAMMESA.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return (
        "https://api.cammesa.com/demanda-svc/demanda/"
        "ObtieneDemandaYTemperaturaRegionByFecha?"
        f"id_region={region_id}&fecha={date}"
    )


def _download_region(date: str, region_id: int) -> pd.Series:
    """
    Download the electricity demand of a region of CAMMESA for a day.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.
    region_id : int
        The identifier of the region of CAMMESA.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    A day out of the data of the API gives an empty list, which is read
    as a day without data. The last value, at 00:00 of the next day,
    belongs to the next day, so it is dropped.
    """
    dataset = utils.fetcher.fetch_dataframe(
        get_url(date, region_id),
        "html",
        read_with="requests.get",
        read_as="json",
    )

    if "dem" not in dataset.columns:
        return pd.Series(dtype="float64")

    dataset = dataset.dropna(subset=["dem"])

    time_series = pd.Series(
        dataset["dem"].values, index=pd.to_datetime(dataset["fecha"])
    )

    return time_series[:-1]


def download_and_extract_data_for_request(date: str, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    date : str
        The date of the electricity demand data in the format
        YYYY-MM-DD.
    code : str
        The code of Argentina or of the subdivision.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    A time without the value of one of the regions has no sum, so it is
    left out.
    """
    logging.info(f"Retrieving electricity demand data for {date}.")

    # Add up the demand of the regions of the country or subdivision.
    region_time_series = [
        _download_region(date, region_id) for region_id in REGION_IDS[code]
    ]
    electricity_demand_time_series = region_time_series[0]
    for time_series in region_time_series[1:]:
        electricity_demand_time_series = electricity_demand_time_series.add(
            time_series
        )

    return electricity_demand_time_series.dropna()
