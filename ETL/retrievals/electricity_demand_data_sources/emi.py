#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Electricity Market Information (EMI)
    in New Zealand. The data is downloaded from Jan 1, 2005 up to the
    current date. The data is retrieved all at once.

    Source: https://www.emi.ea.govt.nz/Wholesale/Reports/W_GD_C
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
    logging.debug("CC-BY 4.0 license. Use for any purpose with attribution.")
    logging.debug("Source: https://www.emi.ea.govt.nz/LegalInformation")
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
        utils.entities.read_date_ranges(data_source="emi")["NZ"][0]
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
    demand data from the EMI website.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(data_source="emi")[
        "NZ"
    ]

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
    Get the URL of the electricity demand data on the EMI website.

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
        "https://www.emi.ea.govt.nz/Wholesale/Download/DataReport/CSV/W_GD_C"
        f"?DateFrom={start_date.strftime('%Y%m%d')}"
        f"&DateTo={end_date.strftime('%Y%m%d')}"
        "&RegionType=NZ"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp, end_date: pandas.Timestamp
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the EMI website.

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
        csv_kwargs={"skiprows": 11},
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Extract the electricity demand time series. Convert GWh to MW
        # considering a 0.5-hour time step.
        electricity_demand_time_series = pandas.Series(
            dataset["Demand (GWh)"].to_numpy() * 1000 / 0.5,
            index=pandas.to_datetime(
                dataset["Period end"], format="%d/%m/%Y %H:%M:%S"
            ),
        )

        # Add the time zone information to the time series.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize(
                "Pacific/Auckland", ambiguous="NaT", nonexistent="NaT"
            )
        )

        return electricity_demand_time_series
