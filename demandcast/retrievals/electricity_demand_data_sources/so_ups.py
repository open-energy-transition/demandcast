"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the System Operator of the Unified Energy
    System of Russia (SO UES). The data is retrieved one day at a time.

    The page of the hourly generation and consumption gives, for a day
    and an interconnected power system (OES), the generation and the
    consumption of each hour in MW in the attributes of its chart: the
    consumption in data-datay and the generation in data-datay1. Since
    October 2022 the page shows only the generation, but its attributes
    still have the consumption. The hours run from 0:00 to 23:00 in
    Moscow time and are the ends of the hours: the consumption of the
    Centre equals that of the IEA, which republishes it at the starts of
    the hours, one hour earlier. On the days when daylight saving time
    started, until 2010, the page repeats the hour after the skipped
    one with the same value, which is kept once, and on the days when
    it ended it gives the hour that ends at the repeated time once,
    which is left out. Some days, such as 2002-02-01 in the Centre,
    have a page without chart, and give no data.

    The website answers about one request in four with the error 503
    when they are sent two seconds apart, so the requests are sent at
    least REQUEST_INTERVAL seconds apart.

    The terms of SO UES allow the reproduction of its information in
    unchanged form for non-commercial use only, and any other use with
    its written consent.

    Source: https://www.so-ups.ru/functioning/ees/ees-indicators/ees-gen-consump-hour/
"""

import datetime as dt
import logging
import re
import time

import pandas as pd

import utils.fetcher

# The identifier of each interconnected power system on the page.
SYSTEMS = {
    "RUS_CENTER": 530000,
    "RUS_EAST": 540000,
    "RUS_NORTHWEST": 840000,
    "RUS_SIBERIA": 610000,
    "RUS_SOUTH": 550000,
    "RUS_URALS": 630000,
    "RUS_VOLGA": 600000,
}

# The minimum time between two requests, in seconds.
REQUEST_INTERVAL = 3.0

# The time of the last request, from time.monotonic.
_last_request = {"time": float("-inf")}


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[dt.date]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of the interconnected power system.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[datetime.date]
        The days of the data.
    """
    return [day.date() for day in pd.date_range(start_date, end_date)]


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the SO UES website.

    Returns
    -------
    str
        The URL of the page of the hourly generation and consumption.
    """
    return (
        "https://www.so-ups.ru/functioning/ees/ees-indicators/"
        "ees-gen-consump-hour/"
    )


def _wait_for_the_interval() -> None:
    """Wait until REQUEST_INTERVAL has passed since the last request."""
    remaining = REQUEST_INTERVAL - (time.monotonic() - _last_request["time"])
    if remaining > 0:
        time.sleep(remaining)
    _last_request["time"] = time.monotonic()


def download_and_extract_data_for_request(
    day: dt.date, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    day : datetime.date
        The day of the electricity demand data.
    code : str
        The code of the interconnected power system.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW, empty if the page has
        no chart of the day.
    """
    logging.info(f"Retrieving electricity demand data for {day}.")

    _wait_for_the_interval()
    text = utils.fetcher.fetch_text(
        get_url(),
        request_params={
            "tx_mscdugraph_pi[controller]": "Graph",
            "tx_mscdugraph_pi[action]": "fullview",
            "tx_mscdugraph_pi[viewDate]": day.isoformat(),
            "tx_mscdugraph_pi[viewKpo]": str(SYSTEMS[code]),
        },
        timeout=60,
    )

    chart = re.search(r'<div class="big-chart"[^>]*>', text)
    attributes = (
        dict(re.findall(r'data-([a-z0-9]+)="([^"]*)"', chart.group(0)))
        if chart
        else {}
    )
    if attributes.get("date") != day.isoformat():
        logging.warning(f"The page of SO UES has no chart of {day}.")
        return pd.Series(dtype=float)

    electricity_demand_time_series = pd.Series(
        pd.to_numeric(attributes["datay"].split(","), errors="coerce"),
        index=pd.to_datetime(
            attributes["datax"].split(","), format="%Y-%m-%d %H:%M"
        ),
    )
    electricity_demand_time_series = electricity_demand_time_series[
        ~electricity_demand_time_series.index.duplicated()
    ]

    # The times are the ends of the hours.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize(
            "Europe/Moscow", ambiguous="NaT", nonexistent="NaT"
        )
    )
    return electricity_demand_time_series[
        electricity_demand_time_series.index.notna()
    ].dropna()
