"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data of ISO New England (ISO-NE) in the United States, from its web
    services, which need an account of ISO Express (the ISONE_USERNAME
    and ISONE_PASSWORD environment variables). The data is retrieved
    one year at a time, one day at a time.

    The hourly system load gives the demand of New England in MW for
    each hour, by its start in local time with its offset to UTC. Its
    load is the demand of New England of the EIA (eia.py), which is the
    same, value for value. The module takes the native load instead,
    which leaves out the asset related demand: the pumping of the
    pumped storage and the charging of the batteries, up to about
    1.5 GW at night. The web services keep the hourly system load of
    about the last seven years, from 2019-05-31 in October 2026.

    The native load leaves out the solar behind the meters, which
    ISO-NE does not monitor in real time: the solar of the consumers and
    the settlement-only generators, up to about 5.5 GW at midday in
    2025. DemandCast includes it in the gross demand, so the module adds
    an estimate of it to each hour:

    - From 2025-01-29, the first day of the data, the estimate of ISO-NE
      in real time (five-minute estimated zonal load), in MW at each
      five minutes in each of the eight load zones. The module adds the
      mean of the sum of the zones over the samples of the hour, after
      its start and until its end.
    - Before, and in the hours without samples (such as the first hours
      of 2025-01-29), the estimate of ISO-NE for its load forecast (BTM
      PV data, updated about three times a year), which counts only the
      solar of the consumers that do not take part in the markets, about
      60% of the estimate in real time. Its normalized output, the share
      of the installed capacity that produces, is given by hour ending
      in local time, with 24 hours on every day: the hours that the
      changes of the clocks add or remove are at night, when the output
      is zero. The module multiplies it by the capacity of all the
      distributed solar of New England, interpolated between its values
      at the ends of the years in the solar forecasts of ISO-NE, and by
      the ratio of the estimate in real time to this product in 2025,
      0.98. The ratio of all the distributed solar to the solar of the
      consumers is between 1.67 and 1.81 in each year from 2020 to 2025,
      so the estimate is close to the one in real time also in earlier
      years.

    The hours without an estimate of the solar are left out.

    The terms of use of the website of ISO-NE protect its content by
    copyright and allow only its personal use, so its data is not
    redistributed.

    Source: https://webservices.iso-ne.com/docs/v1.1/
    Source: https://www.iso-ne.com/system-planning/system-forecasting/distributed-generation-forecast
"""

import base64
import datetime
import logging

import numpy as np
import pandas as pd
import requests
import utils.config
import utils.fetcher
import utils.time_series

# The web services of ISO-NE.
WEB_SERVICES_URL = "https://webservices.iso-ne.com/api/v1.1"

# The estimate of the solar behind the meters for the load forecast.
BTM_PV_DATA_URL = (
    "https://www.iso-ne.com/static-assets/documents/2020/07/btm_pv_data.xlsx"
)

# The first day of the estimate of the solar behind the meters in real
# time, in local time.
FIRST_DAY_OF_REAL_TIME_SOLAR = pd.Timestamp("2025-01-29")

# The capacity of the distributed solar of New England in MW at the end
# of each year, of all the categories (in the markets or not), from the
# pre-discount cumulative totals of the solar forecasts of ISO-NE of the
# next year.
DISTRIBUTED_SOLAR_CAPACITY = {
    2018: 2883.8,
    2019: 3432.4,
    2020: 3995.9,
    2021: 4767.1,
    2022: 5472.7,
    2023: 6541.5,
    2024: 7634.0,
    2025: 8361.0,
}

# The ratio of the estimate in real time to the normalized output of the
# estimate for the load forecast times the capacity, in 2025.
REAL_TIME_RATIO = 0.98

# The time zone of New England.
TIME_ZONE = "America/New_York"


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of New England.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The first day and the day after the last one of each year of
        the data, in local time.
    """
    return utils.time_series.split_period(
        start_date, end_date + datetime.timedelta(days=1), "YS"
    )


def get_url(service: str, day: pd.Timestamp) -> str:
    """
    Get the URL of the data of a day on the web services of ISO-NE.

    Parameters
    ----------
    service : str
        The name of the service, such as "hourlysysload".
    day : pandas.Timestamp
        The day, in local time.

    Returns
    -------
    str
        The URL of the data of the day.
    """
    return f"{WEB_SERVICES_URL}/{service}/day/{day:%Y%m%d}"


def _get_headers() -> dict[str, str]:
    """
    Get the headers of the requests to the web services.

    Returns
    -------
    dict[str, str]
        The headers, with the credentials of the account of ISO Express.
    """
    username = utils.config.read_api_key("ISONE_USERNAME", "ISO New England")
    password = utils.config.read_api_key("ISONE_PASSWORD", "ISO New England")
    credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {credentials}",
    }


def _fetch_day(service: str, day: pd.Timestamp, headers: dict) -> dict:
    """
    Fetch the data of a day from the web services of ISO-NE.

    Parameters
    ----------
    service : str
        The name of the service.
    day : pandas.Timestamp
        The day, in local time.
    headers : dict
        The headers of the request.

    Returns
    -------
    dict
        The data of the day, empty for a day without data.

    Raises
    ------
    TypeError
        If the response is not a requests.Response object.
    """
    response = utils.fetcher.fetch_data(
        get_url(service, day),
        "html",
        timeout=60,
        read_as="plain",
        header_params=headers,
    )
    if not isinstance(response, requests.Response):
        raise TypeError(
            f"The extracted response is a {type(response)} object, "
            "expected a requests.Response object."
        )
    return response.json()


def _get_native_load(day: pd.Timestamp, headers: dict) -> pd.Series:
    """
    Get the hourly native load of New England in a day.

    Parameters
    ----------
    day : pandas.Timestamp
        The day, in local time.
    headers : dict
        The headers of the requests.

    Returns
    -------
    pandas.Series
        The native load in MW at the end of each hour, in UTC.
    """
    rows = (
        _fetch_day("hourlysysload", day, headers)
        .get("HourlySystemLoads", {})
        .get("HourlySystemLoad", [])
    )
    if not rows:
        logging.warning(f"ISO-NE gives no hourly system load on {day.date()}.")
        return pd.Series(dtype=float)
    dataset = pd.DataFrame(rows)
    starts = pd.to_datetime(dataset["BeginDate"], utc=True)
    return pd.Series(
        dataset["NativeLoad"].astype(float).to_numpy(),
        index=pd.DatetimeIndex(starts + pd.Timedelta(hours=1)),
    )


def _get_real_time_solar(day: pd.Timestamp, headers: dict) -> pd.Series:
    """
    Get the estimate in real time of the solar behind the meters.

    Parameters
    ----------
    day : pandas.Timestamp
        The day, in local time.
    headers : dict
        The headers of the requests.

    Returns
    -------
    pandas.Series
        The solar of New England in MW at each five minutes, in UTC.
    """
    rows = (
        _fetch_day("fiveminuteestimatedzonalload", day, headers)
        .get("isone_web_services", {})
        .get("five_min_estimated_zonal_loads", {})
        .get("five_min_estimated_zonal_load", [])
    )
    if not rows:
        return pd.Series(dtype=float)
    dataset = pd.DataFrame(rows)
    dataset["time"] = pd.to_datetime(dataset["interval_begin_date"], utc=True)
    return dataset.groupby("time")["estimated_btm_pv_mw"].sum().astype(float)


def _get_distributed_solar_capacity(times: pd.DatetimeIndex) -> np.ndarray:
    """
    Get the capacity of the distributed solar of New England.

    Parameters
    ----------
    times : pandas.DatetimeIndex
        The times, in UTC.

    Returns
    -------
    numpy.ndarray
        The capacity in MW at the times, interpolated between the ends
        of the years.
    """
    year_ends = pd.DatetimeIndex(
        [
            pd.Timestamp(year + 1, 1, 1, tz=TIME_ZONE)
            for year in DISTRIBUTED_SOLAR_CAPACITY
        ]
    )

    def to_seconds(index: pd.DatetimeIndex) -> np.ndarray:
        return (
            index.tz_convert("UTC")
            .to_numpy(dtype="datetime64[s]")
            .astype("int64")
        )

    return np.asarray(
        np.interp(
            to_seconds(times),
            to_seconds(year_ends),
            list(DISTRIBUTED_SOLAR_CAPACITY.values()),
        )
    )


def _get_forecast_solar() -> pd.Series:
    """
    Get the estimate of the solar behind the meters for the forecast.

    Returns
    -------
    pandas.Series
        The estimate of all the distributed solar of New England in MW
        at the end of each hour, in UTC.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas ExcelFile.
    """
    excel_file = utils.fetcher.fetch_data(
        BTM_PV_DATA_URL, "html", timeout=120, read_as="excel_file"
    )
    if not isinstance(excel_file, pd.ExcelFile):
        raise TypeError(
            f"The extracted data is a {type(excel_file)} object, "
            "expected a pandas ExcelFile."
        )
    dataset = pd.read_excel(excel_file, sheet_name="Normalized BTM PV")

    # Localize the starts of the hours, leaving out those that the
    # changes of the clocks remove or repeat, at night.
    starts = pd.to_datetime(
        dataset[["Year", "Month", "Day"]].rename(columns=str.lower)
    ) + pd.to_timedelta(dataset["HourEnding"] - 1, unit="h")
    normalized_output = utils.time_series.localize_interval_starts(
        pd.Series(dataset["ISONE"].astype(float).to_numpy(), index=starts),
        TIME_ZONE,
        pd.Timedelta(hours=1),
        ambiguous="NaT",
        nonexistent="NaT",
    )
    normalized_output = normalized_output[normalized_output.index.notna()]
    normalized_output.index = pd.DatetimeIndex(
        normalized_output.index
    ).tz_convert("UTC")
    normalized_output = normalized_output[
        ~normalized_output.index.duplicated()
    ]

    # Give the hours left out the output of the hours around them.
    hours = pd.date_range(
        normalized_output.index[0], normalized_output.index[-1], freq="h"
    )
    normalized_output = normalized_output.reindex(hours).interpolate(limit=2)

    return (
        normalized_output
        * _get_distributed_solar_capacity(
            pd.DatetimeIndex(normalized_output.index)
        )
        * REAL_TIME_RATIO
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The first day and the day after the last one, in local time.
    code : str
        The code of New England.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW, in UTC.
    """
    start_day, end_day = period
    logging.info(
        "Retrieving electricity demand data from "
        f"{start_day.date()} to {(end_day - pd.Timedelta(days=1)).date()}."
    )
    headers = _get_headers()
    days = pd.date_range(start_day, end_day, freq="D", inclusive="left")

    native_load = pd.concat(
        [_get_native_load(day, headers) for day in days]
    ).sort_index()
    native_load = native_load[~native_load.index.duplicated()]

    # The estimate in real time of the solar, from its first day, and
    # the one for the load forecast for the hours without it: before
    # the first day, in the first hours of the first day, and in the
    # hours without samples.
    solar = pd.Series(dtype=float)
    real_time_days = days[days >= FIRST_DAY_OF_REAL_TIME_SOLAR]
    if len(real_time_days) > 0:
        samples = pd.concat(
            [_get_real_time_solar(day, headers) for day in real_time_days]
        ).sort_index()
        if not samples.empty:
            # Each hour takes the samples after its start and until its
            # end, and the hour repeated when the clocks go back, which
            # has no samples, takes the hours around it, at night.
            solar = (
                samples.resample("h", closed="right", label="right")
                .mean()
                .interpolate(limit=2)
            )
    forecast_solar = _get_forecast_solar()
    solar = (
        forecast_solar if solar.empty else solar.combine_first(forecast_solar)
    )

    return (native_load + solar.reindex(native_load.index)).dropna()
