# -*- coding: utf-8 -*-
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
    logging.debug("Open data.")
    logging.debug("Source: https://adme.com.uy/datosabiertos.html")
    return True


def _check_input_parameters(
    start_date: pandas.Timestamp,
    end_date: pandas.Timestamp,
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    """
    # Check if the retrieval period is less than 1 year.
    assert (end_date - start_date) <= pandas.Timedelta("366days"), (
        "The retrieval period must be less than or equal to 1 year. "
        f"start_date: {start_date}, end_date: {end_date}"
    )

    # Read the start date of the available data.
    start_date_of_data_availability = pandas.to_datetime(
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "adme"
        )["URY"][0]
    )

    # Check that the start date is greater than or equal to the
    # beginning of the data availability.
    assert start_date >= start_date_of_data_availability, (
        "The beginning of the data availability is "
        f"{start_date_of_data_availability}."
    )


def get_available_requests() -> list[
    tuple[pandas.Timestamp, pandas.Timestamp]
]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the ADME website.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "adme"
        )["URY"]
    )

    # Define intervals for the retrieval periods.
    intervals = pandas.date_range(start_date, end_date, freq="YS")
    intervals = intervals.union(pandas.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-year period.
    return list(zip(start_dates_and_times, end_dates_and_times))


def get_url(start_date: pandas.Timestamp, end_date: pandas.Timestamp) -> str:
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
    """
    # Check if the input parameters are valid.
    _check_input_parameters(start_date, end_date)

    return (
        "https://adme.com.uy/panelControl/gpf.php?anod="
        f"{start_date.year}&mesd={start_date.month}&anoh="
        f"{end_date.year}&mesh={end_date.month}&granularidad=1&fuente=1&tipo=1"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp, end_date: pandas.Timestamp
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ADME website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date : pandas.Timestamp
        The end date and time of the data retrieval.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(start_date, end_date)

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
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pandas.Series(
        dataset["Demanda"].values,
        index=pandas.to_datetime(dataset["Fecha"], format="%d-%m-%Y %H:%M"),
    )

    # Add the time zone information to the time series.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index.tz_localize("America/Montevideo")
    )

    return electricity_demand_time_series
