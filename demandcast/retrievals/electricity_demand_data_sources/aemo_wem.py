"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Australian Energy Market Operator
    (AEMO) for the Wholesale Electricity Market (WEM) in Western
    Australia. The data is retrieved in one-year intervals in CSV format
    until September 2023, and from October 2023 in daily intervals in
    JSON format.

    The files give the operational demand in MW of each interval, of 30
    minutes until September 2023 and 5 minutes since, at its start, in
    AWST, which is UTC+8 all year. The trading days start at 08:00.

    Source: https://data.wa.aemo.com.au/#operational-demand
    Source: https://data.wa.aemo.com.au/public/market-data/wemde/operationalDemandWithdrawal/dailyFiles/
"""

import datetime
import logging

import pandas as pd
import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[bool, int, int | None, int | None]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the AEMO website.

    Parameters
    ----------
    code : str
        The code of Western Australia.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[bool, int, int | None, int | None]]
        The requests, as tuples in the format (pre_reform, year, month,
        day), where the month and day are None for the yearly files.
    """
    # Define the date that marks the beginning of the post-reform
    # period.
    post_reform_start_date = pd.Timestamp("2023-10-01")

    # Define the list of available requests for the pre-reform period,
    # which are the years from 2006 to 2023.
    pre_reform_values = list(
        range(start_date.year, post_reform_start_date.year + 1)
    )

    # Define the list of available requests for the post-reform period,
    # which are the year, month, and day from October 1, 2023, to today.
    post_reform_values = (
        pd.date_range(
            start=post_reform_start_date,
            end=end_date,
            freq="D",
        )
        .strftime("%Y-%m-%d")
        .str.split("-")
        .tolist()
    )

    # Return the available requests that combine the two lists and add a
    # boolean flag to indicate if the request is for the pre-reform
    # period.
    return [(True, year, None, None) for year in pre_reform_values] + [
        (False, int(year), int(month), int(day))
        for year, month, day in post_reform_values
    ]


def get_url(
    pre_reform: bool, year: int, month: int | None, day: int | None
) -> str:
    """
    Get the URL of the electricity demand data on the AEMO website.

    Parameters
    ----------
    pre_reform : bool
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023).
    year : int
        The year of the data to retrieve.
    month : int, optional
        The month of the data to retrieve.
    day : int, optional
        The day of the data to retrieve.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    if pre_reform:
        # If the request is for the pre-reform period, set the URL to
        # fetch .csv files for data from 2006 to 2023.
        return (
            "https://data.wa.aemo.com.au/datafiles/operational-demand/"
            f"operational-demand-{year}.csv"
        )

    # If the request is for the post-reform period, set the URL to
    # fetch .json files for data from September 2023 onward.
    return (
        "https://data.wa.aemo.com.au/public/market-data/wemde/"
        "operationalDemandWithdrawal/dailyFiles/"
        f"OperationalDemandAndWithdrawal_{year}-{month:02d}-{day:02d}.json"
    )


def download_and_extract_data_for_request(
    pre_reform_and_date: tuple[bool, int, int | None, int | None], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the AEMO website.

    Parameters
    ----------
    pre_reform_and_date : tuple[bool, int, int | None, int | None]
        A boolean flag to indicate if the request is for the pre-reform
        period (until 2023), and the year, month and day of the
        electricity demand data. The month and the day are None for
        the pre-reform period.
    code : str
        The code of Western Australia.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    pre_reform, year, month, day = pre_reform_and_date

    if pre_reform:
        logging.info(
            f"Retrieving electricity demand data for the year {year}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_dataframe(url, "csv")

        # Extract the electricity demand data from the dataset.
        electricity_demand_time_series = pd.Series(
            dataset["Operational Demand (MW)"].values,
            index=pd.to_datetime(dataset["Trading Interval"]),
        )

        # The timestamps are in AWST, which is UTC+8 all year, also
        # during the daylight saving that Perth trialled from 2006 to
        # 2009. Move them to the ends of the trading intervals, because
        # the demand data seems to be reported at their beginning.
        electricity_demand_time_series = (
            utils.time_series.localize_interval_starts(
                electricity_demand_time_series,
                datetime.timezone(datetime.timedelta(hours=8)),
                pd.Timedelta(minutes=30),
            ).tz_convert("UTC")
        )

    else:
        logging.info(
            "Retrieving electricity demand data for "
            f"{year}-{month:02d}-{day:02d}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_dataframe(
            url,
            "html",
            read_with="requests.get",
            read_as="json",
            json_keys=["data", "data"],
        )

        # Extract the electricity demand data from the dataset. The
        # times are the starts of the 5-minute dispatch intervals, with
        # their offset from UTC: move them to the ends of the intervals.
        electricity_demand_time_series = pd.Series(
            dataset["operationalDemand"].values,
            index=pd.to_datetime(dataset["dispatchInterval"], utc=True)
            + pd.Timedelta(minutes=5),
        )

    return electricity_demand_time_series
