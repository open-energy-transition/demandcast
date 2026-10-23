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

    From 2020-12-30, the real-time consumption is the real-time
    generation with the licence-exempt generation, which is mostly solar
    on the distribution networks and grew from zero in 2016 to about
    4 GW at midday in 2020: on 3 and 4 June 2024 the consumption is
    their sum at every hour. Until 2020-12-29, it is the real-time
    generation alone, within about 0.5 GW of exchanges, so it leaves out
    the licence-exempt generation, which jumps from 300 to 575 MW to
    4,476 MW in the largest daily difference between consumption and
    generation on 2020-12-30. The module adds the licence-exempt
    generation of the API ("toplam") to the consumption until then, for
    the gross demand of DemandCast, and leaves out the hours without it.
    The licence-exempt generation is that fed into the network and paid
    by the support scheme of renewables (YEKDEM), so the solar consumed
    where it is produced is still left out.

    Source: https://seffaflik.epias.com.tr/
    Source: https://seffaflik.epias.com.tr/electricity-service/technical/en/index.html
"""

import datetime
import logging

import pandas as pd

import utils.config
import utils.fetcher
import utils.time_series

# The URL that gives the tickets of the users of EPIAS.
TICKET_URL = "https://giris.epias.com.tr/cas/v1/tickets"

# The URL of the API of the electricity data of EPIAS.
API_URL = "https://seffaflik.epias.com.tr/electricity-service/v1/"

# The time from which the real-time consumption includes the
# licence-exempt generation.
LICENCE_EXEMPT_INCLUDED = pd.Timestamp("2020-12-30", tz="Europe/Istanbul")


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
    return API_URL + "consumption/data/realtime-consumption"


def get_licence_exempt_url() -> str:
    """
    Get the URL of the licence-exempt generation on the EPIAS platform.

    Returns
    -------
    str
        The URL of the licence-exempt generation.
    """
    return API_URL + "renewables/data/unlicensed-generation-amount"


def _get_ticket() -> str:
    """
    Get a ticket of the account of EPIAS for the requests to the API.

    The ticket is valid for two hours.

    Returns
    -------
    str
        The ticket granting ticket (TGT).
    """
    response = utils.fetcher.fetch_response(
        TICKET_URL,
        "POST",
        header_params={"Accept": "text/plain"},
        post_data_params={
            "username": utils.config.read_api_key("EPIAS_USERNAME", "EPIAS"),
            "password": utils.config.read_api_key("EPIAS_PASSWORD", "EPIAS"),
        },
    )
    return response.text.strip()


def _fetch_hourly_data(
    url: str, start_date: pd.Timestamp, end_date: pd.Timestamp, ticket: str
) -> pd.DataFrame:
    """
    Fetch hourly data of the API of EPIAS.

    Parameters
    ----------
    url : str
        The URL of the data.
    start_date : pandas.Timestamp
        The first day of the data.
    end_date : pandas.Timestamp
        The last day of the data, which is included.
    ticket : str
        The ticket of the account.

    Returns
    -------
    pandas.DataFrame
        The data of each hour, by the start of the hour with its offset
        from UTC ("date").
    """
    # The dates of the request have their offset from UTC in Turkey.
    return utils.fetcher.fetch_dataframe(
        url,
        "html",
        timeout=120,
        read_with="requests.post",
        read_as="json",
        header_params={"TGT": ticket},
        post_json={
            "startDate": start_date.tz_localize("Europe/Istanbul").isoformat(),
            "endDate": end_date.tz_localize("Europe/Istanbul").isoformat(),
        },
        json_keys=["items"],
    )


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

    # Fetch the hourly consumption, with a ticket of the account.
    ticket = _get_ticket()
    dataset = _fetch_hourly_data(get_url(), start_date, end_date, ticket)
    if dataset.empty:
        return pd.Series(dtype="float64")

    # The times are the starts of the hours, with their offset from UTC.
    starts = pd.DatetimeIndex(pd.to_datetime(dataset["date"], utc=True))
    consumption = pd.Series(
        dataset["consumption"].to_numpy(dtype="float64"), index=starts
    )

    # Add the licence-exempt generation to the consumption of the hours
    # before it includes it, and leave out those without it.
    before = consumption.index < LICENCE_EXEMPT_INCLUDED
    if before.any():
        last_day = min(
            end_date,
            (LICENCE_EXEMPT_INCLUDED - pd.Timedelta(days=1)).tz_localize(None),
        )
        exempt = _fetch_hourly_data(
            get_licence_exempt_url(), start_date, last_day, ticket
        )
        generation = pd.Series(dtype="float64")
        if not exempt.empty:
            generation = pd.Series(
                exempt["toplam"].to_numpy(dtype="float64"),
                index=pd.DatetimeIndex(
                    pd.to_datetime(exempt["date"], utc=True)
                ),
            )
            generation = generation[~generation.index.duplicated()]
        consumption[before] += generation.reindex(consumption.index[before])
        consumption = consumption.dropna()

    # Move the times to the ends of the hours.
    return pd.Series(
        consumption.to_numpy(),
        index=(
            pd.DatetimeIndex(consumption.index) + pd.Timedelta(hours=1)
        ).tz_convert("Europe/Istanbul"),
    )
