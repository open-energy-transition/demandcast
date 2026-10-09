"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Administrador del Mercado Eléctrico (ADME)
    in  Uruguay. The data is retrieved for the years from 2019 to the
    current date. The data is retrieved from the available CSV files
    on the ADME website.

    Source: https://adme.com.uy/controlpanel.php
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
    logging.debug("Open data.")
    logging.debug("Source: https://adme.com.uy/datosabiertos.html")
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the ADME website.

    Parameters
    ----------
    code : str
        The code of Uruguay.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Define intervals for the retrieval periods.
    intervals = pd.date_range(start_date, end_date, freq="YS")
    intervals = intervals.union(pd.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-year period.
    return list(zip(start_dates_and_times, end_dates_and_times, strict=True))


def get_url(start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    """
    Get the URL of the electricity demand data on the ADME website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date : pandas.Timestamp
        The end date and time of the data retrieval.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the retrieval period is longer than 1 year.
    """
    # The website gives at most 1 year of data per request.
    if end_date - start_date > pd.Timedelta("366days"):
        raise ValueError(
            "The retrieval period must be less than or equal to 1 year. "
            f"start_date: {start_date}, end_date: {end_date}"
        )

    return (
        "https://adme.com.uy/panelControl/gpf.php?anod="
        f"{start_date.year}&mesd={start_date.month}&anoh="
        f"{end_date.year}&mesh={end_date.month}&granularidad=1&fuente=1&tipo=1"
    )


def download_and_extract_data_for_request(
    period: tuple[pd.Timestamp, pd.Timestamp], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ADME website.

    Parameters
    ----------
    period : tuple[pandas.Timestamp, pandas.Timestamp]
        The start and end date and time of the data retrieval.
    code : str
        The code of Uruguay.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    start_date, end_date = period

    logging.info(
        f"Retrieving data from {start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(start_date, end_date)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        content_type="csv",
        csv_kwargs={"sep": ";"},
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Demanda"].values,
        index=pd.to_datetime(dataset["Fecha"], format="%d-%m-%Y %H:%M"),
    )

    # Add the time zone information to the time series.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("America/Montevideo")
    )

    return electricity_demand_time_series
