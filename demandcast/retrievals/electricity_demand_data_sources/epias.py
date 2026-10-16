"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the transparency platform of Enerji Piyasaları İşletme
    A.Ş. (EPIAS) in Turkey. The data is retrieved in one-year intervals
    from the API of the platform, which needs the username and password
    of a free account of EPIAS, in the environment variables
    EPIAS_USERNAME and EPIAS_PASSWORD.

    The API gives the real-time consumption in MWh of each hour, the
    average demand in MW, from 2015-12-31, at the start of the hour with
    its offset from UTC, two hours after its end. The end date of a
    request is included. When daylight saving time started on
    2016-03-27, the hour that starts at 02:00 has a consumption of 0 and
    the next one comes twice, so the cleaning leaves one hour without
    data. Turkey has had no daylight saving time since September 2016.

    Source: https://seffaflik.epias.com.tr/
    Source: https://seffaflik.epias.com.tr/electricity-service/technical/en/index.html
"""

import datetime
import logging

import pandas as pd
import requests
import utils.config
import utils.fetcher
import utils.time_series

# The URL that gives the tickets of the users of EPIAS.
TICKET_URL = "https://giris.epias.com.tr/cas/v1/tickets"


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EPIAS transparency platform.

    Parameters
    ----------
    code : str
        The code of Turkey.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The first and last day of each one-year period.
    """
    # Split the period of the data into one-year periods.
    return utils.time_series.split_period(start_date, end_date, "YS")


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the EPIAS platform.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return (
        "https://seffaflik.epias.com.tr/electricity-service/v1/"
        "consumption/data/realtime-consumption"
    )


def _get_ticket() -> str:
    """
    Get a ticket of the account of EPIAS for the requests to the API.

    The ticket is valid for two hours.

    Returns
    -------
    str
        The ticket granting ticket (TGT).

    Raises
    ------
    TypeError
        If the response is not a requests.Response object.
    """
    response = utils.fetcher.fetch_data(
        TICKET_URL,
        "html",
        read_with="requests.post",
        read_as="plain",
        header_params={"Accept": "text/plain"},
        post_data_params={
            "username": utils.config.read_api_key("EPIAS_USERNAME", "EPIAS"),
            "password": utils.config.read_api_key("EPIAS_PASSWORD", "EPIAS"),
        },
    )
    if not isinstance(response, requests.Response):
        raise TypeError(
            f"The extracted response is a {type(response)} object, "
            "expected a requests.Response object."
        )
    return response.text.strip()


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the EPIAS transparency platform.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The first and last day of the data retrieval.
    code : str
        The code of Turkey.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    start_date, end_date = period

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    # Fetch the hourly consumption, with a ticket of the account. The
    # dates of the request have their offset from UTC in Turkey.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(),
        "html",
        timeout=120,
        read_with="requests.post",
        read_as="json",
        header_params={"TGT": _get_ticket()},
        post_json={
            "startDate": start_date.tz_localize("Europe/Istanbul").isoformat(),
            "endDate": end_date.tz_localize("Europe/Istanbul").isoformat(),
        },
        json_keys=["items"],
    )
    if dataset.empty:
        return pd.Series(dtype="float64")

    # The times are the starts of the hours, with their offset from
    # UTC. Move them to the ends of the hours.
    starts = pd.DatetimeIndex(pd.to_datetime(dataset["date"], utc=True))
    return pd.Series(
        dataset["consumption"].to_numpy(),
        index=(starts + pd.Timedelta(hours=1)).tz_convert("Europe/Istanbul"),
    )
