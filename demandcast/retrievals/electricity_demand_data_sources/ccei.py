"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Canadian Centre for Energy Information
    (CCEI). The data has various time resolutions.

    CCEI gathers the data of the utilities and system operators of the
    provinces and territories, in MW at times in UTC. The values are
    readings at the times or averages of the intervals that end at
    them: the hourly averages of Alberta, Ontario and Quebec match those
    of AESO, IESO and Hydro-Québec. The readings of some provinces come
    at irregular times, and the data has a few spikes, such as about
    20,000 MW in Alberta or 80,000 MW in Quebec.

    British Columbia is retrieved from BC Hydro instead: CCEI gives its
    data one or two hours early until 2015, from the starts of the hours
    converted with UTC-7 all year, and about 0.5% higher since 2016.
    Saskatchewan is left out, since its data is daily.

    Source: https://energy-information.canada.ca/en/resources/high-frequency-electricity-data
"""

import datetime

import pandas as pd
import utils.fetcher


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is retrieved all at once, so there is a single request,
    without parameters.

    Parameters
    ----------
    code : str
        The code of the subdivision.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[None]
        The single request.
    """
    return [None]


def get_url(code: str) -> str:
    """
    Get the URL of the electricity demand data on the CCEI website.

    Parameters
    ----------
    code : str
        The code of the Province or Territory of interest.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the subdivision code is not supported.
    """
    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Define the mapping between the subdivision codes and API variable
    # names.
    variable_names = {
        "AB": ["AB", "INTERNAL_LOAD"],
        "BC": ["BC", "LOAD"],
        "NB": ["NB", "LOAD"],
        "NL": ["NL", "DEMAND"],
        "NS": ["NS", "LOAD"],
        "ON": ["ON", "ONTARIO_DEMAND"],
        "PE": ["PE", "ON_ISL_LOAD"],
        "QC": ["QC", "DEMAND"],
        "SK": ["SK", "SYSTEM_DEMAND"],
        "YT": ["YK", "TOTAL"],
    }

    if subdivision_code not in variable_names:
        raise ValueError(
            f"Subdivision code {subdivision_code} is not supported."
        )

    # Return the URL of the electricity demand data.
    return (
        "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/"
        f"CCEI,DF_HFED_{variable_names[subdivision_code][0]},1.0/"
        f"N...{variable_names[subdivision_code][1]}?"
        "&dimensionAtObservation=AllDimensions&format=csv"
    )


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CCEI website.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of the subdivision.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Get the URL of the electricity demand data.
    url = get_url(code)

    # Fetch the CSV file of the subdivision.
    dataset = utils.fetcher.fetch_dataframe(url, "csv")

    if code == "CAN_NB":
        # Remove unknown code from the time step values.
        dataset["TIME_PERIOD"] = dataset["TIME_PERIOD"].str.replace(
            ".000Z", ""
        )

    if code == "CAN_ON":
        # The data of Ontario comes from IESO, whose hours end at 1:00
        # to 24:00 in Eastern Standard Time all year. CCEI keeps these
        # times in DATETIME_LOCAL, with the hour 24 at 00:00 of the same
        # day, and converts them to UTC (TIME_PERIOD) as if they
        # followed daylight saving time: an hour early in summer, and a
        # day early at midnight. Read them in Eastern Standard Time
        # (UTC-5), with the hour 24 at midnight of the next day.
        local_times = pd.to_datetime(dataset["DATETIME_LOCAL"])
        local_times += pd.to_timedelta(
            (local_times.dt.hour == 0).astype(int), unit="D"
        )
        times = pd.DatetimeIndex(local_times + pd.Timedelta(hours=5))
    else:
        times = pd.DatetimeIndex(pd.to_datetime(dataset["TIME_PERIOD"]))

    # Extract the electricity demand time series with UTC time zone.
    electricity_demand_time_series = (
        pd.Series(data=dataset["OBS_VALUE"].values, index=times)
        .tz_localize("UTC")
        .sort_index()
    )

    return electricity_demand_time_series
