"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Australian Energy Market Operator
    (AEMO) for the National Electricity Market (NEM) in Australia. The
    data is retrieved for the years from December of 1998 to the current
    month. The data is retrieved from the available CSV files on the
    AEMO website.

    Source: https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data
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
) -> list[tuple[int, int]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the AEMO website.

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
    available_requests : list[tuple[int, int]]
        The list of available requests.
    """
    # Get the list of available requests (year, month).
    values_list = (
        pd.date_range(start=start_date, end=end_date, freq="ME")
        .strftime("%Y-%m")
        .str.split("-")
        .tolist()
    )

    # Return the available requests, which are tuples in the format
    # (year, month).
    return [(int(year), int(month)) for year, month in values_list]


def get_url(year: int, month: int, code: str) -> str:
    """
    Get the URL of the electricity demand data on the AEMO website.

    Parameters
    ----------
    month : int
        The month of the data to retrieve.
    year : int
        The year of the data to retrieve.
    code : str
        The code of the subdivision.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Define the URL of the electricity demand data.
    url = (
        "https://aemo.com.au/aemo/data/nem/priceanddemand/"
        f"PRICE_AND_DEMAND_{year}{month:02d}_{subdivision_code}1.csv"
    )

    return url


def download_and_extract_data_for_request(
    year_and_month: tuple[int, int], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the AEMO website.

    Parameters
    ----------
    year_and_month : tuple[int, int]
        The year and month of the electricity demand data.
    code : str
        The subdivision code of the electricity demand data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity generation time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    year, month = year_and_month

    logging.info(
        "Retrieving electricity demand data for the "
        f"year {year} and month {month}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(year, month, code)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.get",
        header_params={"User-Agent": "Mozilla/5.0"},
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand data from the dataset.
    electricity_demand_time_series = pd.Series(
        dataset["TOTALDEMAND"].values,
        index=pd.to_datetime(dataset["SETTLEMENTDATE"]),
    )

    # Add the time zone information to the index. The timestamps are in
    # NEM time, which is UTC+10 all year, without daylight saving.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize(
            datetime.timezone(datetime.timedelta(hours=10))
        )
    )

    return electricity_demand_time_series
