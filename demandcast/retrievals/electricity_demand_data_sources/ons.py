"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Operador Nacional do Sistema Elétrico
    (ONS) in Brazil. The data is retrieved for the years from 2000 to
    the current year. The data is retrieved from the available CSV files
    on the ONS website.

    Source: https://dados.ons.org.br/dataset/curva-carga
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

    The data of all subsystems is published in one file per year, so
    the requests are the years of the data.

    Parameters
    ----------
    code : str
        The code of the subsystem.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The years of the data.
    """
    return list(range(start_date.year, end_date.year + 1))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the ONS website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/"
        f"curva-carga-ho/CURVA_CARGA_{year}.csv"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ONS website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Extract the subdivision code from the code.
    subdivision_code = code.split("_")[1]

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url, "csv", csv_kwargs={"sep": ";"}
    )

    # Filter the dataset for the subdivision of interest.
    dataset = dataset[dataset["id_subsistema"] == subdivision_code]

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["val_cargaenergiahomwmed"].values,
        index=pd.to_datetime(dataset["din_instante"]),
    ).tz_localize("America/Sao_Paulo", ambiguous="NaT", nonexistent="NaT")

    # Add one hour to the time index because the time values appear
    # to be provided at the beginning of the time interval.
    electricity_demand_time_series.index += pd.Timedelta(hours=1)

    return electricity_demand_time_series
