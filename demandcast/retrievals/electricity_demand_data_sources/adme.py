"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Administrador del Mercado Eléctrico (ADME)
    in Uruguay. The data is retrieved from the available CSV files on
    the ADME website.

    The files give the hourly generation of each source, the imports
    and the exports in MW, and the demand ("Demanda"), which is the
    generation plus the imports minus the exports, at the end of each
    hour in local time. Uruguay has no daylight saving time since 2015.
    A request to the end of a month also gives that month, so the month
    after each one-year period is downloaded twice and kept once.

    Source: https://adme.com.uy/controlpanel.php
"""

import datetime as dt
import io
import logging

import pandas as pd

import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of Uruguay.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    return utils.time_series.split_period(start_date, end_date, "YS")


def get_url(start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    """
    Get the URL of the electricity demand data on the ADME website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date : pandas.Timestamp
        The end date and time of the data retrieval.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the retrieval period is longer than 1 year.

    Notes
    -----
    The website gives at most 1 year of data per request.
    """
    if end_date - start_date > pd.Timedelta("366days"):
        raise ValueError(
            "The retrieval period must be less than or equal to 1 year. "
            f"start_date: {start_date}, end_date: {end_date}"
        )

    return (
        "https://adme.com.uy/panelControl/gpf.php?anod="
        f"{start_date.year}&mesd={start_date.month}&anoh="
        f"{end_date.year}&mesh={end_date.month}&granularidad=1&fuente=1&tipo=1"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The start and end date and time of the data retrieval.
    code : str
        The code of Uruguay.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the file has no table.

    Notes
    -----
    The file of the current year starts with warnings of the PHP code of
    the website, about 8 for each hour, before the header of the table,
    so the table is read from its header ("Fecha;"). A year takes about
    20 seconds to be prepared, so it is fetched with the timeout of a
    file.
    """
    start_date, end_date = period

    logging.info(
        f"Retrieving data from {start_date.date()} to {end_date.date()}."
    )

    url = get_url(start_date, end_date)

    content = utils.fetcher.fetch_response(
        url, timeout=utils.fetcher.FILE_TIMEOUT
    ).content.decode("utf-8", errors="replace")
    header = content.find("Fecha;")
    if header < 0:
        raise ValueError(f"The file of ADME has no table: {url}")
    dataset = pd.read_csv(io.StringIO(content[header:]), sep=";")

    electricity_demand_time_series = pd.Series(
        dataset["Demanda"].values,
        index=pd.to_datetime(dataset["Fecha"], format="%d-%m-%Y %H:%M"),
    )

    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("America/Montevideo")
    )

    return electricity_demand_time_series
