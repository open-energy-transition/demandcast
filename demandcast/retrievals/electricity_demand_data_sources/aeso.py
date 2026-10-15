"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Alberta Electric System Operator (AESO)
    in Canada. The data is retrieved from the CSV files of the hourly
    metered volumes, pool price and Alberta Internal Load (AIL), one
    for each period of several years.

    The demand is the AIL in MW, which includes the load behind the
    fence of industrial sites and the transmission losses, at the start
    of each hour in UTC. The files of the hourly load by area and region
    are not used: from May 2020 they leave out the load behind the
    fence, which is about 30% of the AIL.

    Source: https://www.aeso.ca/market/market-and-system-reporting/data-requests/hourly-generation-metered-volumes-and-pool-price-and-ail-data-2001-to-july-2025/
"""

import datetime
import logging

import pandas as pd
import utils.fetcher
import utils.time_series

# The periods of the files, by the first and last year of their data.
FILE_PERIODS = {
    "2001-2009": (2001, 2009),
    "2010-2019": (2010, 2019),
    "2020-Jul2025": (2020, 2025),
}


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[str]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the AESO website.

    Parameters
    ----------
    code : str
        The code of Alberta.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[str]
        The periods of the files with data between the dates.
    """
    return [
        period
        for period, (first_year, last_year) in FILE_PERIODS.items()
        if first_year <= end_date.year and start_date.year <= last_year
    ]


def get_url(period: str) -> str:
    """
    Get the URL of the electricity demand data on the AESO website.

    Parameters
    ----------
    period : str
        The period of the file, such as "2010-2019".

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return (
        "https://www.aeso.ca/assets/Uploads/data-requests/"
        f"Hourly_Metered_Volumes_and_Pool_Price_and_AIL_{period}.csv"
    )


def download_and_extract_data_for_request(period: str, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the AESO website.

    Parameters
    ----------
    period : str
        The period of the file, such as "2010-2019".
    code : str
        The code of Alberta.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    logging.info(f"Retrieving electricity demand data for {period}.")

    # Fetch the times and the AIL, out of the many columns of the
    # generating assets.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(period),
        "csv",
        csv_kwargs={"usecols": ["Date_Begin_GMT", "ACTUAL_AIL"]},
    )

    # The times are the starts of the hours in UTC, written as
    # "2010-01-01 7:00" or, in the file of 2010 to 2019, as
    # "1/1/2010 7:00", month first. Move them to the ends of the hours.
    electricity_demand_time_series = pd.Series(
        dataset["ACTUAL_AIL"].to_numpy(),
        index=pd.to_datetime(dataset["Date_Begin_GMT"], format="mixed"),
    )
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series, "UTC", pd.Timedelta(hours=1)
        )
    )

    return electricity_demand_time_series
