"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the Real-Time Electricity Tracker of the International
    Energy Agency (IEA). The data is retrieved in three-month intervals.

    The API of the tracker gives the hourly demand of each country, or
    of each region of a country, in GW. Its times are marked as UTC but
    are local times: compared with the data that DemandCast retrieves
    from the system operators and from ENTSO-E, the EIA, the CCEI and
    OCCTO, they are the starts of the hours in the time zone that the
    IEA gives for the country (TIME_ZONES), with these exceptions:

    - The times of Colombia, Ukraine, Uruguay and the regions of the
      United States are the ends of the hours (HOUR_ENDS), those of the
      United States in the time of New York. The times of California
      keep the delay of one hour of CAISO in the data of the EIA, from
      2022-06-16 to 2025-12-02 (see eia.py).
    - The times of Australia are in the standard time of eastern
      Australia, without daylight saving time, those of Ontario in the
      eastern standard time, and those of Baja California and Baja
      California Sur in their own time zones (CODE_TIME_ZONES).

    The times of the earlier years of some series follow other rules,
    which DemandCast does not apply: those of Colombia until 2023 are
    about three hours later than in the data of XM, and those of Chūbu
    until 2019 and of Chūgoku and Tōhoku until 2018 two hours later than
    in the data of OCCTO, so these series start in the next year. The
    times of the countries and regions that DemandCast does not
    retrieve from another source are taken as those of the others. The
    hour that the API gives twice when daylight saving time ends, or
    once, is left out.

    Each series of the IEA is the data of a system operator, whose terms
    also apply. Those of GSO, the operator of Peninsular Malaysia,
    forbid downloading and storing the content of its own website
    without the written consent of TNB; its series is taken from the
    publication of the IEA. The IEA republishes the data of the EIA,
    ENTSO-E, the CCEI and OCCTO, so it is compiled in the yaml file and
    ranks after them (see cleaning/combining.py).

    The demand of India is that of its states, from NITI (see
    niti.py), so the national series of the IEA is not retrieved.

    Source: https://www.iea.org/data-and-statistics/data-tools/real-time-electricity-tracker
"""

import datetime as dt
import itertools
import json
import logging
from typing import Any

import pandas as pd

import utils.fetcher
import utils.time_series

# The time zone of each country in the API of the IEA.
TIME_ZONES = {
    "ALB": "Europe/Tirane",
    "ARG": "America/Argentina/Buenos_Aires",
    "AUS": "Australia/Sydney",
    "AUT": "Europe/Vienna",
    "BEL": "Europe/Brussels",
    "BGD": "Asia/Dhaka",
    "BGR": "Europe/Sofia",
    "BIH": "Europe/Sarajevo",
    "BOL": "America/La_Paz",
    "BRA": "America/Sao_Paulo",
    "CAN": "America/Toronto",
    "CHE": "Europe/Zurich",
    "CHL": "America/Santiago",
    "COL": "America/Bogota",
    "CRI": "America/Costa_Rica",
    "CYP": "Europe/Nicosia",
    "CZE": "Europe/Prague",
    "DEU": "Europe/Berlin",
    "DNK": "Europe/Copenhagen",
    "ESP": "Europe/Madrid",
    "EST": "Europe/Tallinn",
    "FIN": "Europe/Helsinki",
    "FRA": "Europe/Paris",
    "GBR": "Europe/London",
    "GEO": "Asia/Tbilisi",
    "GRC": "Europe/Athens",
    "GTM": "America/Guatemala",
    "HND": "America/Tegucigalpa",
    "HRV": "Europe/Zagreb",
    "HUN": "Europe/Budapest",
    "IRL": "Europe/Dublin",
    "IRN": "Asia/Tehran",
    "ITA": "Europe/Rome",
    "JPN": "Asia/Tokyo",
    "KOR": "Asia/Seoul",
    "LKA": "Asia/Colombo",
    "LTU": "Europe/Vilnius",
    "LUX": "Europe/Luxembourg",
    "LVA": "Europe/Riga",
    "MDA": "Europe/Chisinau",
    "MEX": "America/Mexico_City",
    "MKD": "Europe/Skopje",
    "MNE": "Europe/Podgorica",
    "MYS": "Asia/Kuala_Lumpur",
    "NGA": "Africa/Lagos",
    "NIC": "America/Managua",
    "NLD": "Europe/Amsterdam",
    "NOR": "Europe/Oslo",
    "NZL": "Pacific/Auckland",
    "PAN": "America/Panama",
    "PER": "America/Lima",
    "PHL": "Asia/Manila",
    "POL": "Europe/Warsaw",
    "PRT": "Europe/Lisbon",
    "ROU": "Europe/Bucharest",
    "RUS": "Europe/Moscow",
    "SGP": "Asia/Singapore",
    "SLV": "America/El_Salvador",
    "SRB": "Europe/Belgrade",
    "SVK": "Europe/Bratislava",
    "SVN": "Europe/Ljubljana",
    "SWE": "Europe/Stockholm",
    "THA": "Asia/Bangkok",
    "TUR": "Europe/Istanbul",
    "TWN": "Asia/Taipei",
    "UKR": "Europe/Kyiv",
    "URY": "America/Montevideo",
    "USA": "America/New_York",
    "XKX": "Europe/Belgrade",
    "ZAF": "Africa/Johannesburg",
}

# The time zones of the codes whose times are not in the time zone of
# their country.
CODE_TIME_ZONES = {
    "AUS_DKIS": "Australia/Brisbane",
    "AUS_NSW": "Australia/Brisbane",
    "AUS_QLD1": "Australia/Brisbane",
    "AUS_SA1": "Australia/Brisbane",
    "AUS_SWIS": "Australia/Brisbane",
    "AUS_TAS": "Australia/Brisbane",
    "AUS_VIC": "Australia/Brisbane",
    "CAN_ON": "Etc/GMT+5",
    "MEX_BCA": "America/Tijuana",
    "MEX_BCS": "America/Mazatlan",
}

# The countries whose times are the ends of the hours.
HOUR_ENDS = {"COL", "UKR", "URY", "USA"}

# The names of the regions of each subdivision in the API, in the order
# of their periods when a region was renamed.
REGIONS = {
    "AUS_DKIS": ["Northern Territory"],
    "AUS_NSW": ["New South Wales"],
    "AUS_QLD1": ["Queensland"],
    "AUS_SA1": ["South Australia"],
    "AUS_SWIS": ["Western Australia"],
    "AUS_TAS": ["Tasmania"],
    "AUS_VIC": ["Victoria"],
    "BOL_C": ["Cochabamba"],
    "BOL_H": ["Chuquisaca"],
    "BOL_L": ["La Paz"],
    "BOL_O": ["Oruro"],
    "BOL_P": ["Potosí"],
    "BOL_SIN-B": ["Beni"],
    "BOL_SIN-S": ["Santa Cruz"],
    "BOL_T": ["Tarija"],
    "BRA_N": ["Norte"],
    "BRA_N-2000": ["Norte"],
    "BRA_N-2013": ["Norte"],
    "BRA_N-2015": ["Norte"],
    "BRA_NE": ["Nordeste"],
    "BRA_S": ["Sul"],
    "BRA_SE": ["Sudeste/Centro Oeste"],
    "BRA_SE-2009": ["Sudeste/Centro Oeste"],
    "CAN_AB": ["Alberta"],
    "CAN_BC": ["British Columbia"],
    "CAN_NB": ["New Brunswick"],
    "CAN_NL-ISLAND": ["Newfoundland and Labrador"],
    "CAN_NS": ["Nova Scotia"],
    "CAN_ON": ["Ontario"],
    "CAN_PE": ["Prince Edward Island"],
    "CAN_QC-INTEGRATED": ["Quebec"],
    "CAN_YT-INTEGRATED": ["Yukon"],
    "GBR_GB": ["Great Britain"],
    "JPN_Chūbu": ["Chubu"],
    "JPN_Chūgoku": ["Chugoku"],
    "JPN_Hokkaidō": ["Hokkaido"],
    "JPN_Hokuriku": ["Hokuriku"],
    "JPN_Kansai": ["Kansai"],
    "JPN_Kantō": ["Tokyo"],
    "JPN_Kyūshū": ["Kyushu"],
    "JPN_Okinawa": ["Okinawa"],
    "JPN_Shikoku": ["Shikoku"],
    "JPN_Tōhoku": ["Tohoku"],
    "MEX_BCA": ["BCA-BCA"],
    "MEX_BCS": ["BCS-BCA", "BCS-BCS"],
    "MEX_CEN": ["SIN-CEN", "SIN-CEL"],
    "MEX_NES": ["SIN-NES"],
    "MEX_NOR": ["SIN-NOR"],
    "MEX_NTE": ["SIN-NTE"],
    "MEX_OCC": ["SIN-OCC"],
    "MEX_ORI": ["SIN-ORI"],
    "MEX_PEN": ["SIN-PEN"],
    "NZL_NI": ["North Island"],
    "NZL_SI": ["South Island"],
    "PHL_LUZON": ["Luzon"],
    "PHL_MINDANAO": ["Mindanao"],
    "PHL_VISAYAS": ["Visayas"],
    "RUS_CENTER": ["UES Center"],
    "RUS_EAST": ["UES East"],
    "RUS_NORTHWEST": ["UES of the North-West"],
    "RUS_SIBERIA": ["UES Siberia"],
    "RUS_SOUTH": ["UES South"],
    "RUS_URALS": ["UES Ural"],
    "RUS_VOLGA": ["UES of the Middle Volga"],
    "USA_CAL": ["California"],
    "USA_CAR": ["Carolinas"],
    "USA_CENT": ["Central"],
    "USA_FLA": ["Florida"],
    "USA_MIDA": ["Mid-Atlantic"],
    "USA_MIDW": ["Midwest"],
    "USA_NE": ["New England"],
    "USA_NW": ["Northwest"],
    "USA_NY": ["New York"],
    "USA_SE": ["Southeast"],
    "USA_SW": ["Southwest"],
    "USA_TEN": ["Tennessee"],
    "USA_TEX": ["Texas"],
}


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The first day of each quarter of the data, or the start date,
        and the first day of the next quarter, or the day after the end
        date.

    Notes
    -----
    The requests are quarters, because the API answers some requests
    of a region with an internal error when they take more than about
    15 seconds, which a year, and at times half a year, does.
    """
    day_after_end = end_date + dt.timedelta(days=1)
    boundaries = (
        pd.date_range(start_date, day_after_end, freq="QS")
        .union(pd.to_datetime([start_date, day_after_end]))
        .drop_duplicates()
    )
    return list(itertools.pairwise(boundaries))


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the IEA website.

    Returns
    -------
    str
        The URL of the hourly demand in the API of the tracker.
    """
    return "https://api.iea.org/rte/demand/timeseries"


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The first day of the data and the day after the last one, in
        local time.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    A subdivision whose region was renamed takes the values of each of
    its names, those of the later name where both have values.
    """
    start_date, end_date = period
    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    country_code = code.split("_", maxsplit=1)[0]
    names = REGIONS.get(code)
    parameters = (
        [{"Region": name} for name in names]
        if names
        else [{"ISO3": country_code}]
    )

    electricity_demand_time_series = pd.Series(dtype=float)
    for parameter in parameters:
        electricity_demand_time_series = _download(
            start_date, end_date, parameter
        ).combine_first(electricity_demand_time_series)

    # The local times of the ends of the hours become those of their
    # starts.
    if country_code in HOUR_ENDS:
        electricity_demand_time_series = electricity_demand_time_series.shift(
            -1, freq="h"
        )

    electricity_demand_time_series = electricity_demand_time_series[
        (electricity_demand_time_series.index >= start_date)
        & (electricity_demand_time_series.index < end_date)
    ]

    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            CODE_TIME_ZONES.get(code, TIME_ZONES[country_code]),
            pd.Timedelta(hours=1),
            ambiguous="NaT",
            nonexistent="NaT",
        )
    )
    return electricity_demand_time_series[
        electricity_demand_time_series.index.notna()
    ].dropna()


def _fetch_records(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    parameter: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Fetch the hourly records of a period, or of each of its months.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The first day of the data.
    end_date : pandas.Timestamp
        The day after the last one.
    parameter : dict[str, str]
        The country ("ISO3") or the region ("Region") in the API.

    Returns
    -------
    list[dict[str, Any]]
        The records of the API, with the time ("Date") and the demand
        in GW ("Value") of each hour.

    Raises
    ------
    utils.fetcher.DataNotFoundError
        If the data is not found.
    ConnectionError
        If the API cannot answer the request of a month.

    Notes
    -----
    The API answers some requests of the largest regions, such as the
    Mid-Atlantic of the United States, with an internal error even for
    a quarter, so a period that it cannot answer is requested again
    month by month.
    """
    try:
        return json.loads(
            utils.fetcher.fetch_text(
                get_url(),
                request_params={
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "precision": "hour",
                    **parameter,
                },
                timeout=120,
            )
        )
    except utils.fetcher.DataNotFoundError:
        raise
    except ConnectionError:
        boundaries = (
            pd.date_range(start_date, end_date, freq="MS")
            .union(pd.DatetimeIndex([start_date, end_date]))
            .drop_duplicates()
        )
        if len(boundaries) <= 2:
            raise
        logging.warning(
            f"The IEA cannot answer the request of {parameter} from "
            f"{start_date.date()} to {end_date.date()}, which is requested "
            "month by month."
        )
        return [
            record
            for start, end in itertools.pairwise(boundaries)
            for record in _fetch_records(start, end, parameter)
        ]


def _download(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    parameter: dict[str, str],
) -> pd.Series:
    """
    Download the hourly demand of a country or region.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The first day of the data.
    end_date : pandas.Timestamp
        The day after the last one.
    parameter : dict[str, str]
        The country ("ISO3") or the region ("Region") in the API.

    Returns
    -------
    pandas.Series
        The electricity demand in MW, by local time without time zone,
        without the times that the API gives twice.
    """
    records = _fetch_records(start_date, end_date, parameter)
    electricity_demand_time_series = pd.Series(
        [record.get("Value") for record in records],
        index=pd.to_datetime(
            [record["Date"] for record in records], format="ISO8601"
        ).tz_localize(None),
        dtype=float,
    ).mul(1000)
    duplicated = electricity_demand_time_series.index.duplicated(keep=False)
    return electricity_demand_time_series[~duplicated].sort_index()
