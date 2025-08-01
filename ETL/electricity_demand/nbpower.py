# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the New Brunswick Power Corporation
    (NB Power) in Canada. The data is retrieved for the years from 2018
    to current year. The data is retrieved in one-month intervals.

    Source: https://tso.nbpower.com/Public/en/system_information_archive.aspx
"""  # noqa: W505

import logging

import pandas
import utils.entities
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("All rights reserved by NB Power.")
    logging.debug("Source: https://www.nbpower.com/en/terms-of-use")
    return False


def _check_input_parameters(year: int, month: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    month : int
        The month of the electricity demand data.
    """
    # Check if the year and month are supported.
    assert (year, month) in get_available_requests(), (
        f"Year {year} and month {month} are not available."
    )


def get_available_requests() -> list[tuple[int, int]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the NB Power website.

    Returns
    -------
    list[tuple[int, int]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="nbpower"
    )["CA_NB"]

    # Get the list of available requests, which are the years and
    # months.
    values_list = (
        pandas.date_range(start=start_date, end=end_date, freq="ME")
        .strftime("%Y-%m")
        .str.split("-")
        .tolist()
    )

    # Return the available requests, which are tuples in the format
    # (year, month).
    return [(int(year), int(month)) for year, month in values_list]


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the NB Power website.

    Returns
    -------
    str
        The URL of the electricity demand data
    """
    # Return the URL of the electricity demand data.
    return "https://tso.nbpower.com/Public/en/system_information_archive.aspx"


def download_and_extract_data_for_request(
    year: int, month: int
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the NB Power website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    month : int
        The month of the electricity demand data.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if input parameters are valid.
    _check_input_parameters(year, month)

    logging.info(
        "Retrieving electricity demand data for the "
        f"year {year} and month {month}."
    )

    # Get the URL of the electricity demand data.
    url = get_url()

    # Fetch HTML content from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.post",
        post_data_params={
            "__EVENTTARGET": "ctl00$cphMainContent$lbGetData",
            "ctl00$cphMainContent$ddlMonth": month,
            "ctl00$cphMainContent$ddlYear": year,
        },
        query_aspx_webpage=True,
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Extract the electricity demand time series.
        # It is unclear whether the time values represent the start or
        # end of the hour. Most likely, they represent the start of the
        # hour but this is not confirmed.
        electricity_demand_time_series = pandas.Series(
            dataset["NB_LOAD"].values,
            index=pandas.to_datetime(
                dataset["HOUR"].values, format="%Y-%m-%d %H:%M"
            ),
        )

        # Convert the time zone of the electricity demand time series to
        # UTC.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize(
                "America/Moncton", ambiguous="infer"
            )
        )

        return electricity_demand_time_series
