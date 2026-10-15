"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the US Energy Information Administration
    (EIA). The data is retrieved in six-month intervals.

    Source: https://www.eia.gov/opendata/browser/electricity/rto/region-data
"""

import datetime
import logging

import pandas as pd
import utils.config
import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EIA website.

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
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Split the period of the data into six-month periods, which avoids
    # the limitation of the API to retrieve a maximum of 5000 data
    # points.
    return utils.time_series.split_period(start_date, end_date, "6MS")


def get_url(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    code: str,
) -> str:
    """
    Get the URL of the electricity demand data on the EIA website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the number of time points is greater than 5000, or if the
        EIA API key is not set.
    """
    # Check that the number of time points is less than 5000.
    if (end_date - start_date).days * 24 >= 5000:
        raise ValueError("The number of time points is greater than 5000.")

    # Get the API key.
    api_key = utils.config.read_api_key("EIA_API_KEY", "EIA")

    # Convert the start and end dates and times to the required format.
    start = start_date.strftime("%Y-%m-%dT%H")
    end = end_date.strftime("%Y-%m-%dT%H")

    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Return the URL of the electricity demand data.
    return (
        "https://api.eia.gov/v2/electricity/rto/region-data/data/?"
        f"api_key={api_key}&facets[type][]=D&"
        f"facets[respondent][]={subdivision_code}&"
        f"start={start}&end={end}&frequency=hourly&data[0]=value&"
        "sort[0][column]=period&sort[0][direction]=asc&offset=0&length=5000"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the EIA website.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The start and end date of the data retrieval.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    start_date, end_date = period

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(start_date, end_date, code)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_dataframe(
        url,
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["response", "data"],
    )

    # Create the electricity demand time series. The API gives the
    # values as text.
    electricity_demand_time_series = pd.Series(
        pd.to_numeric(dataset["value"]).to_numpy(),
        index=pd.to_datetime(dataset["period"]),
    ).tz_localize("UTC")

    return electricity_demand_time_series
