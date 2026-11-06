"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Ontario's Independent Electricity System
    Operator (IESO) in Canada. The data is retrieved from the available
    CSV files on the IESO website.

    The times of IESO are in Eastern Standard Time all year, without
    daylight saving time, as on the Power Data page below ("Hour Ending
    (EST)"): the days have 24 hours, also those of daylight saving time.
    The demand is the Ontario demand in MW, without the exports of the
    market demand. The file of 1994 to April 2002 has no data for
    December 2001.

    Source: https://www.ieso.ca/Power-Data/Data-Directory
    Source: https://reports-public.ieso.ca/public/Demand/
    Source: https://www.ieso.ca/power-data
"""

import datetime as dt
import logging

import pandas as pd

import utils.fetcher
import utils.time_series

# Eastern Standard Time, the time of IESO all year.
EASTERN_STANDARD_TIME = dt.timezone(dt.timedelta(hours=-5))


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[tuple[int | None, bool]]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of Ontario.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[int | None, bool]]
        The requests, as tuples of a year and whether the data is
        before May 2002, when the yearly files start: (None, True) for
        the file before May 2002, then (year, False) for each year from
        2002.
    """
    return [(None, True)] + [
        (year, False) for year in range(2002, end_date.year + 1)
    ]


def get_url(year: int | None, before_may_2002: bool) -> str:
    """
    Get the URL of the electricity demand data on the IESO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    before_may_2002 : bool
        Whether the url is for the time period before May 2002.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the year is not between 2002 and the current year.
    """
    if before_may_2002:
        return (
            "https://www.ieso.ca/-/media/Files/IESO/Power-Data/data-directory/"
            "HourlyDemands_1994-2002.csv"
        )
    if year is None or not 2002 <= year <= pd.Timestamp.now().year:
        raise ValueError(
            f"The IESO data of {year} is not available: the yearly files "
            "start in 2002."
        )
    return (
        f"https://reports-public.ieso.ca/public/Demand/PUB_Demand_{year}.csv"
    )


def download_and_extract_data_for_request(
    year_and_old_file: tuple[int | None, bool], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    year_and_old_file : tuple[int | None, bool]
        The year of the electricity demand data, and whether the data
        is in the file of the time period before May 2002, whose year
        is None.
    code : str
        The code of Ontario.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    The times of the file before May 2002 are the starts of the hours:
    the file ends at 23:00 on 30 April 2002, the hour before the first
    one of the yearly files. The times of 1996 have a different format
    from those of the other years. The hours of the yearly files are
    numbered from 1 to 24 by their ends, so the hour 24 ends at midnight
    of the next day.
    """
    year, before_may_2002 = year_and_old_file

    url = get_url(year=year, before_may_2002=before_may_2002)

    if before_may_2002:
        logging.info(
            "Retrieving electricity demand data for the years 1994 to 2002."
        )

        dataset = utils.fetcher.fetch_dataframe(
            url, "html", read_with="requests.get"
        )

        electricity_demand_time_series = pd.Series(
            dataset["OntarioDemand"].values,
            index=pd.to_datetime(dataset["DateTime"], format="mixed"),
        )

        # Move the times from the starts to the ends of the hours.
        electricity_demand_time_series = (
            utils.time_series.localize_interval_starts(
                electricity_demand_time_series,
                EASTERN_STANDARD_TIME,
                pd.Timedelta(hours=1),
            )
        )

        return electricity_demand_time_series

    logging.info(f"Retrieving electricity demand data for the year {year}.")

    dataset = utils.fetcher.fetch_dataframe(
        url, "csv", csv_kwargs={"skiprows": 3}
    )

    index = pd.DatetimeIndex(
        pd.to_datetime(dataset["Date"])
        + pd.to_timedelta(dataset["Hour"], unit="h")
    ).tz_localize(EASTERN_STANDARD_TIME)

    electricity_demand_time_series = pd.Series(
        dataset["Ontario Demand"].values, index=index
    )

    return electricity_demand_time_series
