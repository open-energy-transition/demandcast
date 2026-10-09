"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Australian Energy Market Operator
    (AEMO) for the Wholesale Electricity Market (WEM) in Western
    Australia. The data is retrieved from 2006 to 2023 in one-year
    intervals in CSV format, and from October 1, 2023, to today in daily
    intervals in JSON format.

    Source: https://data.wa.aemo.com.au/#operational-demand
    Source: https://data.wa.aemo.com.au/public/market-data/wemde/operationalDemandWithdrawal/dailyFiles/
"""

import datetime
import logging

import pandas as pd
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Use for any purpose with attribution to AEMO.")
    logging.debug(
        "Source: "
        "https://aemo.com.au/privacy-and-legal-notices/copyright-permissions"
    )
    return True


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
        List of tuples in the format (year, month, day).
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
        The electricity generation time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    pre_reform, year, month, day = pre_reform_and_date

    if pre_reform:
        logging.info(
            f"Retrieving electricity demand data for the year {year}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_data(url, "csv")

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pd.DataFrame):
            raise TypeError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )

        # Extract the electricity demand data from the dataset.
        electricity_demand_time_series = pd.Series(
            dataset["Operational Demand (MW)"].values,
            index=pd.to_datetime(dataset["Trading Interval"]),
        )

        # Add the time zone information to the index. The timestamps are
        # in AWST, which is UTC+8 all year, also during the daylight
        # saving that Perth trialled from 2006 to 2009.
        electricity_demand_time_series = (
            electricity_demand_time_series.tz_localize(
                datetime.timezone(datetime.timedelta(hours=8))
            ).tz_convert("UTC")
        )

        # Add 30 minutes to the index because the demand data seems
        # to be reported at the beginning of the trading interval.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index + pd.Timedelta(minutes=30)
        )

    else:
        logging.info(
            "Retrieving electricity demand data for "
            f"{year}-{month:02d}-{day:02d}."
        )

        # Get the URL of the electricity demand data.
        url = get_url(pre_reform, year, month, day)

        # Fetch the data from the URL.
        dataset = utils.fetcher.fetch_data(
            url,
            "html",
            read_with="requests.get",
            read_as="json",
            json_keys=["data", "data"],
        )

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pd.DataFrame):
            raise TypeError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )

        # Extract the electricity demand data from the dataset.
        electricity_demand_time_series = pd.Series(
            dataset["operationalDemand"].values,
            index=pd.to_datetime(dataset["asAtTimeStamp"], utc=True),
        )

    return electricity_demand_time_series
